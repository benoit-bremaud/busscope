# Class diagram — manual transmission — request, port, and adapters

> **Feature**: issue #34 — [add safe manual CAN frame transmission](../../specs/manual-transmission.md)
> **Source specs**: `docs/architecture/specs/manual-transmission.md` §D4, §D5, §D6, §D7
> **Decisions captured**: D4, D5, D6, D7

## Context

This class view defines the minimum types needed to validate one request and substitute the
hardware boundary in tests. It deliberately excludes command builders, queues, schedulers, and a
general transmission service.

## Diagram

```mermaid
classDiagram
    class ManualTransmission {
        <<immutable>>
        +string channel
        +int arbitration_id
        +bytes payload
        +from_text(channel, identifier, payload) ManualTransmission
        +identifier_hex string
        +payload_hex string
    }

    class CanTransmissionPort {
        <<protocol>>
        +send(request) None
    }

    class CanInterfaceReadinessPort {
        <<protocol>>
        +ensure_ready(channel) None
    }

    class SocketCanTransmitter {
        +send(request) None
    }

    class IpLinkCanInterfaceInspector {
        +ensure_ready(channel) None
    }

    class TransmissionWidget {
        +bool transmission_enabled
        +send_once() None
    }

    class CaptureWindow {
        +add transmission tab
    }

    class TransmissionBus {
        <<protocol>>
        +send(message, timeout) None
        +shutdown() None
    }

    CanTransmissionPort <|.. SocketCanTransmitter
    CanInterfaceReadinessPort <|.. IpLinkCanInterfaceInspector
    SocketCanTransmitter --> CanInterfaceReadinessPort
    TransmissionBus <-- SocketCanTransmitter
    SocketCanTransmitter --> ManualTransmission
    TransmissionWidget --> ManualTransmission
    TransmissionWidget --> CanTransmissionPort
    CaptureWindow o-- "0..1" TransmissionWidget : only when the kill switch is on (ADR-0009)
```

## Notes

- `ManualTransmission.from_text()` owns parsing and all protocol-structural validation.
- `TransmissionWidget` sends the validated instance that it displayed for confirmation.
- `CaptureWindow` hosts the widget but does not receive `CanTransmissionPort` itself.
- `CanTransmissionPort` exists for the real fake-hardware test seam required by safety tests.
- `CanInterfaceReadinessPort` lets the transmitter fail closed before opening a hardware socket;
  its Linux adapter performs one read-only inspection and never configures the interface.
- `TransmissionBus` is the smallest python-can-facing contract needed to test resource cleanup and
  exact send semantics without a physical interface.
- No service class merely forwards from the widget to the port.
