# Use-case diagram — system measurements

## Context

This diagram scopes the operator goal of inspecting the charger system output measurements
from a valid Infypower command `0x01` response.

## Diagram

```mermaid
flowchart LR
    Operator[Operator]
    subgraph System[BusScope]
        UC1((Inspect system output measurements))
        UC2((Inspect an undecodable measurement frame))
    end
    Operator --> UC1
    Operator --> UC2
    UC2 -. "extends" .-> UC1
```

## Notes

- The raw eight-byte payload remains available beside decoded values.
- A `0x01` frame with invalid payload length is diagnostic, not silently accepted.
