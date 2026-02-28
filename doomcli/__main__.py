"""Doom Mod CLI -- interactive command-line toolkit for Doom WAD files."""

from __future__ import annotations

import os
import sys
import textwrap
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import doomcli
from doomcli.wad import WAD, LumpGroup
from doomcli.wadio import WadIO
from doomcli.lump import Lump, Graphic, Flat, Sound
from doomcli.mapedit import MapEditor
from doomcli.util import OrderedDict


BANNER = r"""
    ___                        __  ___          __   ________    ____
   / _ \ ___   ___   __ _     /  |/  / ___  ___/ /  / ___/ /   /  _/
  / // // _ \ / _ \ /  ' \   / /|_/ / / _ \/ _  /  / /__/ /__ _/ /
 /____/ \___/ \___//_/_/_/  /_/  /_/  \___/\_,_/   \___/____//___/
"""


class CLI:
    """Doom Mod CLI -- interactive session wrapping omgifol operations."""

    def __init__(self):
        self.wad: Optional[WAD] = None
        self.wad_path: Optional[str] = None
        self.running = True

    def run(self):
        print(BANNER)
        print(f"  Doom Mod CLI v{doomcli.__version__} -- powered by omgifol")
        print(f"  Type 'help' for commands, 'quit' to exit.\n")

        while self.running:
            status = f" [{self.wad_path}]" if self.wad_path else ""
            try:
                line = input(f"doomcli{status}> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not line:
                continue

            parts = line.split(None, 1)
            cmd = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""

            handler = {
                "help": self.cmd_help,
                "open": self.cmd_open,
                "new": self.cmd_new,
                "save": self.cmd_save,
                "saveas": self.cmd_saveas,
                "close": self.cmd_close,
                "info": self.cmd_info,
                "lumps": self.cmd_lumps,
                "sections": self.cmd_sections,
                "extract": self.cmd_extract,
                "import": self.cmd_import,
                "remove": self.cmd_remove,
                "rename": self.cmd_rename,
                "merge": self.cmd_merge,
                "maps": self.cmd_maps,
                "mapinfo": self.cmd_mapinfo,
                "sprites": self.cmd_sprites,
                "sprite-import": self.cmd_sprite_import,
                "sprite-export": self.cmd_sprite_export,
                "sounds": self.cmd_sounds,
                "sound-export": self.cmd_sound_export,
                "sound-import": self.cmd_sound_import,
                "textures": self.cmd_textures,
                "palette": self.cmd_palette,
                "colormap": self.cmd_colormap,
                "decorate": self.cmd_decorate,
                "png2wad": self.cmd_png2wad,
                "png2pk3": self.cmd_png2pk3,
                "export-sprites": self.cmd_export_all_sprites,
                "export-sounds": self.cmd_export_all_sounds,
                "export-flats": self.cmd_export_all_flats,
                "quit": self.cmd_quit,
                "exit": self.cmd_quit,
            }.get(cmd)

            if handler:
                try:
                    handler(args)
                except Exception as e:
                    print(f"  Error: {e}\n")
            else:
                print(f"  Unknown command: {cmd!r}. Type 'help' for a list.\n")

    # ------------------------------------------------------------------
    # Help
    # ------------------------------------------------------------------

    def cmd_help(self, args: str):
        print(textwrap.dedent("""
        WAD Operations
          open <path>            Open an existing WAD file
          new                    Create a new empty PWAD in memory
          save                   Save changes to the current WAD
          saveas <path>          Save the WAD to a new file
          close                  Close the current WAD
          merge <path>           Merge another WAD into the current one
          info                   Show WAD file summary

        Lump Management
          sections               List all WAD sections and lump counts
          lumps [section]         List lumps (all or in a specific section)
          extract <name> <file>  Extract a lump to file
          import <name> <file>   Import a file as lump
          remove <name>          Remove a lump
          rename <old> <new>     Rename a lump

        Sprites
          sprites                List all sprites
          sprite-import <file>   Import a PNG as a sprite (interactive)
          sprite-export <name>   Export a sprite to PNG

        Sprite Pipeline
          png2wad                Batch PNG folder -> WAD with DECORATE (interactive)
          png2pk3                Batch PNG folder -> PK3 with DECORATE (interactive)
          decorate               Generate a DECORATE definition (interactive)

        Maps
          maps                   List all maps
          mapinfo <name>         Show map statistics

        Sounds
          sounds                 List all sounds
          sound-export <name>    Export a sound to WAV
          sound-import <file>    Import an audio file as a sound (interactive)

        Batch Export
          export-sprites <dir>   Export all sprites to a directory as PNGs
          export-sounds <dir>    Export all sounds to a directory as WAVs
          export-flats <dir>     Export all flats to a directory as PNGs

        Textures & Palette
          textures               List texture definitions
          palette [file]         Export the palette to a PNG file
          colormap               Show colormap info

        General
          help                   Show this help
          quit / exit            Exit the CLI
        """))

    # ------------------------------------------------------------------
    # WAD I/O
    # ------------------------------------------------------------------

    def cmd_open(self, args: str):
        path = args.strip().strip('"').strip("'")
        if not path:
            path = _prompt("WAD file path: ")
        if not path:
            return
        if not os.path.exists(path):
            print(f"  File not found: {path}\n")
            return
        self.wad = WAD(path)
        self.wad_path = path
        total_lumps = sum(len(g) for g in self.wad.groups)
        print(f"  Opened {path} -- {total_lumps} lumps loaded.\n")

    def cmd_new(self, args: str):
        self.wad = WAD()
        self.wad_path = None
        print("  Created new empty PWAD.\n")

    def cmd_save(self, args: str):
        self._require_wad()
        if not self.wad_path:
            return self.cmd_saveas(args)
        self.wad.to_file(self.wad_path)
        print(f"  Saved to {self.wad_path}\n")

    def cmd_saveas(self, args: str):
        self._require_wad()
        path = args.strip().strip('"').strip("'")
        if not path:
            path = _prompt("Save as: ")
        if not path:
            return
        self.wad.to_file(path)
        self.wad_path = path
        print(f"  Saved to {path}\n")

    def cmd_close(self, args: str):
        self.wad = None
        self.wad_path = None
        print("  WAD closed.\n")

    def cmd_merge(self, args: str):
        self._require_wad()
        path = args.strip().strip('"').strip("'")
        if not path:
            path = _prompt("WAD to merge: ")
        if not path or not os.path.exists(path):
            print(f"  File not found: {path}\n")
            return
        other = WAD(path)
        self.wad = self.wad + other
        total = sum(len(g) for g in self.wad.groups)
        print(f"  Merged {path} -- now {total} total lumps.\n")

    def cmd_info(self, args: str):
        self._require_wad()
        print(f"  File: {self.wad_path or '(unsaved)'}")
        for group in self.wad.groups:
            if len(group) > 0:
                print(f"  {group._name:12s}  {len(group)} lumps")
        print()

    # ------------------------------------------------------------------
    # Lump Management
    # ------------------------------------------------------------------

    def cmd_sections(self, args: str):
        self._require_wad()
        print("  Section         Lumps")
        print("  --------------- -----")
        for group in self.wad.groups:
            print(f"  {group._name:16s} {len(group)}")
        print()

    def cmd_lumps(self, args: str):
        self._require_wad()
        section = args.strip().lower() if args.strip() else None

        if section:
            group = getattr(self.wad, section, None)
            if group is None or not isinstance(group, LumpGroup):
                print(f"  Unknown section: {section}")
                print(f"  Available: {', '.join(g._name for g in self.wad.groups)}\n")
                return
            names = group.keys()
            print(f"  {section} ({len(names)} lumps):")
            for name in names:
                size = len(group[name].data) if hasattr(group[name], 'data') else '?'
                print(f"    {name:10s} {size:>8} bytes")
        else:
            for group in self.wad.groups:
                if len(group) > 0:
                    print(f"\n  [{group._name}] ({len(group)} lumps)")
                    for name in list(group.keys())[:20]:
                        lump = group[name]
                        if hasattr(lump, 'data'):
                            print(f"    {name:10s} {len(lump.data):>8} bytes")
                        else:
                            print(f"    {name:10s} (group)")
                    if len(group) > 20:
                        print(f"    ... and {len(group) - 20} more")
        print()

    def cmd_extract(self, args: str):
        self._require_wad()
        parts = args.split(None, 1)
        if len(parts) < 2:
            name = _prompt("Lump name: ")
            target = _prompt("Output file: ")
        else:
            name, target = parts[0], parts[1].strip().strip('"').strip("'")
        if not name or not target:
            return

        lump = self._find_lump(name.upper())
        if lump is None:
            print(f"  Lump {name.upper()!r} not found.\n")
            return
        lump.to_file(target)
        print(f"  Extracted {name.upper()} -> {target} ({len(lump.data)} bytes)\n")

    def cmd_import(self, args: str):
        self._require_wad()
        parts = args.split(None, 1)
        if len(parts) < 2:
            name = _prompt("Lump name: ")
            source = _prompt("Input file: ")
        else:
            name, source = parts[0], parts[1].strip().strip('"').strip("'")
        if not name or not source:
            return

        name = name.upper()[:8]
        lump = Lump(from_file=source)
        self.wad.data[name] = lump
        print(f"  Imported {source} -> {name} ({len(lump.data)} bytes in 'data' section)\n")

    def cmd_remove(self, args: str):
        self._require_wad()
        name = (args.strip() or _prompt("Lump name: ")).upper()
        if not name:
            return
        for group in self.wad.groups:
            if name in group:
                del group[name]
                print(f"  Removed {name} from {group._name}\n")
                return
        print(f"  Lump {name!r} not found.\n")

    def cmd_rename(self, args: str):
        self._require_wad()
        parts = args.split()
        if len(parts) < 2:
            old = _prompt("Old name: ").upper()
            new = _prompt("New name: ").upper()
        else:
            old, new = parts[0].upper(), parts[1].upper()
        if not old or not new:
            return
        for group in self.wad.groups:
            if old in group:
                group.rename(old, new[:8])
                print(f"  Renamed {old} -> {new[:8]} in {group._name}\n")
                return
        print(f"  Lump {old!r} not found.\n")

    # ------------------------------------------------------------------
    # Sprites
    # ------------------------------------------------------------------

    def cmd_sprites(self, args: str):
        self._require_wad()
        names = self.wad.sprites.keys()
        if not names:
            print("  No sprites in this WAD.\n")
            return
        print(f"  Sprites ({len(names)}):")
        for name in names:
            g = self.wad.sprites[name]
            try:
                w, h = g.dimensions
                ox, oy = g.offsets
                print(f"    {name:10s} {w}x{h}  offset ({ox}, {oy})")
            except Exception:
                print(f"    {name:10s} {len(g.data)} bytes")
        print()

    def cmd_sprite_export(self, args: str):
        self._require_wad()
        name = (args.strip() or _prompt("Sprite name: ")).upper()
        if not name:
            return
        if name not in self.wad.sprites:
            print(f"  Sprite {name!r} not found.\n")
            return
        outfile = _prompt(f"Output file [{name}.png]: ") or f"{name}.png"
        mode = _prompt("Mode (P/RGB/RGBA) [RGBA]: ").upper() or "RGBA"
        self.wad.sprites[name].to_file(outfile, mode=mode)
        print(f"  Exported {name} -> {outfile}\n")

    def cmd_sprite_import(self, args: str):
        self._require_wad()
        source = args.strip().strip('"').strip("'") or _prompt("PNG file: ")
        if not source or not os.path.exists(source):
            print(f"  File not found: {source}\n")
            return
        name = _prompt("Sprite lump name (e.g. PLAYA1): ").upper()
        if not name:
            return
        xoff = _prompt_int("X offset", None)
        yoff = _prompt_int("Y offset", None)
        g = Graphic(from_file=source)
        if xoff is not None and yoff is not None:
            g.offsets = (xoff, yoff)
        elif xoff is not None:
            g.offsets = (xoff, g.y_offset)
        elif yoff is not None:
            g.offsets = (g.x_offset, yoff)
        self.wad.sprites[name] = g
        w, h = g.dimensions
        ox, oy = g.offsets
        print(f"  Imported {source} -> {name} ({w}x{h}, offset {ox},{oy})\n")

    # ------------------------------------------------------------------
    # Sprite Pipeline
    # ------------------------------------------------------------------

    def cmd_png2wad(self, args: str):
        self._run_sprite_pipeline("wad")

    def cmd_png2pk3(self, args: str):
        self._run_sprite_pipeline("pk3")

    def _run_sprite_pipeline(self, fmt: str):
        from doomcli.spritetools import folder_to_wad, folder_to_pk3, parse_states_spec

        print(f"  -- Batch PNG -> {fmt.upper()} Pipeline --\n")
        folder = _prompt("  PNG folder path: ").strip().strip('"').strip("'")
        if not folder or not os.path.isdir(folder):
            print(f"  Not a valid directory: {folder}\n")
            return

        output = _prompt(f"  Output .{fmt} path: ").strip().strip('"').strip("'")
        if not output:
            return

        actor = _prompt("  Actor name (e.g. DoomBezos): ")
        if not actor:
            return

        prefix = _prompt("  Sprite prefix (4 chars, or Enter for auto): ").upper() or None
        doomednum = _prompt_int("  DoomEdNum (or Enter to skip)", None)
        health = _prompt_int("  Health (or Enter to skip)", None)
        radius = _prompt_int("  Radius", 20)
        height = _prompt_int("  Height", 16)

        offset_choices = {"1": "center-bottom", "2": "center", "3": "weapon"}
        print("  Offset mode: [1] center-bottom  [2] center  [3] weapon  [4] custom")
        oc = _prompt("  Choice [1]: ") or "1"
        if oc == "4":
            cx = _prompt_int("    X offset", 0)
            cy = _prompt_int("    Y offset", 0)
            offset_mode: object = (cx, cy)
        else:
            offset_mode = offset_choices.get(oc, "center-bottom")

        naming_choices = {"1": "auto", "2": "explicit", "3": "mirror5"}
        print("  Naming mode: [1] auto  [2] explicit  [3] mirror5")
        nc = _prompt("  Choice [1]: ") or "1"
        naming = naming_choices.get(nc, "auto")

        states_str = _prompt("  States (e.g. Spawn:A-D,Death:E-G or Enter for auto): ")
        states = parse_states_spec(states_str) if states_str else None

        flags_str = _prompt("  Flags [+SOLID,+SHOOTABLE]: ") or "+SOLID,+SHOOTABLE"
        flags = [f.strip() for f in flags_str.split(",") if f.strip()]

        replaces = _prompt("  Replaces actor (or Enter to skip): ") or None
        parent = _prompt("  Parent actor (or Enter to skip): ") or None

        kwargs = dict(
            input_folder=folder,
            actor_name=actor,
            sprite_prefix=prefix,
            doomednum=doomednum,
            offset_mode=offset_mode,
            states=states,
            health=health,
            radius=radius,
            height=height,
            flags=flags,
            replaces=replaces,
            parent=parent,
            naming=naming,
        )

        if fmt == "pk3":
            folder_to_pk3(output_pk3=output, **kwargs)
        else:
            folder_to_wad(output_wad=output, **kwargs)

        pngs = [p for p in Path(folder).iterdir() if p.is_file() and p.suffix.lower() == ".png"]
        print(f"\n  Created {fmt.upper()}: {output}")
        print(f"  Imported {len(pngs)} PNGs with DECORATE for actor {actor!r}\n")

    def cmd_decorate(self, args: str):
        from doomcli.spritetools import generate_decorate, parse_states_spec

        print("  -- DECORATE Generator --\n")
        actor = _prompt("  Actor name: ")
        if not actor:
            return
        prefix = _prompt("  Sprite prefix (4 chars): ").upper()
        if not prefix:
            return
        states_str = _prompt("  States (e.g. Spawn:A-D,Death:E-G): ")
        if not states_str:
            return
        states = parse_states_spec(states_str)
        doomednum = _prompt_int("  DoomEdNum (or Enter to skip)", None)
        health = _prompt_int("  Health (or Enter to skip)", None)
        radius = _prompt_int("  Radius", 20)
        height = _prompt_int("  Height", 16)
        flags_str = _prompt("  Flags [+SOLID,+SHOOTABLE]: ") or "+SOLID,+SHOOTABLE"
        flags = [f.strip() for f in flags_str.split(",") if f.strip()]

        text = generate_decorate(
            actor_name=actor,
            sprite_prefix=prefix,
            states_config=states,
            doomednum=doomednum,
            health=health,
            radius=radius,
            height=height,
            flags=flags,
        )
        print(f"\n{text}")

        save = _prompt("  Save to file? (path or Enter to skip): ")
        if save:
            Path(save).write_text(text, encoding="ascii")
            print(f"  Saved to {save}\n")

    # ------------------------------------------------------------------
    # Maps
    # ------------------------------------------------------------------

    def cmd_maps(self, args: str):
        self._require_wad()
        all_maps = list(self.wad.maps.keys()) + list(self.wad.udmfmaps.keys())
        if not all_maps:
            print("  No maps in this WAD.\n")
            return
        print(f"  Maps ({len(all_maps)}):")
        for name in all_maps:
            print(f"    {name}")
        print()

    def cmd_mapinfo(self, args: str):
        self._require_wad()
        name = (args.strip() or _prompt("Map name: ")).upper()
        if not name:
            return

        lumps = None
        if name in self.wad.maps:
            lumps = self.wad.maps[name]
        elif name in self.wad.udmfmaps:
            lumps = self.wad.udmfmaps[name]
        if lumps is None:
            print(f"  Map {name!r} not found.\n")
            return

        if name in self.wad.udmfmaps:
            print(f"  Map {name} (UDMF format)")
            for lname in lumps.keys():
                if lname == "_HEADER_":
                    continue
                print(f"    {lname:12s} {len(lumps[lname].data):>8} bytes")
            print()
            return

        try:
            ed = MapEditor(lumps)
        except Exception as e:
            print(f"  Could not parse map: {e}\n")
            return

        print(f"  Map: {name}")
        print(f"    Vertices:  {len(ed.vertexes)}")
        print(f"    Linedefs:  {len(ed.linedefs)}")
        print(f"    Sidedefs:  {len(ed.sidedefs)}")
        print(f"    Sectors:   {len(ed.sectors)}")
        print(f"    Things:    {len(ed.things)}")
        print(f"    Segs:      {len(ed.segs)}")
        print(f"    SubSectors:{len(ed.ssectors)}")
        print(f"    Nodes:     {len(ed.nodes)}")
        print()

    # ------------------------------------------------------------------
    # Sounds
    # ------------------------------------------------------------------

    def cmd_sounds(self, args: str):
        self._require_wad()
        names = self.wad.sounds.keys()
        if not names:
            print("  No sounds in this WAD.\n")
            return
        print(f"  Sounds ({len(names)}):")
        for name in names:
            snd = self.wad.sounds[name]
            try:
                fmt = snd.format
                length = snd.length
                rate = snd.sample_rate
                fmtname = {0: "PC Speaker", 1: "MIDI Seq", 2: "MIDI Note", 3: "Digital"}.get(fmt, "?")
                print(f"    {name:10s} fmt={fmtname:10s} len={length:6d} rate={rate}")
            except Exception:
                print(f"    {name:10s} {len(snd.data)} bytes")
        print()

    def cmd_sound_export(self, args: str):
        self._require_wad()
        name = (args.strip() or _prompt("Sound name: ")).upper()
        if not name:
            return
        if name not in self.wad.sounds:
            print(f"  Sound {name!r} not found.\n")
            return
        outfile = _prompt(f"Output file [{name}.wav]: ") or f"{name}.wav"
        self.wad.sounds[name].to_file(outfile)
        print(f"  Exported {name} -> {outfile}\n")

    def cmd_sound_import(self, args: str):
        self._require_wad()
        source = args.strip().strip('"').strip("'") or _prompt("Audio file: ")
        if not source or not os.path.exists(source):
            print(f"  File not found: {source}\n")
            return
        name = _prompt("Sound lump name (e.g. DSPISTOL): ").upper()
        if not name:
            return
        snd = Sound(from_file=source)
        self.wad.sounds[name] = snd
        print(f"  Imported {source} -> {name} (rate={snd.sample_rate}, len={snd.length})\n")

    # ------------------------------------------------------------------
    # Textures
    # ------------------------------------------------------------------

    def cmd_textures(self, args: str):
        self._require_wad()
        if not self.wad.txdefs or len(self.wad.txdefs) == 0:
            print("  No texture definitions in this WAD.\n")
            return
        try:
            from doomcli.txdef import Textures
            tx = Textures(self.wad.txdefs)
            print(f"  Textures ({len(tx)}):")
            for name, tdef in list(tx.items())[:50]:
                print(f"    {name:10s} {tdef.width}x{tdef.height} ({tdef.npatches} patches)")
            if len(tx) > 50:
                print(f"    ... and {len(tx) - 50} more")
        except Exception as e:
            print(f"  Could not parse texture defs: {e}")
        print()

    # ------------------------------------------------------------------
    # Palette & Colormap
    # ------------------------------------------------------------------

    def cmd_palette(self, args: str):
        outfile = args.strip() or "palette.png"
        try:
            from PIL import Image
        except ImportError:
            print("  Pillow is required for palette export.\n")
            return

        pal = doomcli.palette.default
        if self.wad:
            pal = self.wad.palette

        img = Image.new("RGB", (256, 1))
        for i, color in enumerate(pal.colors):
            img.putpixel((i, 0), color)
        img = img.resize((512, 32), Image.NEAREST)
        img.save(outfile)
        print(f"  Palette exported to {outfile}\n")

    def cmd_colormap(self, args: str):
        self._require_wad()
        if "COLORMAP" not in self.wad.data:
            print("  No COLORMAP lump in this WAD.\n")
            return
        from doomcli.colormap import Colormap
        cm = Colormap(from_lump=self.wad.data["COLORMAP"])
        print(f"  COLORMAP: {len(cm.tables)} tables (32 brightness + invuln + unused)")
        print(f"  Table 0 (brightest) sample: {cm.tables[0][:16]}...")
        print(f"  Table 31 (darkest) sample:  {cm.tables[31][:16]}...\n")

    # ------------------------------------------------------------------
    # Batch Export
    # ------------------------------------------------------------------

    def cmd_export_all_sprites(self, args: str):
        self._require_wad()
        from doomcli.wadtools import extract_all_sprites
        outdir = args.strip().strip('"').strip("'") or _prompt("Output directory: ")
        if not outdir:
            return
        written = extract_all_sprites(self.wad, outdir)
        print(f"  Exported {len(written)} sprites to {outdir}\n")

    def cmd_export_all_sounds(self, args: str):
        self._require_wad()
        from doomcli.wadtools import extract_all_sounds
        outdir = args.strip().strip('"').strip("'") or _prompt("Output directory: ")
        if not outdir:
            return
        written = extract_all_sounds(self.wad, outdir)
        print(f"  Exported {len(written)} sounds to {outdir}\n")

    def cmd_export_all_flats(self, args: str):
        self._require_wad()
        from doomcli.wadtools import extract_all_flats
        outdir = args.strip().strip('"').strip("'") or _prompt("Output directory: ")
        if not outdir:
            return
        written = extract_all_flats(self.wad, outdir)
        print(f"  Exported {len(written)} flats to {outdir}\n")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _require_wad(self):
        if self.wad is None:
            raise RuntimeError("No WAD loaded. Use 'open <path>' or 'new' first.")

    def _find_lump(self, name: str) -> Optional[Lump]:
        for group in self.wad.groups:
            if name in group:
                obj = group[name]
                if isinstance(obj, Lump):
                    return obj
        return None

    def cmd_quit(self, args: str):
        self.running = False
        print("  Goodbye.\n")


# ------------------------------------------------------------------
# Input helpers
# ------------------------------------------------------------------

def _prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return ""


def _prompt_int(msg: str, default) -> Optional[int]:
    raw = _prompt(f"  {msg} [{default}]: " if default is not None else f"  {msg}: ")
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def main():
    cli = CLI()
    cli.run()


if __name__ == "__main__":
    main()
