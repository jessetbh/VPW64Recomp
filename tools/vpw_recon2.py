#!/usr/bin/env python3
"""Pass-2 recon for VPW64: fixed-segment code/data boundary, descriptor-table
context, and the libultra fingerprint transfer FROM WORLD TOUR (same Dec-1997
libultra generation — expected to be the family's best transfer). Adapted from
Wm2k's tools/recon2.py.

Fingerprint method: mask address-bearing fields (16-bit immediates of I-type
ALU/loads/stores, 26-bit j/jal targets), keep everything else. Match each named
WT function's full masked body against VPW64's fixed-segment code.
"""
import os, re, struct

# Resolve ROMs/symbols relative to this script (workspace root = ../..) so no
# absolute machine paths live in git; sibling repos sit alongside this one.
_WS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

def _sib(*parts):
    return os.path.join(_WS, *parts)

VPW = _sib("Vpw64Recomp", "vpw64.z64")
WT  = _sib("WcwNwoWorldTour", "wcw.z64")
WT_DUMP = _sib("WcwNwoWorldTour", "WCWSyms", "dump.toml")

vp = open(VPW, "rb").read()
wt = open(WT, "rb").read()

# Fixed segment: rom 0x1000 <-> vram 0x80000400; data ends at bss start
# 0x8004A060 (entry-stub decode) -> rom 0x4AC60 = assets start.
VP_DATA_END = 0x4AC60

# --- descriptor table context (descs found at rom 0x3FAC0/0x3FAE4 = vram
#     0x8003EEC0/0x8003EEE4): print surrounding words to confirm table extent.
print("=== words around descriptor table 0x3FA80..0x3FB40 ===")
for off in range(0x3FA80, 0x3FB40, 0x24):
    w = struct.unpack_from(">9I", vp, off)
    print(f"  0x{off:06X} (vram 0x{off - 0x1000 + 0x80000400:08X}): " +
          " ".join(f"{x:08X}" for x in w))

# --- valid-instruction ratio per 1KB window over the fixed segment: find the
#     code/data boundary and any IDO cold-code pockets inside "data".
def looks_insn(w):
    op = w >> 26
    if w == 0: return True
    if op == 0: return True
    return op in (1,2,3,4,5,6,7,8,9,0xA,0xB,0xC,0xD,0xE,0xF,0x10,0x11,0x14,0x15,0x16,0x17,
                  0x20,0x21,0x22,0x23,0x24,0x25,0x26,0x27,0x28,0x29,0x2A,0x2B,0x2E,0x2F,
                  0x31,0x35,0x39,0x3D)
print("=== low-validity 1KB windows in fixed segment 0x1000..0x4AC60 (data pockets) ===")
run_start = None
for base in range(0x1000, VP_DATA_END, 0x400):
    n = ok = 0
    for o in range(base, min(base + 0x400, VP_DATA_END), 4):
        w = struct.unpack_from(">I", vp, o)[0]
        n += 1
        if looks_insn(w): ok += 1
    bad = ok / n < 0.9
    if bad and run_start is None: run_start = base
    if not bad and run_start is not None:
        print(f"  0x{run_start:06X} - 0x{base:06X}")
        run_start = None
if run_start is not None:
    print(f"  0x{run_start:06X} - 0x{VP_DATA_END:06X}")

# --- last jr $ra before the audio-ucode block at 0x2B410 (code end candidate)
last = -1
for off in range(0x1000, 0x2B410, 4):
    if vp[off:off+4] == b"\x03\xe0\x00\x08":
        last = off
print(f"=== last jr $ra before ucode block 0x2B410: rom 0x{last:06X} "
      f"(func end ~0x{last + 8:06X}, vram 0x{last + 8 - 0x1000 + 0x80000400:08X}) ===")

# --- fingerprint transfer WT -> VPW64 ---
def mask_word(w):
    op = w >> 26
    if op in (2, 3):
        return w & 0xFC000000
    if op in (8,9,0xA,0xB,0xC,0xD,0xE,0xF) or 0x20 <= op <= 0x3F:
        return w & 0xFFFF0000
    return w

def masked(buf):
    return [mask_word(struct.unpack_from(">I", buf, i)[0]) for i in range(0, len(buf)//4*4, 4)]

vp_code = masked(vp[0x1000:VP_DATA_END])

sec_rom = sec_vram = 0
targets = []
for line in open(WT_DUMP):
    m = re.match(r'rom = (0x[0-9A-Fa-f]+)', line)
    if m: sec_rom = int(m.group(1), 16)
    m = re.match(r'vram = (0x[0-9A-Fa-f]+)', line)
    if m: sec_vram = int(m.group(1), 16)
    m = re.search(r'\{ name = "([^"]+)", vram = (0x[0-9A-Fa-f]+), size = (0x[0-9A-Fa-f]+)', line)
    if m and not m.group(1).startswith("func_") and m.group(1) not in ("entrypoint", "game_main"):
        name, vram, size = m.group(1), int(m.group(2), 16), int(m.group(3), 16)
        if 0x80000400 <= vram < 0x80088000:   # fixed segment only
            targets.append((name, sec_rom + (vram - sec_vram), size))

print(f"=== fingerprint transfer: {len(targets)} named WT functions -> VPW64 ===")
hits = ambiguous = 0
for name, rom, size in sorted(targets, key=lambda t: t[0]):
    pat = masked(wt[rom:rom+size])
    if len(pat) < 4:
        print(f"  {name:28s} too small, skipped"); continue
    matches = []
    first = pat[0]
    for i in range(len(vp_code) - len(pat) + 1):
        if vp_code[i] != first: continue
        if vp_code[i:i+len(pat)] == pat:
            matches.append(0x1000 + i*4)
            if len(matches) > 3: break
    if len(matches) == 1:
        vram = 0x80000400 + (matches[0] - 0x1000)
        print(f"  {name:28s} -> rom 0x{matches[0]:06X} vram 0x{vram:08X}")
        hits += 1
    elif matches:
        print(f"  {name:28s} AMBIGUOUS x{len(matches)}: " + " ".join(hex(m) for m in matches))
        ambiguous += 1
    else:
        print(f"  {name:28s} no match")
print(f"=== {hits} unique + {ambiguous} ambiguous of {len(targets)} ===")
