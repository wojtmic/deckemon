import json
import os
import queue
import socket
import struct
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Callable

import keyring

SERVICE = "deckemon"
REDIRECT = "http://localhost"
TOKEN_URL = "https://discord.com/api/oauth2/token"
SCOPES = [
    "rpc",
    "rpc.notifications.read",
    "rpc.voice.read", "rpc.voice.write",
    "rpc.video.read", "rpc.video.write",
    "rpc.screenshare.read", "rpc.screenshare.write",
]

OP_HANDSHAKE, OP_FRAME, OP_CLOSE, OP_PING, OP_PONG = range(5)


class RPCError(Exception):
    pass


class NotRunning(Exception):
    pass


def _secret(name):
    return keyring.get_password(SERVICE, name)


def _socket_paths():
    base = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    for d in (base, base / "app/com.discordapp.Discord", base / "snap.discord"):
        for i in range(10):
            yield d / f"discord-ipc-{i}"


def _token_request(**data):
    body = urllib.parse.urlencode({
        **data,
        "client_id": _secret("discord_client_id"),
        "client_secret": _secret("discord_client_secret"),
    }).encode()
    req = urllib.request.Request(TOKEN_URL, body, {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "deckemon",  # Cloudflare 403s urllib's default UA
    })
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)


class DiscordRPC:
    def __init__(self):
        self.connected = False
        self._sock: socket.socket | None = None
        self._send_lock = threading.Lock()
        self._pending: dict[str, tuple[threading.Event, list]] = {}
        self._subs: dict[str, dict | None] = {}
        self._handlers: dict[str, list[Callable[[dict], None]]] = defaultdict(list)
        self._on_connect: list[Callable[[], None]] = []
        self._on_disconnect: list[Callable[[], None]] = []
        self._events: queue.Queue = queue.Queue()
        self._token: str | None = None
        self._token_exp = 0.0
        self._started = False

    # --- public ---

    def on(self, evt: str, fn: Callable[[dict], None], args: dict | None = None):
        self._subs[evt] = args
        self._handlers[evt].append(fn)

    def on_connect(self, fn: Callable[[], None]):
        self._on_connect.append(fn)

    def on_disconnect(self, fn: Callable[[], None]):
        self._on_disconnect.append(fn)

    def start(self):
        if self._started:
            return
        self._started = True
        threading.Thread(target=self._loop, daemon=True).start()
        threading.Thread(target=self._dispatch, daemon=True).start()

    def command(self, cmd: str, args: dict | None = None, evt: str | None = None, timeout=10.0):
        if self._sock is None:
            raise ConnectionError("not connected to Discord")
        nonce = str(uuid.uuid4())
        done, box = threading.Event(), []
        self._pending[nonce] = (done, box)
        payload = {"cmd": cmd, "args": args or {}, "nonce": nonce}
        if evt:
            payload["evt"] = evt
        try:
            self._send(OP_FRAME, payload)
            if not done.wait(timeout):
                raise TimeoutError(cmd)
        finally:
            self._pending.pop(nonce, None)
        if not box:
            raise ConnectionError("connection lost")
        msg = box[0]
        if msg.get("evt") == "ERROR":
            raise RPCError(f"{cmd}: {msg['data']}")
        return msg["data"]

    # --- transport ---

    def _send(self, op, payload):
        data = json.dumps(payload).encode()
        with self._send_lock:
            self._sock.sendall(struct.pack("<II", op, len(data)) + data)

    def _recv_exact(self, n):
        buf = bytearray()
        while len(buf) < n:
            chunk = self._sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("socket closed")
            buf += chunk
        return bytes(buf)

    def _recv(self):
        op, length = struct.unpack("<II", self._recv_exact(8))
        return op, json.loads(self._recv_exact(length))

    def _connect(self):
        for path in _socket_paths():
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                s.connect(str(path))
            except OSError:
                s.close()
                continue
            self._sock = s
            break
        else:
            raise NotRunning
        self._send(OP_HANDSHAKE, {"v": 1, "client_id": _secret("discord_client_id")})
        op, msg = self._recv()
        if op == OP_CLOSE or msg.get("evt") != "READY":
            raise ConnectionError(f"handshake failed: {msg}")

    def _close(self):
        if self._sock:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)  # wakes the blocked reader
            except OSError:
                pass
            self._sock.close()
            self._sock = None

    # --- threads ---

    def _read_loop(self):
        try:
            while True:
                op, msg = self._recv()
                if op == OP_PING:
                    self._send(OP_PONG, msg)
                elif op == OP_CLOSE:
                    return
                elif p := self._pending.get(msg.get("nonce")):
                    p[1].append(msg)
                    p[0].set()
                elif msg.get("cmd") == "DISPATCH":
                    self._events.put((msg["evt"], msg["data"]))
        except (OSError, ValueError):
            return

    def _dispatch(self):
        # handlers run here, not on the reader, so they can call command()
        while True:
            evt, data = self._events.get()
            for fn in self._handlers.get(evt, []):
                try:
                    fn(data)
                except Exception:
                    traceback.print_exc()

    def _fire(self, callbacks):
        for fn in callbacks:
            try:
                fn()
            except Exception:
                traceback.print_exc()

    def _loop(self):
        while True:
            try:
                self._connect()
                reader = threading.Thread(target=self._read_loop, daemon=True)
                reader.start()
                self._setup()
                self.connected = True
                self._fire(self._on_connect)
                reader.join()
            except NotRunning:
                pass
            except Exception:
                traceback.print_exc()
            finally:
                was_connected, self.connected = self.connected, False
                self._close()
                for done, _ in list(self._pending.values()):
                    done.set()
                if was_connected:
                    self._fire(self._on_disconnect)
            time.sleep(5)

    # --- auth ---

    def _access_token(self):
        if self._token and time.time() < self._token_exp - 60:
            return self._token
        tok = None
        if refresh := _secret("discord_refresh_token"):
            try:
                tok = _token_request(grant_type="refresh_token", refresh_token=refresh)
            except urllib.error.HTTPError:
                pass  # revoked/expired, fall through to AUTHORIZE
        if tok is None:
            code = self.command(
                "AUTHORIZE",
                {"client_id": _secret("discord_client_id"), "scopes": SCOPES},
                timeout=300,  # waiting on you to click the popup
            )["code"]
            tok = _token_request(grant_type="authorization_code", code=code, redirect_uri=REDIRECT)
        keyring.set_password(SERVICE, "discord_refresh_token", tok["refresh_token"])
        self._token, self._token_exp = tok["access_token"], time.time() + tok["expires_in"]
        return self._token

    def _setup(self):
        try:
            self.command("AUTHENTICATE", {"access_token": self._access_token()})
        except RPCError:
            self._token = None
            raise
        for evt, args in self._subs.items():
            try:
                self.command("SUBSCRIBE", args, evt=evt)
            except RPCError as e:
                print(f"[discord] subscribe {evt} failed: {e}")


rpc = DiscordRPC()