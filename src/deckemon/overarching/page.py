import threading
import traceback

from deck import deck, Button


class Page:
    name = "?"
    interval: float | None = None  # seconds between tick()s, None = static page

    def __init__(self, buttons: list[Button]):
        self.buttons = buttons
        self._stop: threading.Event | None = None

    def tick(self):
        pass

    def enter(self):
        if self.interval is None:
            return
        self._stop = threading.Event()
        threading.Thread(target=self._run, args=(self._stop,), daemon=True).start()

    def leave(self):
        if self._stop:
            self._stop.set()

    def _run(self, stop: threading.Event):
        while True:
            try:
                self.tick()
                deck.redraw()
            except Exception:
                traceback.print_exc()
            if stop.wait(self.interval):
                return