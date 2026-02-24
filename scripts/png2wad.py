#!/usr/bin/env python

from __future__ import annotations

import sys
from pathlib import Path

# Add project root so "omg" is importable when run from repo
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
from typing import Dict, List, Optional, Tuple, Union

from omg.spritetools import folder_to_wad, parse_states_spec


def parse_custom_offset(value: str) -> Tuple[int, int]:
    try:
        x_str, y_str = value.split(",", 1)
        return int(x_str.strip()), int(y_str.strip())
    except Exception as exc:
        raise argparse.ArgumentTypeError("custom offset must be formatted as 'x,y'") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert a folder of PNG sprites into a playable Doom PWAD with DECORATE."
    )
    parser.add_argument("input_folder", help="Folder containing PNG sprite files")
    parser.add_argument("-o", "--output", required=True, help="Output PWAD path")
    parser.add_argument("--actor", required=True, help="DECORATE actor class name")
    parser.add_argument("--prefix", help="4-char sprite prefix (defaults from actor name)")
    parser.add_argument("--doomednum", type=int, help="DoomEdNum for map placement")
    parser.add_argument("--health", type=int, help="Actor health")
    parser.add_argument("--radius", type=int, default=20, help="Actor radius (default: 20)")
    parser.add_argument("--height", type=int, default=16, help="Actor height (default: 16)")
    parser.add_argument(
        "--offset",
        choices=("center-bottom", "center", "weapon", "custom"),
        default="center-bottom",
        help="Offset mode (default: center-bottom)",
    )
    parser.add_argument(
        "--offset-custom",
        type=parse_custom_offset,
        help="Custom offsets if --offset=custom, in form x,y",
    )
    parser.add_argument(
        "--states",
        help="State mapping, e.g. idle:A-D,walk:E-H,attack:I-K,death:L-P",
    )
    parser.add_argument(
        "--flags",
        default="+SOLID,+SHOOTABLE",
        help="Comma-separated DECORATE flags (default: +SOLID,+SHOOTABLE)",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    input_folder = Path(args.input_folder)
    if not input_folder.exists() or not input_folder.is_dir():
        parser.error(f"Input folder does not exist or is not a directory: {input_folder}")

    offset_mode: Union[str, Tuple[int, int]] = args.offset
    if args.offset == "custom":
        if args.offset_custom is None:
            parser.error("--offset-custom is required when --offset=custom")
        offset_mode = args.offset_custom

    states: Optional[Dict[str, List[str]]] = None
    if args.states:
        states = parse_states_spec(args.states)

    flags = [f.strip() for f in args.flags.split(",") if f.strip()]

    folder_to_wad(
        input_folder=input_folder,
        output_wad=args.output,
        actor_name=args.actor,
        sprite_prefix=args.prefix,
        doomednum=args.doomednum,
        offset_mode=offset_mode,
        states=states,
        health=args.health,
        radius=args.radius,
        height=args.height,
        flags=flags,
    )

    png_count = len([p for p in input_folder.iterdir() if p.is_file() and p.suffix.lower() == ".png"])
    print(f"Created WAD: {args.output}")
    print(f"Imported PNGs: {png_count}")
    print("Added lump: DECORATE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
