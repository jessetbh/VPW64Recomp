#!/usr/bin/env python3
"""Pass-3 recon for VPW64: resolve the pass-2 ambiguities by inspecting the
UNMASKED words (raw-MMIO immediates discriminate the *DeviceBusy family:
lui 0xA480=SI, 0xA460=PI, 0xA404=SP, 0xA410=DP), and settle the
osViGetCurrentFramebuffer/osViGetNextFramebuffer adjacency using WT's order.
Adapted from Wm2k's tools/recon3.py.
"""
import re, struct

VPW = r"C:\Users\selki\depot\Vpw64Recomp\vpw64.z64"
WT_DUMP = r"C:\Users\selki\depot\WcwNwoWorldTour\WCWSyms\dump.toml"

vp = open(VPW, "rb").read()

print("=== __osSiDeviceBusy candidates: raw words ===")
for rom in (0x20060, 0x20090, 0x266F0):
    words = struct.unpack_from(">12I", vp, rom)
    luis = [f"{w:08X}" for w in words]
    print(f"  @0x{rom:06X} (vram 0x{rom - 0x1000 + 0x80000400:08X}): " + " ".join(luis))

print("=== osViGet*Framebuffer candidates: raw words ===")
for rom in (0x13A70, 0x13AB0):
    words = struct.unpack_from(">16I", vp, rom)
    print(f"  @0x{rom:06X} (vram 0x{rom - 0x1000 + 0x80000400:08X}): " +
          " ".join(f"{w:08X}" for w in words))

print("=== WT order of the Vi pair (from dump.toml) ===")
for line in open(WT_DUMP):
    m = re.search(r'\{ name = "(osViGet\w+Framebuffer|__osSiDeviceBusy|__osPiDeviceBusy|__osSpDeviceBusy|__osDpDeviceBusy)", vram = (0x[0-9A-Fa-f]+), size = (0x[0-9A-Fa-f]+)', line)
    if m:
        print(f"  {m.group(1):28s} vram {m.group(2)} size {m.group(3)}")
