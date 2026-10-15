from deckemon.deck import deck
from deckemon.mute import mute_button
from deckemon.spotify_playpause import spotify_button
import deckemon.overarching_controller as overarching_controller

def main():
    deck.keys[0] = mute_button
    deck.keys[5] = spotify_button
    overarching_controller.setup()
    deck.run()