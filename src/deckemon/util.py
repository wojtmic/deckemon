import subprocess
from io import BytesIO
from PIL import Image

def svg(path, size=72):
    png = subprocess.run(
        ["rsvg-convert", "-w", str(size), "-h", str(size), path],
        check=True, capture_output=True,
    ).stdout
    return Image.open(BytesIO(png))
