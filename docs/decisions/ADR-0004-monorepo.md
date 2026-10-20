# ADR-0004: One repository for board, firmware, core and UI

**Status:** Accepted — 2026-10-19

## Context

The box (ADR-0002) adds a KiCad design, an STM32 firmware and a USB protocol shared with the
application. The repository already holds the ESP32-C3 bench firmware next to the Python
application. The owner's comparable hardware projects are single repositories.

## Options and scoring

| # | Criterion | Weight | **A: one repository** | B: box repo + app repo | C: three repositories |
|---|---|---|---|---|---|
| 1 | USB protocol traceability box ↔ app | 25 | 5 (one PR changes both sides) | 3 | 2 |
| 2 | Consistency with the owner's other hardware projects | 20 | 5 | 3 | 2 |
| 3 | Separate CI per stack | 15 | 3 (path filters) | 5 | 5 |
| 4 | Confidentiality | 15 | 4 | 4 | 4 |
| 5 | Simplicity | 15 | 4 | 3 | 1 |
| 6 | Independent releases | 10 | 3 (tag lanes) | 5 | 5 |
| | **Total / 500** | **100** | **420** | 365 | 290 |

Doubling the CI weight keeps A first (465 against 440).

## Decision

**One repository.** Fallback: B, if the CI of one stack starts to slow the others down.

## Consequences

- Top-level areas: the application, `firmware/` (bench and box), `hardware/` (KiCad, simulations),
  `mechanics/` (enclosure); CI jobs filtered by path.
- Release tags use separate lanes, for example `v*` for the application and `pcb-r*` / `proto-r*`
  for boards, with a `REVISIONS.md` for hardware.
- The repository is public: schematics are welcome, charger captures and vendor-confidential
  material never are.
