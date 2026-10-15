import traceback

from PIL import Image

from deckemon.deck import Button, deck
from deckemon.overarching import discord, sysmon
from deckemon.util import icon

SWITCHER = 10
SLOTS = [11, 12, 13, 14]
PAGES = [sysmon.page, discord.page]

ICON_SIZE = 34
W, H = deck.device.key_image_format()["size"]

_index = 0
switcher = Button()

def _page_icon(page):
    try:
        ic = icon(f"overarching-{page.name.lower()}.svg").convert("RGBA")
    except Exception:
        traceback.print_exc()
        return None  # no icon → title only
    ic = ic.resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS)
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    canvas.paste(ic, ((W - ICON_SIZE) // 2, 9), ic)
    return canvas

def _show():
    page = PAGES[_index]
    for slot, btn in zip(SLOTS, page.buttons):
        deck.keys[slot] = btn
    switcher.title = page.name
    switcher.image = _page_icon(page)
    deck.redraw()

def _switch():
    global _index
    PAGES[_index].leave()
    _index = (_index + 1) % len(PAGES)
    PAGES[_index].enter()
    _show()

switcher.callback = _switch

def setup():
    deck.keys[SWITCHER] = switcher
    PAGES[_index].enter()
    _show()
