from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import zipfile
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

from doomcli.lump import Graphic, Lump
from doomcli.wad import WAD
from doomcli.util import OrderedDict, safe_name


_EXPLICIT_SPRITE_RE = re.compile(
    r"^(?P<prefix>[A-Z0-9]{4})(?P<frame1>[A-Z])(?P<rot1>[0-8])(?:(?P<frame2>[A-Z])(?P<rot2>[0-8]))?$"
)


def _normalize_prefix(prefix: str) -> str:
    cleaned = "".join(ch for ch in prefix.upper() if ch.isalnum())
    cleaned = (cleaned + "XXXX")[:4]
    return cleaned


def _auto_prefix_from_actor(actor_name: str) -> str:
    return _normalize_prefix(actor_name)


def _frame_for_index(index: int) -> str:
    # Doom frame letters are A-Z. For >26, continue as A..Z in wrapped loops.
    return chr(ord("A") + (index % 26))


def _mirror5_lump_name(prefix: str, frame_letter: str, rotation: int) -> str:
    frame_letter = frame_letter.upper()
    if rotation == 1:
        return f"{prefix}{frame_letter}1"
    if rotation == 2:
        return f"{prefix}{frame_letter}2{frame_letter}8"
    if rotation == 3:
        return f"{prefix}{frame_letter}3{frame_letter}7"
    if rotation == 4:
        return f"{prefix}{frame_letter}4{frame_letter}6"
    if rotation == 5:
        return f"{prefix}{frame_letter}5"
    raise ValueError("mirror5 rotation must be in range 1..5")


def parse_frame_range(spec: str) -> List[str]:
    part = spec.strip().upper()
    if "-" in part:
        start, end = [p.strip() for p in part.split("-", 1)]
        if len(start) != 1 or len(end) != 1:
            raise ValueError(f"Invalid frame range: {spec!r}")
        a, b = ord(start), ord(end)
        step = 1 if a <= b else -1
        return [chr(i) for i in range(a, b + step, step)]
    if len(part) != 1:
        raise ValueError(f"Invalid frame token: {spec!r}")
    return [part]


def parse_states_spec(states_spec: str) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for chunk in states_spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ":" not in chunk:
            raise ValueError(f"Invalid state spec segment: {chunk!r}")
        state_name, frame_spec = [x.strip() for x in chunk.split(":", 1)]
        out[state_name] = parse_frame_range(frame_spec)
    return out


@dataclass
class SpriteFrame:
    lump_name: str
    frame_letter: str
    rotation: int
    image_path: Path
    graphic: Graphic


