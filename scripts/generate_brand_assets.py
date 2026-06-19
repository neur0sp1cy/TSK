#!/usr/bin/env python3
"""Generate UI-sized brand images and favicons from web/static/kofi-avatar.png."""

from pathlib import Path
import shutil

try:
    from PIL import Image
except ImportError:
    raise SystemExit("Install Pillow: uv run --with pillow python scripts/generate_brand_assets.py")

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "web" / "static"
AVATAR_SRC = STATIC / "kofi-avatar.png"


def main() -> None:
    if not AVATAR_SRC.is_file():
        raise SystemExit(f"Missing {AVATAR_SRC}")

    avatar = Image.open(AVATAR_SRC).convert("RGBA")
    avatar.resize((128, 128), Image.Resampling.LANCZOS).save(
        STATIC / "kofi-avatar-ui.png", optimize=True
    )

    for size, name in [(16, "favicon-16.png"), (32, "favicon-32.png"), (192, "favicon-192.png")]:
        avatar.resize((size, size), Image.Resampling.LANCZOS).save(STATIC / name, optimize=True)

    ico_sizes = [(16, 16), (32, 32), (48, 48)]
    avatar.resize((16, 16), Image.Resampling.LANCZOS).save(
        STATIC / "favicon.ico", format="ICO", sizes=ico_sizes
    )
    shutil.copy2(STATIC / "favicon-32.png", STATIC / "favicon.png")

    print("Brand assets written to", STATIC)


if __name__ == "__main__":
    main()
