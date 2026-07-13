#!/usr/bin/env python3
"""Pass-1 ROM recon for Virtual Pro Wrestling 64 (J), adapted from Wm2k's
tools/recon.py (kept there as the method reference). VPW64 is WT's Dec-1997
sibling, so WT is the primary comparison target: entry-stub decode, jr-$ra
density code regions, sister-ROM similarity, the 9-word overlay-descriptor
scan, and the WT aspMain audio-ucode byte search (WT rom 0x2A850, 0xE20).
"""
import struct

VPW = r"C:\Users\selki\depot\Vpw64Recomp\vpw64.z64"
WT  = r"C:\Users\selki\depot\WcwNwoWorldTour\wcw.z64"
REV = r"C:\Users\selki\depot\WcwRevengeRecomp\revenge.z64"

vp = open(VPW, "rb").read()
wt = open(WT, "rb").read()
rev = open(REV, "rb").read()

# --- entry stub at rom 0x1000 (vram 0x80000400): decode enough to see the bss
#     clear range, initial sp, and the jump to game_main (WT expects 0x80000460).
print("=== entry stub words @0x1000 ===")
REG = ("zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 "
       "s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp fp ra").split()
def dis(w):
    op = w >> 26
    rs, rt = (w >> 21) & 31, (w >> 16) & 31
    imm = w & 0xFFFF
    if w == 0: return "nop"
    if op == 0x0F: return f"lui   ${REG[rt]}, 0x{imm:04X}"
    if op == 0x09: return f"addiu ${REG[rt]}, ${REG[rs]}, 0x{imm:04X}"
    if op == 0x08: return f"addi  ${REG[rt]}, ${REG[rs]}, 0x{imm:04X}"
    if op == 0x0D: return f"ori   ${REG[rt]}, ${REG[rs]}, 0x{imm:04X}"
    if op == 0x2B: return f"sw    ${REG[rt]}, 0x{imm:04X}(${REG[rs]})"
    if op == 0x23: return f"lw    ${REG[rt]}, 0x{imm:04X}(${REG[rs]})"
    if op == 0x05: return f"bne   ${REG[rs]}, ${REG[rt]}, {imm}"
    if op == 0x04: return f"beq   ${REG[rs]}, ${REG[rt]}, {imm}"
    if op in (2, 3): return f"{'j' if op==2 else 'jal'}   0x{((w & 0x3FFFFFF) << 2) | 0x80000000:08X}"
    if op == 0 and (w & 0x3F) == 8: return f"jr    ${REG[rs]}"
    if op == 0 and (w & 0x3F) == 0x25: return f"or    ${REG[(w>>11)&31]}, ${REG[rs]}, ${REG[rt]}"
    return f".word 0x{w:08X}"
for i in range(20):
    w = struct.unpack_from(">I", vp, 0x1000 + i*4)[0]
    print(f"  0x{0x80000400 + i*4:08X}: {w:08X}  {dis(w)}")
print("  --- same stub in WT for comparison ---")
for i in range(20):
    w = struct.unpack_from(">I", wt, 0x1000 + i*4)[0]
    print(f"  0x{0x80000400 + i*4:08X}: {w:08X}  {dis(w)}")

# --- jr $ra density -> code regions
def regions(rom, thresh=8, window=0x4000):
    regs, start = [], None
    for base in range(0, len(rom), window):
        n = rom[base:base+window].count(b"\x03\xe0\x00\x08")
        if n >= thresh and start is None: start = base
        elif n < thresh and start is not None: regs.append((start, base)); start = None
    if start is not None: regs.append((start, len(rom)))
    return regs
print("=== VPW64 code regions (jr $ra density >= 8/16KB) ===")
for s, e in regions(vp):
    print(f"  0x{s:06X} - 0x{e:06X}  ({(e-s)//1024} KB)")

# --- sister similarity, first 64KB from 0x1000
print("=== boot-code similarity: identical 16-byte blocks at same offset, 0x1000..0x11000 ===")
for name, other in (("WorldTour", wt), ("Revenge", rev)):
    same = total = 0
    for off in range(0x1000, 0x11000, 16):
        total += 1
        if vp[off:off+16] == other[off:off+16]: same += 1
    print(f"  vs {name}: {same}/{total} blocks identical ({100*same//total}%)")

# --- overlay descriptor scan (9 words: romStart, romEnd, entry, textStart,
#     textEnd, dataStart, dataEnd, bssStart, bssEnd)
print("=== overlay descriptor candidates ===")
def is_vram(w): return 0x80000000 <= w < 0x80800000
for off in range(0x1000, min(len(vp), 0x200000), 4):
    w = struct.unpack_from(">9I", vp, off)
    if (0x1000 <= w[0] < w[1] <= len(vp) and
            all(is_vram(x) for x in w[2:9]) and
            w[3] <= w[4] <= w[5] <= w[6] <= w[7] <= w[8] and
            w[3] <= w[2] < w[8] and
            (w[1] - w[0]) == (w[6] - w[3])):
        print(f"  desc @rom 0x{off:06X}: rom 0x{w[0]:06X}-0x{w[1]:06X} entry 0x{w[2]:08X} "
              f"text 0x{w[3]:08X}-0x{w[4]:08X} data 0x{w[5]:08X}-0x{w[6]:08X} bss 0x{w[7]:08X}-0x{w[8]:08X}")

# --- audio ucode: WT's stock aspMain (rom 0x2A850, 0xE20) — the expected case.
print("=== WT aspMain audio-ucode text search ===")
sig = wt[0x2A850:0x2A850+0xE20]
idx = vp.find(sig)
print(f"  full 0xE20-byte match at: {hex(idx) if idx >= 0 else 'NOT FOUND'}")
if idx < 0:
    idx = vp.find(sig[:0x100])
    print(f"  first 0x100 bytes match at: {hex(idx) if idx >= 0 else 'NOT FOUND'}")
    sig2 = rev[0x2C910:0x2C910+0xC54]
    idx = vp.find(sig2)
    print(f"  Revenge newer-ucode full match at: {hex(idx) if idx >= 0 else 'NOT FOUND'}")

# --- ucode name strings
print("=== ucode name string search ===")
for pat in (b"F3DEX2", b"F3DEX", b"S2DEX", b"aspMain", b"RSP Gfx", b"RSP SW"):
    pos, hits = 0, []
    while True:
        i = vp.find(pat, pos)
        if i < 0 or len(hits) > 6: break
        hits.append(i); pos = i + 1
    if hits:
        print(f"  {pat}: " + " ".join(hex(h) for h in hits[:6]))
