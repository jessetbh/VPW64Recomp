#!/usr/bin/env python3
"""Generate N64Recomp symbol TOML (syms/dump.toml) from splat output — VPW64.

Same approach as WM2000/Revenge's generator (symbol-TOML mode; spimdisasm emits
`nonmatching <name>, <size>` + per-instruction `/* ROM VRAM WORD */` comments).
One [[section]] per asm file; overlays are ordinary sections (librecomp tracks
their loads by rom address).

RENAME transfers libultra knowledge. VPW64 (Dec 1997) is WORLD TOUR's direct
sibling — same era, likely the SAME libultra generation, so fingerprint the
fixed segment against WT FIRST (adapt WM2000's tools/recon2.py, which matched
Revenge->WM2000 27/39; WT->Revenge did NOT transfer because the generations
differed — WT->VPW64 should). Evidence method per function: WT's
disasm/libultra.md. The map below is EMPTY until recon fills it — the WM2000
addresses it used to hold are meaningless here (see the sister's
tools/gen_symbols.py for the worked example, including the boot-crash-loop
identifications: osCreatePiManager/osCartRomInit/osDriveRomInit/
osAiSetNextBuffer/osDestroyThread and the osViGet*Framebuffer adjacency pair).
Input invariant from BOTH sisters: rename ONLY osContInit + __osSiRawStartDma +
__osSiDeviceBusy; do NOT rename osContStartReadData (kills the raw-SI path).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASM = ROOT / "disasm" / "asm"
OUT = ROOT / "syms" / "dump.toml"

RENAME = {
    # host-collision rename, same as WT/Revenge/WM2000 (splat leaves the entry
    # target unnamed; the entry stub at rom 0x1000 jr's to it — find game_main's
    # address during recon, expected 0x80000460 per the AKI family pattern):
    "main": "game_main",
    # TODO(recon): fill from WT fingerprint transfer + crash-loop identification.
}

# Extra function entry points injected into dump.toml that splat cannot express:
# j-referenced entries living INSIDE another sized function (IDO multi-entry
# shared-tail clusters; Revenge's EXTRA_FUNCS mechanism). N64Recomp recompiles each
# independently from ROM bytes, so the overlap just duplicates a little code.
# Populated automatically by tools/recomp_loop.py from N64Recomp "Unhandled branch"
# errors, one "section name vram size" line per entry in syms/extra_funcs.txt.
EXTRA_FUNCS = {}
_extra_file = Path(__file__).resolve().parent.parent / "syms" / "extra_funcs.txt"
if _extra_file.exists():
    for l in open(_extra_file):
        parts = l.split()
        if len(parts) == 4:
            EXTRA_FUNCS.setdefault(parts[0], []).append(
                (parts[1], int(parts[2], 16), int(parts[3], 16)))

# Functions suppressed as symbols (continuation fragments merged into an earlier
# function).
SKIP = set()
_skip_file = ROOT / "syms" / "skip_functions.txt"
if _skip_file.exists():
    SKIP = {l.strip() for l in open(_skip_file) if l.strip()}

FUNC_RE = re.compile(r"^nonmatching (\S+), (0x[0-9A-Fa-f]+)")
GLABEL_RE = re.compile(r"^glabel (\S+)")
INSN_RE = re.compile(r"^\s*/\* ([0-9A-Fa-f]+) ([0-9A-Fa-f]{8}) ([0-9A-Fa-f]{8}) \*/")

SECTION_NAMES = {
    "1000.s": "entry",
    # TODO(recon): add the overlay asm filenames once disasm/vpw64.yaml has the real
    # overlay bounds (rom start in hex + ".s", e.g. WM2000 had "4C160.s": "ovl_a").
    # WT/Revenge precedent: TWO overlays sharing ONE vram slot; find the 9-word
    # descriptor table (romStart..bssEnd) in the fixed segment's data.
}

def parse_file(path):
    """Return (rom_start, vram_start, rom_end, [(name, vram, size)])."""
    funcs = []
    pending_size = None
    pending_name = None
    first = None
    last = None
    for line in open(path, encoding="utf-8"):
        m = FUNC_RE.match(line)
        if m:
            pending_name, pending_size = m.group(1), int(m.group(2), 16)
            continue
        m = GLABEL_RE.match(line)
        if m and pending_name == m.group(1):
            funcs.append([pending_name, None, pending_size])
            continue
        m = INSN_RE.match(line)
        if m:
            rom, vram = int(m.group(1), 16), int(m.group(2), 16)
            if first is None:
                first = (rom, vram)
            last = (rom, vram)
            if funcs and funcs[-1][1] is None:
                funcs[-1][1] = vram
    if first is None:
        return None
    return first[0], first[1], last[0] + 4, [(n, v, s) for n, v, s in funcs if v is not None]

def main():
    sections = []
    for path in sorted(ASM.glob("*.s")):
        parsed = parse_file(path)
        if not parsed:
            continue
        rom, vram, rom_end, funcs = parsed
        if path.name == "1000.s":
            name = "entry"
            funcs = [("entrypoint", vram, 0x38)] if not funcs else funcs
        elif path.name in SECTION_NAMES:
            name = SECTION_NAMES[path.name]
        else:
            name = f"main_{rom:X}"
        sections.append((name, rom, vram, rom_end - rom, funcs))

    OUT.parent.mkdir(exist_ok=True)
    unused = set(RENAME) - {"main"}
    with open(OUT, "w", newline="\n") as f:
        f.write("# Autogenerated from splat disassembly by tools/gen_symbols.py\n")
        total = 0
        seen = {}
        for name, rom, vram, size, funcs in sections:
            f.write(f"\n[[section]]\nname = \"{name}\"\n")
            f.write(f"rom = 0x{rom:08X}\nvram = 0x{vram:08X}\nsize = 0x{size:X}\n\n")
            f.write("functions = [\n")
            funcs = sorted(list(funcs) + EXTRA_FUNCS.get(name, []), key=lambda t: t[1])
            for fn, fv, fs in funcs:
                if fn in SKIP:
                    continue
                unused.discard(fn)
                fn = RENAME.get(fn, fn)
                # disambiguate names colliding across same-vram overlays (WT scheme)
                if fn in seen and seen[fn] != (name, fv):
                    fn = f"{fn}_{name}"
                seen[fn] = (name, fv)
                f.write(f"    {{ name = \"{fn}\", vram = 0x{fv:08X}, size = 0x{fs:X} }},\n")
                total += 1
            f.write("]\n")
    print(f"wrote {OUT}: {len(sections)} sections, {total} functions")
    if unused:
        print("WARNING: RENAME keys not found in splat output (splat merged/missed them):")
        for k in sorted(unused):
            print(f"  {k} -> {RENAME[k]}")

if __name__ == "__main__":
    main()
