from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from deckemon.deck import Button, deck
from deckemon.discord_rpc import rpc
from deckemon.overarching.page import Page
from deckemon.util import icon

W, H = deck.device.key_image_format()["size"]
FONT = ImageFont.load_default(size=12)
ICON_SIZE = 34
ICON_DIR = Path(__file__).parent.parent / "icons" / "discord"

WHITE = (255, 255, 255)
BLURPLE = (88, 101, 242)
RED = (237, 66, 69)
GREY = (130, 130, 130)

ICONS = {
    name: icon(f"{name}.svg", ICON_SIZE).convert("RGBA")
    for name in ("mic", "mic-off", "headphones", "headphones-off",
                 "screen", "screen-live", "voice", "voice-off")
}


def _fit(text, width):
    if FONT.getlength(text) <= width:
        return text
    while text and FONT.getlength(text + "…") > width:
        text = text[:-1]
    return text + "…"


def tile(icon, text, color):
    img = Image.new("RGB", (W, H), "black")
    ic = ICONS[icon]
    # use the white icon's alpha as a mask to stamp it in `color`
    img.paste(Image.new("RGB", ic.size, color), ((W - ic.width) // 2, 9), ic)
    ImageDraw.Draw(img).text((W / 2, H - 13), _fit(text, W - 8), font=FONT, fill=color, anchor="mm")
    return img


def _when_connected(fn):
    def wrapper():
        if rpc.connected:
            fn()
    return wrapper


class DiscordPage(Page):
    name = "Discord"

    def __init__(self):
        self.mute_btn = Button(callback=_when_connected(lambda: self._set(mute=not self.muted)))
        self.deaf_btn = Button(callback=_when_connected(lambda: self._set(deaf=not self.deafened)))
        self.share_btn = Button(callback=_when_connected(lambda: rpc.command("TOGGLE_SCREENSHARE")))
        self.chan_btn = Button(callback=_when_connected(self._leave))
        super().__init__([self.mute_btn, self.deaf_btn, self.share_btn, self.chan_btn])

        self.muted = self.deafened = self.sharing = False
        self.channel_name: str | None = None

        rpc.on("VOICE_SETTINGS_UPDATE", self._on_settings)
        rpc.on("VOICE_CHANNEL_SELECT", self._on_channel)
        rpc.on("SCREENSHARE_STATE_UPDATE", self._on_share)
        rpc.on_connect(self._sync)
        rpc.on_disconnect(self._render)
        self._render()
        rpc.start()

    def _set(self, **kw):
        rpc.command("SET_VOICE_SETTINGS", kw)  # state comes back via VOICE_SETTINGS_UPDATE

    def _leave(self):
        if self.channel_name:
            rpc.command("SELECT_VOICE_CHANNEL", {"channel_id": None, "force": True})

    def _sync(self):
        self._on_settings(rpc.command("GET_VOICE_SETTINGS"))
        ch = rpc.command("GET_SELECTED_VOICE_CHANNEL")
        self.channel_name = ch["name"] if ch else None
        self.sharing = False  # no GET for screenshare state; corrected on next update
        self._render()

    def _on_settings(self, d):
        self.muted, self.deafened = d["mute"], d["deaf"]
        self._render()

    def _on_channel(self, d):
        cid = d.get("channel_id")
        self.channel_name = rpc.command("GET_CHANNEL", {"channel_id": cid})["name"] if cid else None
        if not cid:
            self.sharing = False
        self._render()

    def _on_share(self, d):
        self.sharing = d["active"]
        self._render()

    def _render(self):
        if not rpc.connected:
            for b in self.buttons:
                b.image = tile("voice-off", "Offline", GREY)
        else:
            self.mute_btn.image = (tile("mic-off", "Muted", RED) if self.muted
                                   else tile("mic", "Mute", WHITE))
            self.deaf_btn.image = (tile("headphones-off", "Deafened", RED) if self.deafened
                                   else tile("headphones", "Deafen", WHITE))
            self.share_btn.image = (tile("screen-live", "Live", RED) if self.sharing
                                    else tile("screen", "Share", WHITE))
            self.chan_btn.image = (tile("voice", self.channel_name, BLURPLE) if self.channel_name
                                   else tile("voice-off", "Not in VC", GREY))
        deck.redraw()


page = DiscordPage()