class SpriteSheet:
    """Manages sprite frames for a single actor prefix."""

    def __init__(self, prefix: str, palette=None):
        self.prefix = _normalize_prefix(prefix)
        self.palette = palette
        self.frames: List[SpriteFrame] = []

    def add_frame(
        self,
        frame_letter: str,
        rotation: int,
        image_path: Union[str, Path],
        x_offset: Optional[int] = None,
        y_offset: Optional[int] = None,
        lump_name: Optional[str] = None,
    ) -> SpriteFrame:
        image_path = Path(image_path)
        frame_letter = frame_letter.upper()
        if len(frame_letter) != 1 or not frame_letter.isalpha():
            raise ValueError("frame_letter must be one A-Z character")
        if rotation < 0 or rotation > 8:
            raise ValueError("rotation must be in range 0..8")

        name = lump_name or f"{self.prefix}{frame_letter}{rotation}"
        name = safe_name(name)
        graphic = Graphic(from_file=str(image_path), palette=self.palette)
        if x_offset is not None or y_offset is not None:
            ox = x_offset if x_offset is not None else graphic.x_offset
            oy = y_offset if y_offset is not None else graphic.y_offset
            graphic.offsets = (ox, oy)

        frame = SpriteFrame(
            lump_name=name,
            frame_letter=frame_letter,
            rotation=rotation,
            image_path=image_path,
            graphic=graphic,
        )
        self.frames.append(frame)
        return frame

    def add_frames_from_folder(self, folder: Union[str, Path], naming: str = "auto") -> List[SpriteFrame]:
        folder = Path(folder)
        pngs = sorted(
            [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".png"],
            key=lambda p: p.name.lower(),
        )
        if not pngs:
            raise ValueError(f"No PNG files found in {folder}")

        added: List[SpriteFrame] = []
        if naming == "mirror5":
            if len(pngs) % 5 != 0:
                raise ValueError(
                    "mirror5 naming requires PNG count to be a multiple of 5 "
                    "(per frame: rotations 1,2,3,4,5 mirrored to 8,7,6)."
                )
            for i in range(0, len(pngs), 5):
                frame_letter = _frame_for_index(i // 5)
                group = pngs[i : i + 5]
                for rot, image in enumerate(group, start=1):
                    lump_name = _mirror5_lump_name(self.prefix, frame_letter, rot)
                    added.append(
                        self.add_frame(
                            frame_letter=frame_letter,
                            rotation=rot,
                            image_path=image,
                            lump_name=lump_name,
                        )
                    )
            return added

        for i, image in enumerate(pngs):
            stem = image.stem.upper()
            match = _EXPLICIT_SPRITE_RE.match(stem)

            if naming == "explicit" and not match:
                raise ValueError(f"Expected explicit Doom sprite name for {image.name}")

            if naming in ("auto", "explicit") and match:
                lump_name = match.group(0)
                frame_letter = match.group("frame1")
                rotation = int(match.group("rot1"))
                added.append(
                    self.add_frame(
                        frame_letter=frame_letter,
                        rotation=rotation,
                        image_path=image,
                        lump_name=lump_name,
                    )
                )
                continue

            # Pattern-based and sequential both resolve into sorted A-Z assignment.
            frame_letter = _frame_for_index(i)
            added.append(self.add_frame(frame_letter=frame_letter, rotation=0, image_path=image))

        return added

    def auto_offset(self, mode: Union[str, Tuple[int, int]] = "center-bottom") -> None:
        for frame in self.frames:
            offsets = _compute_offsets(frame.graphic.width, frame.graphic.height, mode)
            frame.graphic.offsets = offsets

    def to_wad_sprites(self) -> Dict[str, Graphic]:
        sprites = OrderedDict()
        for frame in self.frames:
            sprites[frame.lump_name] = frame.graphic
        return sprites


def _default_states_from_frames(frames: Sequence[SpriteFrame]) -> Dict[str, List[str]]:
    ordered = []
    seen = set()
    for frame in frames:
        if frame.frame_letter not in seen:
            ordered.append(frame.frame_letter)
            seen.add(frame.frame_letter)
    return {"Spawn": ordered}


def _compute_offsets(
    width: int,
    height: int,
    mode: Union[str, Tuple[int, int]] = "center-bottom",
) -> Tuple[int, int]:
    if isinstance(mode, tuple):
        return mode
    if mode == "center-bottom":
        return ((width // 2) - 1, height - 5)
    if mode == "center":
        return ((width // 2) - 1, (height // 2) - 1)
    if mode == "weapon":
        return (160, 200 - height)
    raise ValueError(f"Unknown offset mode: {mode}")


def generate_decorate(
    actor_name: str,
    sprite_prefix: str,
    states_config: Dict[str, List[str]],
    doomednum: Optional[int] = None,
    health: Optional[int] = None,
    radius: int = 20,
    height: int = 16,
    flags: Optional[Sequence[str]] = None,
    replaces: Optional[str] = None,
    parent: Optional[str] = None,
    frame_offsets: Optional[Dict[str, Tuple[int, int]]] = None,
) -> str:
    sprite_prefix = _normalize_prefix(sprite_prefix)
    flags = list(flags or ["+SOLID", "+SHOOTABLE"])
    actor_header = f"ACTOR {actor_name}"
    if parent:
        actor_header += f" : {parent}"
    if replaces:
        actor_header += f" replaces {replaces}"
    if doomednum is not None:
        actor_header += f" {doomednum}"

    lines: List[str] = [actor_header, "{"]
    if health is not None:
        lines.append(f"  Health {health}")
    lines.append(f"  Radius {radius}")
    lines.append(f"  Height {height}")
    for flag in flags:
        if flag:
            lines.append(f"  {flag}")

    lines.append("  States")
    lines.append("  {")
    for state_name, frames in states_config.items():
        if not frames:
            continue
        lines.append(f"  {state_name}:")
        for frame in frames:
            frame_key = frame.upper()
            offset_text = ""
            if frame_offsets and frame_key in frame_offsets:
                ox, oy = frame_offsets[frame_key]
                offset_text = f" Offset({ox}, {oy})"
            lines.append(f"    {sprite_prefix} {frame_key} 4{offset_text}")
        if state_name.lower() in {"death", "xdeath"}:
            lines.append("    Stop")
        else:
            lines.append("    Loop")
    lines.append("  }")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def folder_to_wad(
    input_folder: Union[str, Path],
    output_wad: Union[str, Path],
    actor_name: str,
    sprite_prefix: Optional[str] = None,
    doomednum: Optional[int] = None,
    offset_mode: Union[str, Tuple[int, int]] = "center-bottom",
    states: Optional[Dict[str, List[str]]] = None,
    health: Optional[int] = None,
    radius: int = 20,
    height: int = 16,
    flags: Optional[Sequence[str]] = None,
    replaces: Optional[str] = None,
    parent: Optional[str] = None,
    naming: str = "auto",
) -> None:
    prefix = _normalize_prefix(sprite_prefix or _auto_prefix_from_actor(actor_name))
    sheet = SpriteSheet(prefix=prefix)
    sheet.add_frames_from_folder(input_folder, naming=naming)
    sheet.auto_offset(offset_mode)

    states_config = states or _default_states_from_frames(sheet.frames)
    decorate_text = generate_decorate(
        actor_name=actor_name,
        sprite_prefix=prefix,
        states_config=states_config,
        doomednum=doomednum,
        health=health,
        radius=radius,
        height=height,
        flags=flags,
        replaces=replaces,
        parent=parent,
    )

    wad = WAD()
    for lump_name, graphic in sheet.to_wad_sprites().items():
        wad.sprites[lump_name] = graphic
    wad.data["DECORATE"] = Lump(data=decorate_text.encode("ascii"))
    wad.to_file(str(output_wad))


def folder_to_pk3(
    input_folder: Union[str, Path],
    output_pk3: Union[str, Path],
    actor_name: str,
    sprite_prefix: Optional[str] = None,
    doomednum: Optional[int] = None,
    offset_mode: Union[str, Tuple[int, int]] = "center-bottom",
    states: Optional[Dict[str, List[str]]] = None,
    health: Optional[int] = None,
    radius: int = 20,
    height: int = 16,
    flags: Optional[Sequence[str]] = None,
    replaces: Optional[str] = None,
    parent: Optional[str] = None,
    naming: str = "auto",
) -> None:
    prefix = _normalize_prefix(sprite_prefix or _auto_prefix_from_actor(actor_name))
    sheet = SpriteSheet(prefix=prefix)
    sheet.add_frames_from_folder(input_folder, naming=naming)
    sheet.auto_offset(offset_mode)

    states_config = states or _default_states_from_frames(sheet.frames)
    try:
        from PIL import Image
    except ImportError as exc:
        raise ImportError("folder_to_pk3 requires Pillow to read PNG dimensions") from exc

    frame_offsets: Dict[str, Tuple[int, int]] = {}
    for frame in sheet.frames:
        with Image.open(frame.image_path) as img:
            width, height_px = img.size
        frame_offsets.setdefault(
            frame.frame_letter.upper(),
            _compute_offsets(width, height_px, offset_mode),
        )

    decorate_text = generate_decorate(
        actor_name=actor_name,
        sprite_prefix=prefix,
        states_config=states_config,
        doomednum=doomednum,
        health=health,
        radius=radius,
        height=height,
        flags=flags,
        replaces=replaces,
        parent=parent,
        frame_offsets=frame_offsets,
    )

    output_path = Path(output_pk3)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for frame in sheet.frames:
            zf.write(frame.image_path, arcname=f"sprites/{frame.lump_name}.png")
        zf.writestr("DECORATE", decorate_text.encode("ascii"))
