import glob
import subprocess
from collections import deque
from pathlib import Path

import psutil
from PIL import Image, ImageDraw, ImageFont

from deck import Button, deck
from overarching.page import Page

HISTORY = 36
W, H = deck.device.key_image_format()["size"]
F_SMALL = ImageFont.load_default(size=11)
F_BIG = ImageFont.load_default(size=20)


def _read(p: Path) -> int:
    return int(p.read_text())


def _find_dgpu() -> Path:
    # 7800X3D has an iGPU too; pick the card with the most VRAM
    cards = {Path(p).parent.resolve() for p in glob.glob("/sys/class/drm/card*/device/mem_info_vram_total")}
    return max(cards, key=lambda d: _read(d / "mem_info_vram_total"))


GPU = _find_dgpu()
GPU_TEMP = next(
    (p.with_name(p.name.replace("_label", "_input"))
     for p in GPU.glob("hwmon/hwmon*/temp*_label")
     if p.read_text().strip() == "junction"),
    None,
)


def _tctl():
    for s in psutil.sensors_temperatures().get("k10temp", []):
        if s.label == "Tctl":
            return s.current
    return None


def _temp(t):
    return f"{t:.0f}°" if t is not None else ""


def cpu():
    pct = psutil.cpu_percent()
    return pct, f"{pct:.0f}%", _temp(_tctl())


def gpu():
    pct = _read(GPU / "gpu_busy_percent")
    return pct, f"{pct}%", _temp(_read(GPU_TEMP) / 1000 if GPU_TEMP else None)


def ram():
    vm = psutil.virtual_memory()
    return vm.percent, f"{vm.used / 2**30:.1f}G", f"{vm.total / 2**30:.0f}G"


def vram():
    used, total = _read(GPU / "mem_info_vram_used"), _read(GPU / "mem_info_vram_total")
    return used / total * 100, f"{used / 2**30:.1f}G", f"{total / 2**30:.0f}G"


METRICS = [
    ("CPU", cpu, (79, 195, 247)),
    ("GPU", gpu, (255, 112, 67)),
    ("RAM", ram, (171, 71, 188)),
    ("VRAM", vram, (255, 202, 40)),
]


def _draw(label, color, history, pct, value, sub):
    img = Image.new("RGB", (W, H), "black")
    d = ImageDraw.Draw(img)

    # sparkline
    top, bottom = 18, H - 6
    pts = [(i * (W - 1) / (HISTORY - 1), bottom - min(v, 100) / 100 * (bottom - top))
           for i, v in enumerate(history)]
    d.polygon([(0, bottom), *pts, (W - 1, bottom)], fill=tuple(c // 4 for c in color))
    d.line(pts, fill=color, width=2)

    # fill bar
    d.rectangle((0, H - 4, W - 1, H - 1), fill=(40, 40, 40))
    d.rectangle((0, H - 4, round((W - 1) * min(pct, 100) / 100), H - 1), fill=color)

    # text
    s = dict(stroke_width=2, stroke_fill="black")
    d.text((4, 3), label, font=F_SMALL, fill=color, **s)
    if sub:
        d.text((W - 4, 3), sub, font=F_SMALL, anchor="ra", fill=(200, 200, 200), **s)
    d.text((W / 2, H / 2 + 4), value, font=F_BIG, anchor="mm", fill="white", **s)
    return img


def _btop():
    subprocess.Popen(["kitty", "btop"], start_new_session=True)


class SysMon(Page):
    name = "Sysmon"
    interval = 1.0

    def __init__(self):
        super().__init__([Button(callback=_btop) for _ in METRICS])
        self.history = [deque([0.0] * HISTORY, maxlen=HISTORY) for _ in METRICS]

    def tick(self):
        for btn, hist, (label, fn, color) in zip(self.buttons, self.history, METRICS):
            pct, value, sub = fn()
            hist.append(pct)
            btn.image = _draw(label, color, hist, pct, value, sub)


page = SysMon()