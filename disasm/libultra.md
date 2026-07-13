# libultra identification evidence — VPW64

How every named function in `tools/gen_symbols.py`'s `RENAME` map was identified.
Convention inherited from the sister projects (see World Tour's
`disasm/libultra.md` for the original per-function evidence this project
transfers from).

## Primary method: fingerprint transfer from World Tour (2026-07-12)

VPW64 and WCW vs. nWo World Tour are direct siblings (December 1997, same
developer, same libultra generation). `tools/vpw_recon2.py` masked every
address-bearing field (16-bit immediates of I-type ALU/loads/stores, 26-bit
j/jal targets) in each of World Tour's 52 named fixed-segment functions and
matched the full masked bodies against VPW64's fixed segment:

- **47/52 matched uniquely** — the best transfer rate in the family
  (WT→Revenge was 3/46 across generations; Revenge→WM2000 was 27/39).
  Each unique full-body masked match inherits the WT name and, transitively,
  WT's original identification evidence.

## Ambiguity resolutions (`tools/vpw_recon3.py`)

- `__osSiDeviceBusy` = `0x80025AF0`: three shape-identical candidates; the raw
  MMIO immediates discriminate — this one polls `lui 0xA480 / lw 0x18 / andi 3`
  (SI_STATUS busy bits). The others poll SP (0xA404/0x10/0x1C) and DP
  (0xA410/0xC/0x100) and are left unnamed (only reached through the already
  runtime-provided osSpTask* set).
- `osViGetCurrentFramebuffer` = `0x80012E70` / `osViGetNextFramebuffer` =
  `0x80012EB0`: adjacent 0x40-apart pair, matched ambiguously as a pair; WT's
  source order (Current first) plus the field offsets they read (+0x40 vs
  +0x44) settle the assignment.

## Byte-exact tiny leaves

Too small for masked matching (no relocations at that size), located by exact
byte search of WT's full body, unique hit each:

- `osAiGetLength` = `0x80017280` (12 bytes: `lui 0xA450; jr; lw 0x4` — AI_LEN).
- `osGetCount` = `0x8001F360` (12 bytes: `mfc0 v0, C0_COUNT; jr; nop`).

## Structure names (not libultra)

- `game_main` = `0x80000450`: the entry stub at 0x1000 jr's here (entry-stub
  decode in `tools/vpw_recon.py`).
- `ovl_load_sections` / `ovl_load_and_enter` / `ovl_swap_loop`: fingerprint
  matches of WT's identically-named overlay plumbing.

## Stub classifications (`tools/vpw_recon4.py`)

The nine `[patches] stubs` in `vpw64.toml` (exception handler, TLB ops,
SR/Compare accessors) each reverse-fingerprint onto the exact function WT also
stubs — identities and WT cross-references are documented above the stubs
block in `vpw64.toml`.
