#!/usr/bin/env python
"""
Analyze PNG images for technical details (bit depth, color type, alpha, etc.).
Use before/after remove_bg to compare and debug color issues.
"""

from __future__ import annotations

import argparse
import json
import shutil
import struct
import subprocess
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    Image = None


def read_png_ihdr(path: Path) -> dict | None:
    """Read PNG IHDR chunk: width, height, bit_depth, color_type."""
    with open(path, "rb") as f:
        if f.read(8) != b"\x89PNG\r\n\x1a\n":
            return None
        h = f.read(8)
        length, ctype = struct.unpack(">I4s", h)
        if ctype != b"IHDR" or length != 13:
            return None
        data = f.read(13)
        w, h, bd, ct, comp, fil, inter = struct.unpack(">IIBBBBB", data)
        return {"width": w, "height": h, "bit_depth": bd, "color_type": ct}


def pil_analysis(path: Path) -> dict:
    """PIL-based analysis."""
    if Image is None:
        return {"error": "Pillow not installed"}
    with Image.open(path) as img:
        px = img.load()
        w, h = img.size
        center = px[w // 2, h // 2]
        corners = [
            px[0, 0],
            px[w - 1, 0],
            px[0, h - 1],
            px[w - 1, h - 1],
        ]
        icc = img.info.get("icc_profile")
        return {
            "mode": img.mode,
            "size": [w, h],
            "center_pixel": list(center),
            "corner_pixels": [list(c) for c in corners],
            "icc_profile_bytes": len(icc) if icc else 0,
            "info": {k: v for k, v in img.info.items() if k != "icc_profile"},
        }


def ffprobe_analysis(path: Path, ffprobe_path: str | None = None) -> dict | None:
    """Run ffprobe and return stream/format info. Uses shutil.which to resolve path."""
    exe = ffprobe_path or shutil.which("ffprobe")
    if not exe:
        return {"ffprobe": "not found in PATH"}
    try:
        out = subprocess.run(
            [exe, "-v", "error", "-show_streams", "-show_format", "-print_format", "json", str(path)],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if out.returncode != 0:
            return {"ffprobe_error": out.stderr or "unknown"}
        return json.loads(out.stdout)
    except FileNotFoundError:
        return {"ffprobe": "not installed"}
    except Exception as e:
        return {"ffprobe_error": str(e)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze PNG images for technical details.")
    parser.add_argument("paths", nargs="+", help="Image paths to analyze")
    parser.add_argument("--ffprobe", action="store_true", help="Include ffprobe output")
    parser.add_argument("--ffprobe-path", help="Path to ffprobe executable (default: resolve from PATH)")
    args = parser.parse_args()

    for p in args.paths:
        path = Path(p)
        if not path.exists():
            print(f"Not found: {path}\n")
            continue
        print(f"=== {path} ===")
        ihdr = read_png_ihdr(path)
        if ihdr:
            print(f"IHDR: {ihdr['width']}x{ihdr['height']}, bit_depth={ihdr['bit_depth']}, color_type={ihdr['color_type']} (6=RGBA)")
        pil = pil_analysis(path)
        print(f"PIL: mode={pil.get('mode')}, size={pil.get('size')}")
        print(f"     center_pixel={pil.get('center_pixel')}")
        print(f"     icc_profile={pil.get('icc_profile_bytes', 0)} bytes")
        if args.ffprobe:
            fp = ffprobe_analysis(path, ffprobe_path=args.ffprobe_path)
            if fp and "streams" in fp:
                s = fp["streams"][0]
                print(f"ffprobe: pix_fmt={s.get('pix_fmt')}, color_range={s.get('color_range')}, color_space={s.get('color_space')}")
            elif fp and ("ffprobe_error" in fp or "ffprobe" in fp):
                print(f"ffprobe: {fp.get('ffprobe_error', fp.get('ffprobe', 'error'))}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
