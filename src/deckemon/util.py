import subprocess
from io import BytesIO
from PIL import Image
from pathlib import Path

ICONS = Path(__file__).parent / "icons"

def icon(path, size=72):
    png = subprocess.run(
        ["rsvg-convert", "-w", str(size), "-h", str(size), ICONS / path],
        check=True, capture_output=True,
    ).stdout
    return Image.open(BytesIO(png))
