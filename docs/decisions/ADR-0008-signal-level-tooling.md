# ADR-0008: Signal-level tooling — FX2 + PulseView through an isolated logic tap, Analog Discovery 3 later

**Status:** Accepted — 2026-10-19

## Context

The application works at frame and value level. Some faults only show at signal level: bit
timing, error frames, a Control Pilot duty cycle, glitches — two days of bench time were lost to
jumper wires that measured fine at rest. The owner has a 24 MHz 8-channel logic analyser built on
a Cypress CY7C68013A (FX2, `fx2lafw` firmware), and PulseView with sigrok-cli is installed with
the CAN, Modbus RTU, UART, LIN, I²C and SPI decoders. The FX2 inputs accept 0–5 V only, with no
isolation and no protection.

## Options and scoring

| # | Criterion | Weight | FX2 + PulseView | DSLogic + DSView | **Analog Discovery 3** | Saleae Logic Pro 8 | Scope with decode |
|---|---|---|---|---|---|---|---|
| 1 | Analogue view (CP ±12 V, CAN differential) | 25 | 0 | 0 | 5 (±25 V with BNC adapter, 14 bit, 125 MS/s) | 3 (±10 V) | 5 *(est.)* |
| 2 | CAN / Modbus / UART / LIN decoders | 20 | 5 | 5 *(est.)* | 3 (no Modbus, no LIN) | 4 *(est.)* | 3 *(est.)* |
| 3 | Linux, open, scriptable | 15 | 5 | 4 *(est.)* | 4 | 4 | 2 |
| 4 | Input robustness | 15 | 1 | 3 *(est.)* | 4 (±50 V protection) | 5 (±25 V) | 5 *(est.)* |
| 5 | Cost | 10 | 5 (owned) | 4 *(est.)* | 2 (about 380 $) | 1 (about 1 150 €) | 3 *(est.)* |
| 6 | Sample rate and depth | 10 | 2 | 5 *(est.)* | 4 | 5 | 4 *(est.)* |
| 7 | Already owned | 5 | 5 | 0 | 0 | 0 | 0 |
| | **Total / 500** | **100** | 285 | 295 | **365** | 350 | 360 |

## Decision

- **Now: FX2 + PulseView**, connected only through the box's **isolated 8-channel 3.3 V logic tap
  header** (ADR-0002), which carries each receiver line and the CP comparator output. The
  analyser never touches a charger bus directly.
- **Later: a Digilent Analog Discovery 3**, bought when analogue views become necessary.
  Fallback: the Saleae Logic Pro 8 if more robust inputs matter more than price. The scope
  column scores higher (360) but rests on estimates, so the Saleae stays the fallback until a
  specific scope is scored.

## Consequences

- The logic tap is a box requirement; its isolation is part of the high-voltage review.
- Neither the AD3 nor a bench oscilloscope is isolated: on a charger, use a laptop on battery or
  an isolated USB hub.
- The scope column rests mostly on estimates; to be re-scored if a model is considered.
