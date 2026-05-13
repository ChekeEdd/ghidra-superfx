# ghidra-superfx

A [Ghidra](https://github.com/NationalSecurityAgency/ghidra) processor
module (SLEIGH spec) for Nintendo's **SuperFX / GSU-1 / GSU-2 / MARIO Chip**
co-processor, the 16-bit RISC found inside enhancement-chip SNES cartridges.

| Field | Value |
|---|---|
| Language id | `SuperFX:LE:24:default` |
| Tested against | Ghidra 12.0.4 (currently the latest public release) |
| Forward compatibility | When a newer Ghidra ships (12.1, 12.2, …), open `extension.properties` and change the `version=12.0.4` line to match your build. The SLEIGH spec itself is forward-compatible; Ghidra's extension-version check is the only thing that gates loading. |
| Backward compatibility | Should also work on Ghidra 11.3.2 by setting `version=11.3.2`; not fully retested for that release. |
| Verified ROM | Star Fox (USA) Rev 2 (SHA1 `cf08148cd8f26d51f8c67c956179dfc594e7a4f1`) |
| Accuracy | **100 % byte-boundary, 100 % mnemonic-family agreement** against bsnes ground truth across 64 KB of real GSU code |
| License | BSD 3-Clause |

## Supported games

The SuperFX co-processor was used by:

- Star Fox (USA / EU / JP, all revisions)
- Star Fox 2 (released 2017 via SNES Classic; also playable from leaked
  prototype ROMs)
- Yoshi's Island (a.k.a. Super Mario World 2)
- Stunt Race FX (a.k.a. Wild Trax)
- Doom (SNES)
- Vortex (a.k.a. Citadel)
- Dirt Trax FX
- Winter Gold

Any GSU code in these cartridges decodes through this module.

## Install

### Option A — drop-in folder (fastest)

1. Download or `git clone` this repo.
2. Copy the entire repo contents into a folder named `ghidra-superfx`
   under your Ghidra user extensions directory:
   - Windows: `%APPDATA%\ghidra\ghidra_<VERSION>_PUBLIC\Extensions\ghidra-superfx\`
   - Linux: `~/.config/ghidra/ghidra_<VERSION>_PUBLIC/Extensions/ghidra-superfx/`
   - macOS: `~/Library/ghidra/ghidra_<VERSION>_PUBLIC/Extensions/ghidra-superfx/`
3. (Re)start Ghidra. The module loads automatically; no further GUI
   configuration is required.
4. When importing a ROM, choose `SuperFX:LE:24:default` as the
   Language / Compiler.

### Option B — release zip (for File → Install Extensions)

If a release zip is available on the GitHub Releases page:

1. Ghidra → File → Install Extensions… → `+` → pick the downloaded
   `ghidra-superfx-vX.Y.Z.zip`.
2. Tick the new "SuperFX" entry, click OK, restart Ghidra.
3. Same Language selection step as Option A.

## What the module does

- Decodes all ~80 GSU instructions (STOP / NOP / CACHE / LSR / ROL,
  10 conditional branches, register-encoded ALU (ADD / SUB / AND / OR /
  XOR / MULT / UMULT / INC / DEC), TO / WITH / FROM register
  prefixes, LOAD / STORE word & byte families, IBT / IWT / LMS / SMS /
  LM / SM immediate-and-memory transfers, JMP / LJMP, LINK, LOOP,
  PLOT / RPIX / COLOR / CMODE / MERGE graphics ops, FMULT / LMULT
  fractional multiplies, GETB / GETC ROM-byte fetches, RAMB / ROMB
  bank-register writes, HIB / LOB / SEX / ROR / ASR / DIV2 / SWAP /
  NOT bit ops).
- Models the **ALT1 / ALT2 / ALT3 prefix state machine** through a
  SLEIGH context register propagated with `globalset(inst_next, …)`.
- Models the **branch delay slot** on every taken control-flow
  instruction (BRA + 10 conditional branches, JMP, LJMP, LOOP,
  `IWT R15, #imm16`) via SLEIGH's `delayslot(1)` directive — important
  for accurate P-code / decompiler output.
- Maps the special-function registers `SFR`, `PBR`, `ROMBR`, `RAMBR`,
  `CBR`, `SCBR`, `SCMR`, `COLR`, `POR`, `BRAMR`, `CFGR` plus the
  individual SFR flag bits as discrete varnodes.

See [`CHANGELOG.md`](CHANGELOG.md) for the version-by-version history
and the slaspec header for full design rationale.

## Limitations / known corner cases

- Hex prefix style (`$` vs `0x`) is a Ghidra-wide Listing display
  option (Edit → Tool Options → Listing Display). This module emits
  the default `0x` prefix; the user-facing choice is not slaspec
  controllable. (Confirmed by surveying Ghidra-shipped 6502, 65C02,
  CR16C specs and the SLEIGH `tokens` documentation.)
- An `ALT1` / `ALT2` / `ALT3` prefix appearing **inside the delay slot
  of a taken branch** would (per a strict reading of the hardware)
  mark the branch target with the ALT flag. This module sets the flag
  at the prefix's physical fall-through address, which is correct in
  straight-line code and the entire 64 KB of validated Star Fox GSU
  code, but is the wrong address for that particular corner case.
  Fixing it requires a major restructuring of how altCtx is carried
  and is left for a future pcodeop-driven runtime-flag rewrite.

## Validation methodology

The module is byte-validated against bsnes' SuperFX disassembler
(`bsnes/processor/gsu/disassembler.cpp`, BSD-licensed). The validation
harness extracts a chunk of GSU code from a real Star Fox ROM, walks
it linearly through both bsnes' Python-reimplemented decoder and
Ghidra's headless analyzer using this module, then diffs the two
text outputs line by line. Across 64 KB of real GSU code (covering
all 12 RPC entry points in Star Fox, plus their helpers and the AC1D
per-frame driver) the two decoders agree on 100 % of byte boundaries
and 100 % of mnemonic families.

## References

This module's design uses public reference material only. No bytes
from leaked source were copied:

- bsnes-jg / bsnes (BSD 3-Clause) — instruction encoding and semantics
- SnesLab Super_FX wiki — register layout & SFR bit definitions
- Wikibooks SNES Programming Super FX tutorial — opcode summary
- jsgroth.dev SNES coprocessors part 7 — pipeline, cache, delay-slot
  documentation
- problemkaputt.de fullsnes.htm — SNES bus integration
- Ghidra's MIPS / 6502 / ARM SLEIGH specs — SLEIGH idiom reference
  (`delayslot`, `globalset`, context register patterns)

## Origin

Originally developed as Phase 1a of a clean-room
[Star Fox SNES decompilation](https://github.com/edwardchekanua/StarFoxDecompilation)
(repo name pending publication). Split out into a standalone repo so
it is useful to anyone reverse-engineering a SuperFX game, not only
Star Fox.

## Contributing

Bug reports and PRs are welcome. If you find a real ROM where this
module's disassembly disagrees with bsnes ground truth, please open
an issue with the ROM SHA1, the GSU PC address, and the byte sequence
that misdecodes.

## License

BSD 3-Clause — see [`LICENSE`](LICENSE).
