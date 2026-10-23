# ADR-0009: Transmission kill switch — a default-off environment variable

**Status:** Accepted — 2026-10-23

## Context

The application ships a Transmission tab (issue #34) that can send a frame on a SocketCAN
interface. It is gated by a checkbox, a confirmation dialog and a refusal on listen-only
interfaces, but it is present in every build. AGENTS.md requires transmission to stay disabled
until explicitly designed, reviewed, tested and enabled, and the capture tab claims that frame
transmission is disabled. The CAN audit of 2026-10-21 filed this as a Must (issue #95).

## Options and scoring

| # | Criterion | Weight | **A. Env var** | B. Build flag | C. Build flag + env var | D. Settings file |
|---|---|---|---|---|---|---|
| 1 | Default-off safety | 35 | 4 (must be set at every launch) | 5 (needs a rebuild) | 5 (two locks) | 2 (persists, easy to forget) |
| 2 | Simplicity | 25 | 5 (one lookup) | 3 (new packaging step) | 2 (two mechanisms) | 4 |
| 3 | Testability | 20 | 5 (a plain mapping) | 3 | 4 | 4 |
| 4 | Bench ergonomics | 10 | 5 | 2 | 3 | 4 |
| 5 | Auditability, no accidental enable | 10 | 3 | 5 | 5 | 2 |
| | **Total / 500** | **100** | **445** | 380 | 385 | 310 |

Sensitivity: with safety at 50 and simplicity at 10, A and C tie at 430; A leads elsewhere.

## Decision

- **A.** `BUSSCOPE_ENABLE_TRANSMISSION=1` enables transmission for that process. Only the exact
  value `1` counts; an absent, empty or `0` value keeps it off, and any other value keeps it off
  with a logged warning.
- When off, the composition root builds neither `SocketCanTransmitter` nor `TransmissionWidget`,
  and the window has no Transmission tab. The listen-only tooltip says
  "Frame transmission is disabled".
- **Fallback: C** (add a packaging flag on top of the variable) if a distributed build must make
  transmission impossible to enable without a rebuild.

## Consequences

- Release and bench builds are listen-only unless the operator sets the variable on purpose.
- The decision is a pure function in the framework-independent `transmission` module.
- When on, the issue #34 safety gates still apply unchanged.
