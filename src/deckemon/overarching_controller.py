from deck import Button, deck
from overarching import sysmon

SWITCHER = 10
SLOTS = [11, 12, 13, 14]
PAGES = [sysmon.page]

_index = 0


def _show():
    page = PAGES[_index]
    for slot, btn in zip(SLOTS, page.buttons):
        deck.keys[slot] = btn
    switcher.title = page.name
    deck.redraw()


def _switch():
    global _index
    PAGES[_index].leave()
    _index = (_index + 1) % len(PAGES)
    PAGES[_index].enter()
    _show()


switcher = Button(callback=_switch)


def setup():
    deck.keys[SWITCHER] = switcher
    PAGES[_index].enter()
    _show()