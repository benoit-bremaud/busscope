# Use-case diagram — offline replay

> **Feature**: issues #19 and #40 — [replay exported CAN captures offline with semantic decoding](../../specs/offline-replay.md)

## Context

This diagram identifies the operator goals for loading and replaying a saved capture locally.
Semantic values are restored from each raw frame before playback. The system boundary explicitly
excludes CAN transmission.

## Diagram

```mermaid
flowchart LR
    Operator((Operator))
    subgraph SYSTEM ["BusScope"]
        subgraph OfflineReplay ["Offline replay"]
            UC1(("Load a saved capture"))
            UC2(("Replay a decoded capture"))
            UC3(("Control replay playback"))
        end
    end
    Operator --> UC1
    Operator --> UC2
    Operator --> UC3
```

## Notes

- Replay is a local file operation.
- Loading restores semantic values from raw frames without parsing presentation text.
- Pause, stop, and reset are playback controls under one operator goal, not separate use cases.
- No use case opens SocketCAN or sends a frame.
