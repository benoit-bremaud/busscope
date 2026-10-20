# Class diagram — module measurements

> **Feature**: issue #3 — [Decode individual charger module measurements](https://github.com/benoit-bremaud/busscope/issues/3)
> **Source specs**: `docs/architecture/specs/module-measurements.md`

## Context

This class view defines the typed output for command `0x03` while reusing the common decoded
identifier for the module address.

## Diagram

```mermaid
classDiagram
    class ModuleMeasurements {
        +float output_voltage_volts
        +float output_current_amperes
    }
    class CanFrame {
        +int arbitration_id
        +bytes data
        +bool is_extended_id
        +bool is_error_frame
    }
    class DecodeResult {
        +CanFrame frame
        +ModuleMeasurements module_measurements
        +tuple diagnostics
    }
    DecodeResult *-- CanFrame
    DecodeResult o-- ModuleMeasurements
```

## Notes

- Units are part of field names to keep UI and exports unambiguous.
- The module identity is represented by `InfypowerIdentifier.destination_address`.
- `DecodeResult` always preserves the raw frame, including when diagnostics are present.
