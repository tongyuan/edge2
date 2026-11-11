from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent
SOURCE = Path(
    "/var/folders/dm/ctz4b4_d2yq9jbskg25nx6xw0000gn/T/"
    "codex-clipboard-cc67abab-488a-4bca-b95c-ef9fc83b76f5.png"
)
ITEMS = (
    ("SOURCE DESIGN", SOURCE),
    ("SYMBOLS · NVDA", ROOT / "symbols-nvda-desktop-final.png"),
    ("GROUP RADAR · MAG7", ROOT / "group-radar-mag7-desktop.png"),
    ("EVENTS · AAPL", ROOT / "events-aapl-desktop.png"),
)


def fitted(image: Image.Image, width: int, height: int) -> Image.Image:
    copy = image.copy()
    copy.thumbnail((width, height), Image.Resampling.LANCZOS)
    return copy


canvas = Image.new("RGB", (1672, 1760), "#050a0f")
draw = ImageDraw.Draw(canvas)
source = fitted(Image.open(ITEMS[0][1]).convert("RGB"), 1632, 900)
draw.text((20, 12), ITEMS[0][0], fill="#53e0ae")
canvas.paste(source, ((1672 - source.width) // 2, 38))

column_width = 544
for index, (label, path) in enumerate(ITEMS[1:]):
    x = 12 + (index * 552)
    draw.text((x, 970), label, fill="#53e0ae")
    image = fitted(Image.open(path).convert("RGB"), column_width, 740)
    canvas.paste(image, (x, 996))

canvas.save(ROOT / "comparison-board.jpg", quality=92, optimize=True)
