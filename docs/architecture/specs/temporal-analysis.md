# Temporal analysis specification

> **Feature**: issue #17 — [temporal analysis of captured CAN frames](https://github.com/benoit-bremaud/busscope/issues/17)

## Scope

This feature summarizes retained read-only capture records by exact CAN identifier. It helps
the operator understand message cadence without changing acquisition or enabling transmission.

## Decisions

- Statistics use the retained records and their relative timestamps.
- Each identifier reports its count, first timestamp, last timestamp, observed period, and
  estimated frequency.
- The observed period is the elapsed time between the first and last occurrence divided by
  `count - 1` when an identifier appears at least twice.
- The estimated frequency is the inverse of the observed period when that period is positive.
- A single occurrence has no observed period and no estimated frequency.
- Non-positive or non-monotonic elapsed time produces no period or frequency rather than an
  invalid or infinite value.
- Statistics are independent of the visible identifier filter and remain available while the
  capture session is active.

## Acceptance criteria

- The operator can refresh statistics from retained records.
- Statistics are grouped by exact arbitration identifier.
- Single occurrences and zero-duration captures are handled safely.
- Non-monotonic timestamps do not produce misleading frequency values.
- Existing filtering, pause, clear, and CSV export behavior remains unchanged.
- Happy paths, sad paths, and edge cases maintain at least 90% test coverage.
