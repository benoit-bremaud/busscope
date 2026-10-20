# Module topology decoding

> **Status**: implemented for Issue [#37](https://github.com/benoit-bremaud/busscope/issues/37)
>
> **Protocol reference**: *Charger module CAN Communication Protocol V1.13*, commands
> `0x02` and `0x04`

## Goal

Allow an operator to identify how many Infypower charger modules report belonging to a
system or group and to identify the group number reported by an individual module. The
feature extends passive decoding only: it never discovers devices actively and never sends
a CAN frame.

## Scope

- Decode the reported module count from byte 2 of a valid command `0x02` response.
- Decode the module group number from byte 2 of a valid command `0x04` response.
- Preserve the existing ambient-temperature and state decoding for command `0x04`.
- Surface both values through the existing live-capture display and CSV-analysis paths.

Module discovery, topology history, change detection, query transmission, module versions,
extended diagnostics, and barcode decoding are outside this feature.

Offline replay continues to preserve raw frame metadata, description, and diagnostics without
re-decoding semantic protocol values. Restoring all supported decoded values during replay is
tracked separately by Issue [#40](https://github.com/benoit-bremaud/busscope/issues/40).

## Protocol interpretation

Semantic decoding is allowed only when the existing identifier validation succeeds and the
payload contains exactly eight bytes.

| Command | Payload byte 2 | Context retained from the identifier |
| --- | --- | --- |
| `0x02` | Unsigned module count in the addressed system or group | Device number and source address distinguish system and group responses |
| `0x04` | Unsigned group number reported by the source module | Source address identifies the reporting module |

Values are decoded as unsigned bytes. Therefore, the decoder accepts the complete wire range
from 0 through 255 without adding a stricter rule that the protocol does not state for these
response fields. Reserved payload bytes remain uninterpreted.

## Domain design

`DecodeResult` remains the immutable aggregate returned by the pure `ProtocolDecoder`. It gains
two optional scalar fields:

- `module_count: int | None`
- `module_group_number: int | None`

For command `0x02`, only `module_count` is populated. For command `0x04`, only
`module_group_number` is populated. Other commands and invalid payload lengths leave both
fields unset.

A separate topology entity, service, repository, factory, or protocol interface is deliberately
not introduced. The feature adds two independent scalar facts to an existing immutable result,
has no new I/O boundary, and requires no runtime variation. Direct fields are therefore the
smallest design that preserves type clarity and the Clean Architecture dependency rule.

## Presentation

When decoded-value display is enabled, the existing presentation paths append stable labels:

- `Modules=<count>` for command `0x02`;
- `Group=<number>` for command `0x04`.

The group label appears before the existing ambient-temperature and state information for a
command `0x04` result. Numeric precision settings do not affect integer topology values. When
decoded-value display is disabled, no topology label is shown, while the retained
`DecodeResult` remains unchanged.

## Error handling

- Invalid, standard, or CAN error frames retain the existing diagnostics and expose no topology
  values.
- Payloads shorter or longer than eight bytes retain the existing payload-length diagnostic and
  expose no topology values.
- Unsupported commands remain valid generic Infypower results but expose no topology values.
- A zero value is valid wire data and must not be confused with a missing value.

## Test strategy

Fast, isolated unit tests exercise the pure decoder and existing presenters without CAN hardware
or mocks of domain code.

| Category | Required evidence |
| --- | --- |
| Happy path | Documented system count 7, documented group count 3, and command `0x04` group 2 with ambient temperature 27 °C and existing state decoding preserved |
| Sad path | Short and oversized payloads expose neither topology field and retain diagnostics; unrelated commands expose neither field |
| Edge cases | Counts and group numbers 0 and 255 remain unsigned and distinguishable from `None`; decoded-value hiding suppresses labels |
| Regression | Existing protocol, live display, replay timing, CSV export, state, and temperature tests remain green |

Total project coverage must remain at least 90%, and pytest, Ruff, and strict mypy must pass.

## Traceability

| Requirement | Design realization | Verification |
| --- | --- | --- |
| Decode command `0x02` count | `DecodeResult.module_count` and the `0x02` decoder branch | Protocol happy-path and boundary tests |
| Complete command `0x04` topology | `DecodeResult.module_group_number` in the existing `0x04` branch | Combined group, temperature, and state test |
| Preserve Clean dependencies | Pure decoder result consumed by existing presenters | Import review and unit tests without infrastructure |
| Fail safely | Exact payload-length gate before semantic decoding | Short and oversized payload tests |
| Avoid speculative design | No new boundary, service, or pattern | Architecture review |
