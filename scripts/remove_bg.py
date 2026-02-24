#!/usr/bin/env python
"""
Remove image backgrounds and output transparent PNGs using rembg.

Install: pip install rembg pillow
"""

from __future__ import annotations

import argparse
import io
import shutil
from pathlib import Path

try:
    from PIL import Image
    import numpy as np
except ImportError:
    Image = None
    np = None
try:
    from rembg import remove as rembg_remove
except ImportError:
    rembg_remove = None


def unpremultiply_alpha(img: "Image.Image") -> "Image.Image":
    """
    Convert premultiplied alpha to straight (unassociated) alpha.
    rembg outputs premultiplied alpha; GZDoom and most image software expect straight alpha.
    """
    if np is None:
        return img  # no numpy, skip
    arr = np.array(img, dtype=np.float64)
    r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]
    with np.errstate(divide="ignore", invalid="ignore"):
        scale = np.where(a > 0, 255.0 / a, 1.0)
        arr[:, :, 0] = np.clip(r * scale, 0, 255)
        arr[:, :, 1] = np.clip(g * scale, 0, 255)
        arr[:, :, 2] = np.clip(b * scale, 0, 255)
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


def analyze_image(path: Path) -> dict:
    """Gather technical details about an image for before/after comparison."""
    if Image is None:
        return {}
    with Image.open(path) as img:
        px = img.load()
        w, h = img.size
        center = px[min(w // 2, w - 1), min(h // 2, h - 1)]
        return {
            "path": str(path),
            "mode": img.mode,
            "size": (w, h),
            "center_pixel": list(center),
            "icc_profile": len(img.info.get("icc_profile") or b""),
        }


def parse_size(value: str) -> tuple[int, int]:
    """Parse WxH string into (width, height)."""
    try:
        w, h = value.lower().split("x", 1)
        return int(w.strip()), int(h.strip())
    except (ValueError, AttributeError) as e:
        raise argparse.ArgumentTypeError("Size must be WxH (e.g. 65x65)") from e


def remove_background(
    input_path: Path,
    output_path: Path,
    resize: tuple[int, int] | None = None,
    unpremultiply: bool = False,
    resample: str = "nearest",
) -> None:
    """Remove background from image and save as 8-bit RGBA PNG (GZDoom compatible)."""
    if rembg_remove is None:
        raise ImportError("rembg is required. Install with: pip install rembg pillow")
    if Image is None:
        raise ImportError("Pillow is required. Install with: pip install pillow")

    with open(input_path, "rb") as f:
        img_data = f.read()

    output_data = rembg_remove(img_data)

    # Convert to 8-bit RGBA for GZDoom compatibility (rembg may output 16-bit)
    img = Image.open(io.BytesIO(output_data))
    img = img.convert("RGBA")
    if resize:
        resampler = Image.NEAREST if resample.lower() == "nearest" else getattr(Image, "Resampling", Image).LANCZOS
        img = img.resize(resize, resampler)
    if unpremultiply:
        img = unpremultiply_alpha(img)
    img.save(output_path, "PNG")

    # Verify resize
    if resize:
        with Image.open(output_path) as check:
            actual = check.size
        if actual != resize:
            raise RuntimeError(
                f"Resize verification failed: expected {resize[0]}x{resize[1]}, got {actual[0]}x{actual[1]}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Remove backgrounds from images, leaving transparent PNGs with the subject."
    )
    parser.add_argument(
        "input",
        help="Input image file or folder containing images",
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file or folder. Default: write next to input with _nobg suffix",
    )
    parser.add_argument(
        "--suffix",
        default="_nobg",
        help="Suffix for output filenames when processing folders (default: _nobg)",
    )
    parser.add_argument(
        "--resize",
        type=parse_size,
        default="65x65",
        help="Resize output to WxH pixels (default: 65x65)",
    )
    parser.add_argument(
        "--source-dir",
        default="source_img",
        help="Folder to copy original images to, renamed by Doom name (default: source_img)",
    )
    parser.add_argument(
        "--name",
        help="Doom sprite name for output (e.g. TESTA0). Required for single file; for folder, derived from input stem.",
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Run image analysis before and after, print comparison report",
    )
    parser.add_argument(
        "--unpremultiply",
        action="store_true",
        help="Apply unpremultiply alpha (only if rembg outputs premultiplied alpha; can blow out colors if not)",
    )
    parser.add_argument(
        "--resample",
        choices=("nearest", "lanczos"),
        default="nearest",
        help="Resize method: nearest (pixelated, good for Doom sprites) or lanczos (smooth)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        parser.error(f"Input does not exist: {input_path}")

    if rembg_remove is None:
        print("Error: rembg is not installed.")
        print("Install with: pip install rembg pillow")
        return 1

    supported = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    source_dir = Path(args.source_dir)

    if input_path.is_file():
        if input_path.suffix.lower() not in supported:
            parser.error(f"Unsupported format: {input_path.suffix}")
        if not args.name:
            parser.error("--name is required for single file (e.g. --name TESTA0)")
        doom_name = args.name.upper()[:8].replace(" ", "")
        if not doom_name.endswith(".png"):
            doom_name = doom_name + ".png"

        source_dir.mkdir(parents=True, exist_ok=True)
        source_copy = source_dir / doom_name
        shutil.copy2(input_path, source_copy)
        print(f"Copied source to {source_copy}")

        out_dir = Path(args.output) if args.output else Path(".")
        if out_dir.suffix.lower() == ".png":
            out = out_dir
            out.parent.mkdir(parents=True, exist_ok=True)
        else:
            out_dir = out_dir if out_dir.is_dir() else out_dir
            out_dir.mkdir(parents=True, exist_ok=True)
            out = out_dir / doom_name
        if args.analyze:
            before = analyze_image(input_path)
            print(f"BEFORE: {before}")
        print(f"Processing {input_path.name} -> {out.name}")
        remove_background(
            input_path, out,
            resize=args.resize,
            unpremultiply=args.unpremultiply,
            resample=args.resample,
        )
        if args.analyze:
            after = analyze_image(out)
            print(f"AFTER:  {after}")
            print(f"Diff:   center_pixel {before.get('center_pixel')} -> {after.get('center_pixel')}")
        w, h = args.resize
        print(f"Verified: output is {w}x{h}")
    else:
        files = sorted(
            [p for p in input_path.iterdir() if p.is_file() and p.suffix.lower() in supported],
            key=lambda p: p.name.lower(),
        )
        if not files:
            parser.error(f"No supported images in folder: {input_path}")
        out_dir = Path(args.output) if args.output else input_path / "nobg"
        out_dir.mkdir(parents=True, exist_ok=True)
        source_dir.mkdir(parents=True, exist_ok=True)
        for i, f in enumerate(files):
            doom_name = f.stem.upper()[:8].replace(" ", "") + ".png"
            source_copy = source_dir / doom_name
            shutil.copy2(f, source_copy)
            out = out_dir / doom_name
            if args.analyze:
                before = analyze_image(f)
                print(f"BEFORE [{f.name}]: {before}")
            print(f"[{i+1}/{len(files)}] {f.name} -> source: {source_copy.name}, output: {out.name}")
            remove_background(
                f, out,
                resize=args.resize,
                unpremultiply=args.unpremultiply,
                resample=args.resample,
            )
            if args.analyze:
                after = analyze_image(out)
                print(f"AFTER:  {after} | center: {before.get('center_pixel')} -> {after.get('center_pixel')}")
        w, h = args.resize
        print(f"Saved {len(files)} images to {out_dir}")
        print(f"Source copies in {source_dir}")
        print(f"Verified: all outputs are {w}x{h}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
