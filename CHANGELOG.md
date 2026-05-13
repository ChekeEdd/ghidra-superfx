# Changelog

All notable changes to ghidra-superfx are recorded in this file.
The format is loosely based on Keep a Changelog; versions follow the
SLEIGH spec's own version stamp in `data/languages/superfx.slaspec`.

## v0.3.1 — 2026-05-13

Post-release review fixes (cosmetic / correctness, no functional
regression for mnemonic disassembly).

### Fixed

- **`GSU_REGS` / `GSU_CACHE` default memory blocks no longer overlap.**
  v0.3.0 declared `GSU_REGS` as `start=$3000, length=0x300` which
  collided with `GSU_CACHE` at `$3100`. Per the SuperFX bus map
  the register window is `$3000-$30FF` (length `0x100`); the
  instruction cache covers `$3100-$32FF`. Fixed in `superfx.pspec`.
- **`STOP` pipeline behaviour documented (no semantic change).**
  A first pass added `delayslot(1)` to `STOP` on the theory that the
  byte after STOP runs as a delay slot. Pre-commit codex review
  caught that this was wrong: bsnes-jg's `regs.pipeline = 0x01` line
  in `instructionSTOP` REPLACES the pre-fetched byte with a NOP — it
  does not execute the stream byte that follows STOP. Adding a delay
  slot would have made Ghidra mis-execute and mis-classify whatever
  followed STOP in memory. Reverted before commit; `STOP` keeps the
  plain semantic body. SnesLab's "put a NOP after STOP" convention
  is an assembler-clarity guideline, not an execution requirement.
- **`superfx.ldefs` `version` bumped from `0.1` to `0.3`** so the
  manifest the Ghidra Processor Manager UI reads matches the
  slaspec header changelog.

### Known limitation, scheduled for v0.4

- **`SREG` / `DREG` selectors only partially modelled.** On real
  SuperFX hardware, `WITH Rn` / `TO Rn` / `FROM Rn` are prefix
  instructions that set the source / destination register selectors
  for the next ALU / load / store op. Our v0.3.x state:

  | Opcode | Hardware behaviour | This slaspec emits |
  |---|---|---|
  | `WITH Rn` | `SREG := Rn`, `DREG := Rn` | `SREG := Rn`, `DREG := Rn` ✓ |
  | `TO Rn`   | `DREG := Rn` (prefix to next op) | `Rn := R0` (direct copy, **does not touch DREG**) |
  | `FROM Rn` | `SREG := Rn` (prefix to next op) | `R0 := Rn` (direct copy, **does not touch SREG**) |

  And even when WITH does populate the selectors, the following
  ALU / load / store opcodes still read and write `R0` directly
  rather than indirecting through `R<SREG>` / `R<DREG>`. So the
  selectors carry no data flow downstream into the decompiler.

  Mnemonic disassembly remains 100 % byte-boundary and 100 %
  family-name correct against bsnes ground truth (`bsnes/processor/
  gsu/disassembler.cpp` ALT0 also prints standalone `to rN` and
  `from rN` mnemonics in this style). What is missing is the
  P-code data flow across `WITH`/`TO`/`FROM` prefix sequences.

  v0.4 plan: rewrite `TO` / `FROM` as proper prefix constructors
  that emit a `globalset(inst_next, ...)` of the selector context,
  then rebuild the ALU / load / store constructors so they read
  `R<SREG>` and write `R<DREG>` via attached sub-tables.

## v0.3.0 — 2026-05-13

The "no more deferrals" release. Three items previously marked
"deferred / out of scope" in v0.2.4 are each either implemented or
formally closed with concrete evidence.

### Added

- **Branch delay-slot modelling.** SuperFX hardware always executes
  one instruction after a taken branch / jump (the architectural
  delay slot). v0.3.0 inserts SLEIGH's `delayslot(1)` directive into
  the semantic action of every control-flow-modifying constructor
  before its `goto`:
  - `BRA` and the 10 conditional branches (`BLT` / `BGE` / `BNE` /
    `BEQ` / `BPL` / `BMI` / `BCC` / `BCS` / `BVC` / `BVS`)
  - `JMP Rn` in ALT0 and ALT2
  - `LJMP Rn` in ALT1 and ALT3
  - `LOOP` (loop-counter conditional branch via R12 / R13)
  - `IWT R15, #imm16` — new dedicated constructor carved out of the
    generic IWT family; writing R15 is architecturally a long branch
    and gets the same treatment
