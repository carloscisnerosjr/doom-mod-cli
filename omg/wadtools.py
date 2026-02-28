"""High-level convenience functions for common WAD operations."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

from omg.wad import WAD, LumpGroup
from omg.lump import Graphic, Flat, Lump, Sound
from omg.mapedit import MapEditor


def wad_summary(wad: WAD) -> Dict[str, int]:
    """Return a dict mapping section names to their lump counts."""
    return {g._name: len(g) for g in wad.groups}


def list_sprites(wad: WAD) -> List[Dict[str, object]]:
    """Return a list of dicts with sprite name, dimensions, and offsets."""
    result = []
    for name in wad.sprites.keys():
        g = wad.sprites[name]
        try:
            w, h = g.dimensions
            ox, oy = g.offsets
            result.append({"name": name, "width": w, "height": h, "x_offset": ox, "y_offset": oy})
        except Exception:
            result.append({"name": name, "size": len(g.data)})
    return result


def list_maps(wad: WAD) -> List[str]:
    """Return a combined list of all map names (standard + UDMF)."""
    return list(wad.maps.keys()) + list(wad.udmfmaps.keys())


def map_stats(wad: WAD, map_name: str) -> Optional[Dict[str, int]]:
    """Return a dict of map statistics (vertex/linedef/sector/thing counts)."""
    lumps = None
    if map_name in wad.maps:
        lumps = wad.maps[map_name]
    elif map_name in wad.udmfmaps:
        lumps = wad.udmfmaps[map_name]
    if lumps is None:
        return None

    try:
        ed = MapEditor(lumps)
    except Exception:
        return None

    return {
        "vertexes": len(ed.vertexes),
        "linedefs": len(ed.linedefs),
        "sidedefs": len(ed.sidedefs),
        "sectors": len(ed.sectors),
        "things": len(ed.things),
        "segs": len(ed.segs),
        "subsectors": len(ed.ssectors),
        "nodes": len(ed.nodes),
    }


def extract_all_sprites(wad: WAD, output_dir: Union[str, Path], mode: str = "RGBA") -> List[str]:
    """Export every sprite from a WAD to PNG files in the given directory.

    Returns a list of file paths written.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name in wad.sprites.keys():
        outpath = output_dir / f"{name}.png"
        wad.sprites[name].to_file(str(outpath), mode=mode)
        written.append(str(outpath))
    return written


def extract_all_sounds(wad: WAD, output_dir: Union[str, Path], fmt: str = "wav") -> List[str]:
    """Export every sound from a WAD to audio files in the given directory.

    Returns a list of file paths written.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name in wad.sounds.keys():
        snd = wad.sounds[name]
        try:
            if snd.format == 3:
                outpath = output_dir / f"{name}.{fmt}"
                snd.to_file(str(outpath))
                written.append(str(outpath))
        except Exception:
            pass
    return written


def extract_all_flats(wad: WAD, output_dir: Union[str, Path], mode: str = "P") -> List[str]:
    """Export every flat from a WAD to PNG files in the given directory.

    Returns a list of file paths written.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name in wad.flats.keys():
        outpath = output_dir / f"{name}.png"
        wad.flats[name].to_file(str(outpath), mode=mode)
        written.append(str(outpath))
    return written


def import_sprites_from_dir(
    wad: WAD,
    sprite_dir: Union[str, Path],
    translate: bool = False,
) -> List[str]:
    """Import all PNG files from a directory as sprites into the WAD.

    File stems (without extension) become the lump names (uppercased, max 8 chars).
    Returns a list of imported lump names.
    """
    sprite_dir = Path(sprite_dir)
    imported = []
    for png in sorted(sprite_dir.glob("*.png")):
        name = png.stem.upper()[:8]
        g = Graphic(from_file=str(png))
        wad.sprites[name] = g
        imported.append(name)
    return imported


def merge_wads(*paths: str) -> WAD:
    """Merge multiple WAD files into a single WAD.

    Usage: merged = merge_wads("base.wad", "extra.wad", "more.wad")
    """
    if not paths:
        raise ValueError("At least one WAD path required")
    result = WAD(paths[0])
    for path in paths[1:]:
        result = result + WAD(path)
    return result


def replace_thing_type(wad: WAD, map_name: str, old_type: int, new_type: int) -> int:
    """Replace all things of one type with another in a map.

    Returns the number of things replaced.
    """
    lumps = wad.maps.get(map_name) or wad.udmfmaps.get(map_name)
    if lumps is None:
        raise KeyError(f"Map {map_name!r} not found")

    ed = MapEditor(lumps)
    count = 0
    for thing in ed.things:
        if thing.type == old_type:
            thing.type = new_type
            count += 1
    wad.maps[map_name] = ed.to_lumps()
    return count
