# Capture analysis specification

> **Feature**: issue #15 — [filter, pause, clear, and export captured CAN frames](https://github.com/benoit-bremaud/busscope/issues/15)

## Scope

This feature improves the read-only capture workflow without changing CAN acquisition or
enabling transmission. The operator can filter the visible history, pause only the display,
clear the visible history, and export the captured records to CSV.

## Decisions

- Filtering applies to the displayed history. Capture remains active and records continue to
  be retained for export.
- Pausing suspends display updates only. It does not stop the capture session.
- The first filter is an exact identifier filter supporting a list of identifiers.
- CSV export includes relative timestamp, CAN metadata, raw payload, decoder description,
  decoded values, and diagnostics.
- Empty captures produce a valid CSV containing the header row.
- Transmission and automatic SocketCAN interface configuration remain out of scope.

## Acceptance criteria

- The operator can enter one or more exact identifiers.
- Invalid identifier input is rejected with an actionable UI message.
- The operator can pause and resume display without stopping capture.
- The operator can clear the visible history without stopping capture.
- CSV export is deterministic and handles empty captures.
- Happy paths, sad paths, and edge cases maintain at least 90% test coverage.
