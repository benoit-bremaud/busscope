# ADR-0005: Toolchain — KiCad, ngspice, FreeCAD scripted in Python

**Status:** Accepted — 2026-10-19

## Context

The box needs schematic capture, PCB layout, circuit calculations, simulation of the analogue
front ends (CP ±12 V input, terminations, isolation) and a 3D-printed enclosure. The owner asked
for KiCad with its PCB Calculator, PSpice for simulation and FreeCAD for the enclosure. The
development machine runs Linux; the owner's other hardware projects simulate with ngspice netlists
replayed in review.

## Options and scoring (simulation)

Two families exist: verification tools, whose results enter the design dossier and must be
replayable, and intuition or cross-check tools, mostly online. Only the first family is scored as
the primary tool.

| # | Criterion | Weight | **ngspice in KiCad** | PSpice | LTspice under Wine | Qucs-S | Falstad / CircuitJS |
|---|---|---|---|---|---|---|---|
| 1 | Native Linux | 20 | 5 | 0 (Windows only) | 2 *(est.)* | 5 | 4 (browser) |
| 2 | Simulates the KiCad schematic itself | 20 | 5 | 1 | 1 | 2 | 0 |
| 3 | Vendor models | 15 | 4 (reads most PSpice models) | 5 | 5 | 4 | 0 |
| 4 | Replayable in Git and CI | 20 | 5 (`.cir`, `ngspice -b`) | 1 | 3 *(est.)* | 3 | 1 |
| 5 | Analogue and transient accuracy | 10 | 4 | 5 | 5 | 4 | 1 |
| 6 | Learning curve | 10 | 3 | 3 | 4 | 3 | 5 |
| 7 | Cost | 5 | 5 | 1 | 5 | 5 | 5 |
| | **Total / 500** | **100** | **455** | 200 | 310 | 355 | 185 |

Halving criterion 2 keeps ngspice first (405 against 335).

## Decision

- **KiCad** for schematics and layout, with its **PCB Calculator** for track widths, clearances
  and impedances.
- **ngspice inside KiCad** for simulation; netlists and plots are versioned and reviewed in pull
  requests. **Fallback: LTspice under Wine**, only for a part whose model exists for LTspice alone.
- **Online tools** (Falstad, impedance calculators) are welcome for intuition and cross-checks,
  never as the source of a figure in the calculations file; only generic circuits are sent to
  them, never the full design.
- **FreeCAD** for the enclosure, driven by a versioned Python script; STL/STEP outputs are
  generated, and the board's STEP export from KiCad positions connectors and fixings.

## Consequences

- PSpice, requested at first, is not used: Windows-only and not replayable in CI.
- Hardware CI follows the owner's other projects: ERC/DRC and fabrication outputs through KiBot.
