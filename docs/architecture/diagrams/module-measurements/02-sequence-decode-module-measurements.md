# Sequence diagram — module measurements — command 0x03

> **Feature**: issue #3 — [Decode individual charger module measurements](https://github.com/benoit-bremaud/busscope/issues/3)
> **Source specs**: `docs/architecture/specs/module-measurements.md`

## Context

This sequence defines the pure decoding path for voltage and current in a valid command `0x03`
response. Invalid frame metadata and payload length are preserved as diagnostics.

## Diagram

```mermaid
sequenceDiagram
    participant Decoder as Protocol decoder
    participant Measurements as Module measurement decoder
    participant Result as Module measurements

    Decoder->>Measurements: decode(payload[0:8])
    alt payload has 8 bytes and command is 0x03
        Measurements->>Measurements: read voltage bytes 0 to 3
        Measurements->>Measurements: read current bytes 4 to 7
        Measurements->>Result: create immutable measurements
        Result-->>Decoder: voltage and current
    else invalid metadata or payload
        Measurements-->>Decoder: preserve frame and add diagnostic
    end
```

## Notes

- The protocol example contains voltage in bytes 0 to 3 and current in bytes 4 to 7.
- Both values are big-endian IEEE-754 binary32 values.
