# ADR-0003: Box MCU — STM32G474, STM32H723 as fallback

**Status:** Accepted — 2026-10-19

## Context

ADR-0002 needs three CAN FD controllers, at least four UARTs, timer capture and fast ADCs for the
Control Pilot, hardware listen-only per CAN controller, hardware receive timestamps and a USB link
to the PC. The CANable 2.0 already used on the bench is built on an STM32G431, the same family and
FDCAN peripheral as the G474. The ESP32-C3 bench is the only firmware written so far.

## Options and scoring

Six candidates. Scores 0–5, weights sum to 100, totals out of 500. *(est.)* marks unverified cells.

| # | Criterion | Weight | ESP32-S3 | **STM32G474** | RP2350 | STM32H563 | STM32H723 | ESP32-P4 |
|---|---|---|---|---|---|---|---|---|
| 1 | Native CAN / CAN FD controllers | 25 | 1 (one TWAI, classic) | 5 (3 FDCAN) | 1 (none) | 4 (2 FDCAN) | 5 (3 FDCAN) | 2 *(est.)* |
| 2 | UARTs | 12 | 3 | 5 | 3 | 5 | 5 | 4 *(est.)* |
| 3 | CP / PP measurement | 8 | 3 | 5 | 3 | 4 | 4 | 3 |
| 4 | Hardware listen-only | 15 | 4 | 5 | 1 | 5 | 5 | 4 |
| 5 | Hardware timestamping | 8 | 3 | 5 | 3 | 5 | 5 | 3 |
| 6 | USB throughput | 7 | 4 | 4 | 4 | 4 | 4 | 5 *(est.)* |
| 7 | On-chip Ethernet (off the board, ADR-0002) | 0 | 0 | 0 | 0 | 5 | 5 | 5 |
| 8 | Wireless | 5 | 5 | 0 | 0 | 0 | 0 | 0 |
| 9 | Familiarity | 12 | 5 | 3 | 2 | 3 | 2 | 3 |
| 10 | Cost and supply | 8 | 4 | 4 | 4 | 4 | 3 | 2 |
| | **Total / 500** | **100** | 314 | **436** | 208 | 403 | 408 | 293 |

These are the validated weights: Ethernet is captured off the board (ADR-0002), so its weight is
0. The three STM32 parts are close and only that weight separates them: at Ethernet 5 and
familiarity 7, the H723 leads by 2 points (H723 423, G474 421, H563 413); at Ethernet 10, taking
the extra points from wireless, it leads clearly (H723 448, H563 438, G474 421).

## Decision

**STM32G474.** **Fallback: STM32H723**, activated only if precise on-board CAN/Ethernet
correlation becomes a real need. It is a PCB redesign (LQFP144, about 10 €), not a drop-in, but
the FDCAN peripheral and the ST HAL are shared, so the CAN firmware carries over.

## Consequences

- The box firmware is a new STM32 target; the ESP32-C3 bench firmware stays as the test generator.
- USB full speed (12 Mbit/s) must carry three loaded CAN FD buses plus the UARTs, which can exceed
  it at high data-phase rates: to be measured before the CDR. The H723 fallback does not lift this
  limit without an external ULPI PHY.
- Unverified: ESP32-P4 CAN FD support, exact prices.
