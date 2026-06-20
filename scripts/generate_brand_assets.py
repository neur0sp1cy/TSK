#!/usr/bin/env python3
"""Generate UI-sized avatar and favicons from web/static/tsk-avatar.png."""

from pathlib import Path
import shutil

try:
    from PIL import Image
except ImportError:
    raise SystemExit("Install Pillow: uv run --with pillow python scripts/generate_brand_assets.py")

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "web" / "static"
AVATAR_SRC = STATIC / "tsk-avatar.png"


def square_crop_bow(img: Image.Image, bow_center_y_ratio: float = 0.38) -> Image.Image:
    """Crop a square centered on the key bow (skull) for small favicon readability."""
    w, h = img.size
    side = min(w, h)
    cx = w // 2
    cy = int(h * bow_center_y_ratio)
    left = max(0, min(cx - side // 2, w - side))
    top = max(0, min(cy - side // 2, h - side))
    return img.crop((left, top, left + side, top + side))


def main() -> None:
    if not AVATAR_SRC.is_file():
        raise SystemExit(f"Missing {AVATAR_SRC}")

    avatar = Image.open(AVATAR_SRC).convert("RGBA")
    avatar.resize((128, 128), Image.Resampling.LANCZOS).save(
        STATIC / "tsk-avatar-ui.png", optimize=True
    )

    favicon_src = square_crop_bow(avatar) if avatar.size[0] != avatar.size[1] else avatar

    for size, name in [(16, "favicon-16.png"), (32, "favicon-32.png"), (192, "favicon-192.png")]:
        favicon_src.resize((size, size), Image.Resampling.LANCZOS).save(STATIC / name, optimize=True)

    ico_sizes = [(16, 16), (32, 32), (48, 48)]
    favicon_src.resize((48, 48), Image.Resampling.LANCZOS).save(
        STATIC / "favicon.ico", format="ICO", sizes=ico_sizes
    )
    shutil.copy2(STATIC / "favicon-32.png", STATIC / "favicon.png")

    print("Brand assets written to", STATIC)


if __name__ == "__main__":
    main()
