# Offline replay specification

> **Feature**: issue #19 — [replay exported CAN captures offline](https://github.com/benoit-bremaud/busscope/issues/19)
>
> **Semantic decoding extension**: issue #40 — [preserve decoded protocol values](https://github.com/benoit-bremaud/busscope/issues/40)

## Scope

This feature loads BusScope CSV exports and replays their retained records locally. It uses
the existing display and statistics workflow without opening SocketCAN or transmitting frames.

## Decisions

- The loader accepts the CSV header produced by `CsvExporter`.
- Rows are validated before replay starts.
- Replay preserves CSV row order and uses `timestamp_seconds` as relative timing.
- The first record is immediately available; subsequent records become available when their
  relative timestamp is reached.
- Empty captures are valid and produce an empty replay.
- After validating a row, the loader creates its `CanFrame` and passes it once to the pure
  `ProtocolDecoder`. The returned identifier and semantic protocol values become the replay
  result.
- The raw CAN frame is the only machine-readable source for protocol decoding. The human-readable
  `decoded_values` CSV column is accepted for format compatibility but never parsed or trusted.
- The loader preserves the CSV `description` field instead of replacing it with the current
  decoder description.
- Final diagnostics contain the current decoder diagnostics first, followed by stored CSV
  diagnostics that are not already present. This preserves current safety warnings and historical
  context without duplicates.
- Semantic decoding happens during loading. `ReplayController` receives already decoded records
  and remains responsible only for deterministic playback timing.
- The eight-column CSV header and row format remain unchanged, so existing valid exports stay
  loadable.
- Replay controls are local playback controls and cannot access the CAN port.

## Acceptance criteria

- Valid exported CSV files load successfully.
- Empty captures load successfully.
- Invalid headers, identifiers, payloads, timestamps, and boolean metadata produce actionable
  errors.
- Supported Infypower frames restore the same identifier and semantic values as live decoding,
  including measurements, state, ratings, availability, and module topology.
- Stored `description` survives loading unchanged. Stored diagnostics remain available without
  duplicating current decoder diagnostics, and current decoder diagnostics are never discarded.
- Stale, empty, or arbitrary `decoded_values` content does not influence the decoded result.
- Standard, CAN error, unsupported, and incomplete frames retain safe decoder behavior without
  gaining semantic values that their raw frame does not support.
- Replay preserves ordering and relative timing.
- Play, pause, stop, and reset are deterministic.
- Live capture, filtering, statistics, and export remain unchanged.
- Happy paths, sad paths, and edge cases maintain at least 90% test coverage.

## Design rationale

`CsvCaptureLoader` depends directly on `ProtocolDecoder` because the decoder is a pure inward
domain dependency, not an infrastructure detail. A decoder port, factory, strategy, or new service
would have one implementation and no testability benefit, so it is deliberately omitted.

Decoding in the UI would move protocol behavior into the framework boundary. Decoding on every
replay tick would repeat deterministic work. Serializing every domain field would duplicate the
protocol model in the CSV schema. Load-time decoding from the raw frame is therefore the smallest
design that preserves Clean dependency direction, DRY, and future decoder compatibility.

## Test strategy

| Category | Required evidence |
| --- | --- |
| Happy path | Export and reload each supported command, then compare its semantic result with direct `ProtocolDecoder` output |
| Sad path | Invalid rows still fail before replay; standard, CAN error, unsupported, and incomplete raw frames retain current decoder diagnostics and gain no unsupported semantic values |
| Edge cases | Empty captures remain valid; arbitrary `decoded_values` is ignored; stored description and diagnostics are preserved; duplicate diagnostics occur only once |
| Integration | The UI displays restored topology from a loaded replay without opening SocketCAN |
| Regression | Replay timing, filtering, statistics, export, and all existing protocol tests remain green |

Total project coverage must remain at least 90%, and pytest, Ruff, and strict mypy must pass.
