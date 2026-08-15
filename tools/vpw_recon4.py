#!/usr/bin/env python3
"""Pass-4 recon: classify VPW64's remaining stub functions (cop0/cache/tlb
bodies gen_stubs.py flagged) by reverse-fingerprinting each against WORLD
TOUR's fixed segment and reporting which WT function (named or not) contains
the match. Masked-match method as vpw_recon2.py."""
import os, re, struct

# Resolve ROMs/symbols relative to this script (workspace root = ../..) so no
# absolute machine paths live in git; sibling repos sit alongside this one.
_WS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

def _sib(*parts):
    return os.path.join(_WS, *parts)

VPW = _sib("Vpw64Recomp", "vpw64.z64")
WT  = _sib("WcwNwoWorldTour", "wcw.z64")
VPW_DUMP = _sib("Vpw64Recomp", "syms", "dump.toml")
WT_DUMP = _sib("WcwNwoWorldTour", "WCWSyms", "dump.toml")

vp = open(VPW, "rb").read()
wt = open(WT, "rb").read()

STUBS = ["func_8001D4D0", "func_8001D4E0", "func_8001D5A0", "func_8001DA9C",
         "func_8001DBCC", "func_8001DD24", "func_8001DEB0", "func_8001F4C0",
         "func_80026640"]

def load_funcs(path):
    out = []
    for line in open(path):
        m = re.search(r'\{ name = "([^"]+)", vram = (0x[0-9A-Fa-f]+), size = (0x[0-9A-Fa-f]+)', line)
        if m:
            out.append((m.group(1), int(m.group(2), 16), int(m.group(3), 16)))
    return out

vp_funcs = {n: (v, s) for n, v, s in load_funcs(VPW_DUMP)}
wt_funcs = [(n, v, s) for n, v, s in load_funcs(WT_DUMP) if 0x80000400 <= v < 0x80088000]

def mask_word(w):
    op = w >> 26
    if op in (2, 3): return w & 0xFC000000
    if op in (8,9,0xA,0xB,0xC,0xD,0xE,0xF) or 0x20 <= op <= 0x3F: return w & 0xFFFF0000
    return w

def masked(buf):
    return [mask_word(struct.unpack_from(">I", buf, i)[0]) for i in range(0, len(buf)//4*4, 4)]

# WT fixed segment: rom 0x1000 <-> vram 0x80000400, code to ~0x2A9B0
wt_code = masked(wt[0x1000:0x2A9B0])

def wt_func_at(vram):
    for n, v, s in wt_funcs:
        if v <= vram < v + s:
            return f"{n} (+0x{vram - v:X}, size 0x{s:X})"
    return "?"

for name in STUBS:
    vram, size = vp_funcs[name]
    rom = 0x1000 + (vram - 0x80000400)
    words = struct.unpack_from(f">{min(size//4, 6)}I", vp, rom)
    ops = " ".join(f"{w:08X}" for w in words)
    pat = masked(vp[rom:rom+size])
    matches = []
    first = pat[0]
    for i in range(len(wt_code) - len(pat) + 1):
        if wt_code[i] == first and wt_code[i:i+len(pat)] == pat:
            matches.append(0x80000400 + i*4)
            if len(matches) > 4: break
    print(f"{name} size 0x{size:X}")
    print(f"   head: {ops}")
    if matches:
        for m in matches:
            print(f"   WT match vram 0x{m:08X}: {wt_func_at(m)}")
    else:
        print("   no WT match")
