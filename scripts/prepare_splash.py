"""Prepare the supplied PT2VHF splash for all release packages (offline).

Usage:
    python scripts/prepare_splash.py path/to/user-banner.png

Produces pt2vhf/assets/branding/welcome-banner.jpg, 1200 pixels wide,
without cropping. Requires Pillow only to prepare the release source asset.
"""
from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "pt2vhf" / "assets" / "branding" / "welcome-banner.jpg"


def prepare(source: Path, destination: Path = TARGET) -> Path:
    from PIL import Image, ImageOps
    source = Path(source)
    if not source.is_file():
        raise FileNotFoundError(f"Supplied PT2VHF banner not found: {source}")
    with Image.open(source) as raw:
        picture = ImageOps.exif_transpose(raw).convert("RGB")
        target_width = 1200
        target_height = round(picture.height * target_width / picture.width)
        picture = picture.resize((target_width, target_height), Image.Resampling.LANCZOS)
        destination.parent.mkdir(parents=True, exist_ok=True)
        picture.save(destination, "JPEG", quality=82, optimize=True, progressive=True)
    if destination.stat().st_size < 25_000:
        raise ValueError("Suspiciously small PT2VHF banner")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, default=TARGET)
    args = parser.parse_args()
    print(prepare(args.source, args.output))
