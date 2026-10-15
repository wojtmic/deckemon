import subprocess
import threading
from deckemon.util import icon
from deckemon.deck import deck, Button

PLAYER = ["playerctl", "-p", "spotify"]

PLAY = icon("play.svg")
PAUSE = icon("pause.svg")

def toggle():
    subprocess.run([*PLAYER, "play-pause"])

spotify_button = Button(image=PLAY, callback=toggle)

def _watch():
    proc = subprocess.Popen([*PLAYER, "--follow", "status"], stdout=subprocess.PIPE, text=True)
    for line in proc.stdout:
        spotify_button.image = PAUSE if line.strip() == "Playing" else PLAY
        deck.redraw()

threading.Thread(target=_watch, daemon=True).start()
