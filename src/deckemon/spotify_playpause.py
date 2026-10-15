import subprocess
import threading
from util import svg
from deck import deck, Button

PLAYER = ["playerctl", "-p", "spotify"]

PLAY = svg("icons/play.svg")
PAUSE = svg("icons/pause.svg")

def toggle():
    subprocess.run([*PLAYER, "play-pause"])

spotify_button = Button(image=PLAY, callback=toggle)

def _watch():
    proc = subprocess.Popen([*PLAYER, "--follow", "status"], stdout=subprocess.PIPE, text=True)
    for line in proc.stdout:
        spotify_button.image = PAUSE if line.strip() == "Playing" else PLAY
        deck.redraw()

threading.Thread(target=_watch, daemon=True).start()
