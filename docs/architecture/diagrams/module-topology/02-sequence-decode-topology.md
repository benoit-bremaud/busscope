# Sequence diagram — module topology decoding

> **Feature**: Issue [#37](https://github.com/benoit-bremaud/busscope/issues/37) — decode Infypower module topology information
> **Source specification**: [`module-topology.md`](../../specs/module-topology.md)

## Context

This sequence shows how the existing pure decoder and presenters collaborate for eligible and
ineligible frames. It specifies no new layer or infrastructure dependency.

## Diagram

```mermaid
sequenceDiagram
    actor Operator
    participant Source as Live capture source
    participant Decoder as ProtocolDecoder
    participant Result as DecodeResult
    participant Presenter as Existing display or CSV presenter

    Source->>Decoder: decode frame
    alt Invalid identifier or payload length is not eight
        Decoder->>Result: preserve frame and diagnostics without topology
    else Command 0x02
        Decoder->>Decoder: read payload byte 2 as unsigned module count
        Decoder->>Result: set module_count
    else Command 0x04
        Decoder->>Decoder: read payload byte 2 as unsigned group number
        Decoder->>Decoder: preserve temperature and state decoding
        Decoder->>Result: set module_group_number, temperature, and state
    else Other valid command
        Decoder->>Result: preserve existing decoded fields without topology
    end
    Decoder-->>Source: immutable result
    Source->>Presenter: present result
    Presenter-->>Operator: show topology when decoded values are enabled
```

## Notes

- `ProtocolDecoder` remains framework- and I/O-independent.
- The existing source and presenter boundaries remain unchanged and depend on the domain result.
- Offline replay decoding is outside this feature and tracked by Issue
  [#40](https://github.com/benoit-bremaud/busscope/issues/40).
- Zero is represented as a decoded integer, while absence is represented by `None`.
- No Strategy, Factory, Repository, or additional service is justified for two fixed command
  branches.
