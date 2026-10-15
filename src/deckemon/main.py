from deck import deck
from mute import mute_button
from spotify_playpause import spotify_button
import overarching_controller

deck.keys[0] = mute_button
deck.keys[5] = spotify_button
overarching_controller.setup()
deck.run()