- Pre-slot target capture pattern: branch / jump targets are captured
  into a local varnode **before** `delayslot(1)` so that any slot
  instruction reading R15 / PBR / CBR observes the pre-branch values,
  not the new ones.

### Documented

- **Hex prefix `$` vs `0x`** is a Ghidra Tool-level Listing Display
  preference, NOT slaspec-controllable. Closed with citation to
  Ghidra-shipped 6502, 65C02, CR16C specs and the SLEIGH `tokens`
  documentation. See slaspec header for full evidence.
- **Branch display as absolute target** kept intentionally. Every
  Ghidra-shipped processor with PC-relative branches (MIPS, ARM,
  etc.) resolves to absolute addresses in the listing for navigable
  xrefs. bsnes prints relative offsets because it is a linear-walking
  debugger; Ghidra is interactive and absolute is more useful.

### Known limitations

- **ALT prefix in a taken-branch delay slot** is a corner case where
  the altCtx flag is set on the physical fall-through address rather
  than the branch target. This does not occur in any of the 64 KB of
  real Star Fox GSU code we have validated; left as a future
  pcodeop-driven rewrite.

## v0.2.4 — 2026-05-13

Cosmetic display polish identified during wide-region validation.

- `LM` / `SM` operand now displays the 16-bit immediate with
  `(#imm)` parens to match `LMS` / `SMS` and bsnes
- Shared-op 4-bit immediates (ADD / SUB / AND / MULT / OR in ALT2,
  ADC / BIC / UMULT / XOR in ALT3) now display decimal "0".."15"
  instead of hex "0x0".."0xf"
- `branchDelay` context register declared but not yet honoured —
  follow-up in v0.3.0

## v0.2.3 — 2026-05-13

- Bug D fix: shared opcodes ($00 STOP / $01 NOP / $02 CACHE / $05–
  $0F branches / etc.) previously declared only under altCtx=0 and
  would emit `unimpl` when prefixed by ALT1/2/3 in real code. Now
  ungated where bsnes shows the opcode is identical across ALT states,
  or duplicated as parallel constructors where pairs share semantics.
- 18 constraint clauses removed; 13 new duplicate constructors added.

## v0.2.2 — 2026-05-13

- Bug A fix: `$DF` altCtx mapping was off by one. v0.2.1 had
  `RAMB@ALT1` and `ROMB@ALT2`; bsnes has `GETC@ALT1`, `RAMB@ALT2`,
  `ROMB@ALT3`. Corrected.

## v0.2.1 — 2026-05-13

- Bug 1 fix: `$10`–`$1F` now displays as `TO Rn` instead of `MOVE Rn`
- Bug 2 fix: `LMS` / `SMS` operand byte now displayed as the
  effective RAM word address (`byte << 1`) instead of the raw byte
- Bug 3 fix: ALT3+`$DF` (ROMB) was previously `unimpl`; now decodes

## v0.2 — 2026-05-13

- Remaining ALT0 opcodes implemented (PLOT, MERGE, ROR, FMULT, GETC,
  GETB, SBK, LOOP)
- Full ALT1 / ALT2 / ALT3 context-driven decoding via the `altCtx`
  context register propagated with `globalset(inst_next, …)`

## v0.1 — 2026-05-12

- Initial scaffolding: pspec / ldefs / cspec / slaspec compiling
  under Ghidra 12.0.4
- Register file (R0–R15 plus SFR / PBR / ROMBR / RAMBR / CBR / SCBR /
  SCMR / COLR / POR / BRAMR / CFGR plus individual flag bits)
- Context register for ALT1 / ALT2 / ALT3 decode-time state
- Approximately 40 ALT0 opcodes implemented with P-code semantics
