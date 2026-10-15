import atexit
import signal
import threading
import traceback
from dataclasses import dataclass
from typing import Callable, Optional

from PIL import Image, ImageDraw, ImageFont
from StreamDeck.DeviceManager import DeviceManager
from StreamDeck.ImageHelpers import PILHelper

KEY_COUNT = 15  # Stream Deck MK.2


@dataclass
class Button:
    title: str = ""
    image: Optional[Image.Image] = None
    callback: Optional[Callable[[], None]] = None


class _Deck:
    def __init__(self):
        self.device = DeviceManager().enumerate()[0]
        self.device.open()
        self.device.reset()
        self.keys: list[Button] = [Button() for _ in range(KEY_COUNT)]
        self._font = ImageFont.load_default(size=14)
        self._lock = threading.Lock()
        self._closed = False
        self.device.set_key_callback(self._on_key)
        atexit.register(self.close)

    def _render(self, btn: Button):
        if btn.image:
            img = PILHelper.create_scaled_key_image(self.device, btn.image, margins=[0, 0, 0, 0])
            pos, anchor = (img.width / 2, img.height - 4), "mb"
        else:
            img = PILHelper.create_image(self.device)
            pos, anchor = (img.width / 2, img.height / 2), "mm"
        if btn.title:
            ImageDraw.Draw(img).text(
                pos, btn.title, font=self._font, anchor=anchor,
                fill="white", stroke_width=1, stroke_fill="black",
            )
        return PILHelper.to_native_key_format(self.device, img)

    def redraw(self):
        with self._lock:
            if self._closed:
                return  # background threads may still try to draw during shutdown
            for i, btn in enumerate(self.keys):
                self.device.set_key_image(i, self._render(btn))

    def _on_key(self, _dev, key, pressed):
        cb = self.keys[key].callback
        if pressed and cb:
            try:
                cb()
            except Exception:
                traceback.print_exc()

    def run(self):
        """Block until SIGINT (Ctrl+C) or SIGTERM (systemctl stop), then shut down cleanly."""
        stop = threading.Event()

        def handler(signum, _frame):
            print(f"received {signal.Signals(signum).name}, shutting down")
            stop.set()

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)

        while not stop.wait(0.5):
            pass
        self.close()

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            try:
                self.device.reset()
                self.device.close()
            except Exception:
                pass


deck = _Deck()