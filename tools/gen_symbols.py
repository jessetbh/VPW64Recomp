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
    # target unnamed; the entry stub at rom 0x1000 jr's to it at 0x80000450 —
    # confirmed by entry-stub decode, vpw_recon.py 2026-07-12):
    "main": "game_main",
    "func_80000450": "game_main",

    # --- WT fingerprint transfer, 2026-07-12 (vpw_recon2.py): masked full-body
    #     match of WT's named set, 47/52 unique — the family's best transfer, as
    #     the same-generation sibling prediction said. Evidence per function:
    #     WT's disasm/libultra.md. Naming a function makes N64Recomp auto-ignore
    #     it (built-in set in N64Recomp/src/symbol_lists.cpp) so the runtime
    #     provides it; game-structure names (ovl_*) are documentation.
    "func_8000075C": "ovl_load_sections",
    "func_800007C8": "ovl_load_and_enter",
    "func_800117C4": "ovl_swap_loop",
    "func_80011960": "osInitialize",
    "func_80011BF0": "osCreateThread",
    "func_80011D40": "osStartThread",
    "func_80011E90": "osCreatePiManager",
    "func_80012020": "osCartRomInit",
    "func_80012170": "osCreateMesgQueue",
    "func_800121A0": "osSetThreadPri",
    "func_800122B0": "osSendMesg",
    "func_80012400": "osInvalDCache",
    "func_800124B0": "osEPiStartDma",
    "func_80012590": "osRecvMesg",
    "func_800126D0": "osInvalICache",
    "func_800127F0": "__osDisableInt",
    "func_80012810": "__osRestoreInt",
    "func_80012830": "osCreateViManager",
    "func_80012B90": "osViSetMode",
    "func_80012C00": "osViBlack",
    "func_80012C70": "osSetEventMesg",
    "func_80012CE0": "osViSetEvent",
    "func_80012D50": "osSetIntMask",
    "func_80012DF0": "osSpTaskYielded",
    "func_80012F40": "osWritebackDCacheAll",
    "func_8001308C": "osSpTaskLoad",
    "func_8001321C": "osSpTaskStartGo",
    "func_80013260": "osDpSetNextBuffer",
    "func_80013310": "osSpTaskYield",
    "func_80013640": "osViSetSpecialFeatures",
    "func_80013DD0": "__d_to_ll",
    "func_80013DEC": "__f_to_ll",
    "func_80013E08": "__d_to_ull",
    "func_80013EA8": "__f_to_ull",
    "func_80013F44": "__ll_to_d",
    "func_80013F5C": "__ll_to_f",
    "func_80013F74": "__ull_to_d",
    "func_80013FA8": "__ull_to_f",
    "func_80014290": "osVirtualToPhysical",
    "func_80014310": "osWritebackDCache",
    "func_80014430": "osAiSetFrequency",
    "func_800171D0": "osAiSetNextBuffer",
    "func_80017970": "osContInit",
    "func_8001E170": "osGetThreadPri",
    "func_80024030": "osGetTime",
    "func_80025AF0": "__osSiDeviceBusy",  # of 3 shape-matches, the lui 0xA480 /
        # lw 0x18 / andi 3 one = SI_STATUS (vpw_recon3.py; others are SP/DP variants)
    "func_800241A0": "__osSiRawStartDma",
    # Vi getter pair: adjacent 0x40-apart, WT's source order (Current first) —
    # 0x12E70 loads field +0x40, 0x12EB0 loads +0x44 (vpw_recon3.py):
    "func_80012E70": "osViGetCurrentFramebuffer",
    "func_80012EB0": "osViGetNextFramebuffer",
    # Tiny leaves, byte-exact unique match of WT's full body (no relocs at that size):
    "func_80017280": "osAiGetLength",
    "func_8001F360": "osGetCount",
    # Vi swap: fingerprint-matched:
    "func_80012EF0": "osViSwapBuffer",
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
    # Overlays per the descriptor table at rom 0x3FAC0/0x3FAE4 (disasm/vpw64.yaml):
    # two overlays sharing vram slot 0x80088000.
    "F1AF80.s": "ovl_a",
    "F6D170.s": "ovl_b",
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
