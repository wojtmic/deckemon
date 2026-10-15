from deckemon.util import icon
import subprocess
from deckemon.deck import deck, Button

SRC = '@DEFAULT_AUDIO_SOURCE@'

MIC = icon("mic.svg")
MIC_MUTED = icon("mic-muted.svg")

def is_muted() -> bool:
    out = subprocess.run(
        ["wpctl", "get-volume", SRC],
        capture_output=True, text=True, check=True,
    ).stdout
    return "[MUTED]" in out

muted = is_muted()

def toggle_mute():
    global muted
    muted = not muted
    deck.keys[0].image = MIC_MUTED if muted else MIC
    subprocess.run(["wpctl", "set-mute", SRC, "toggle"], check=True)
    deck.redraw()

mute_button = Button(image=MIC_MUTED if muted else MIC, callback=toggle_mute)
