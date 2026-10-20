# Use-case diagram — module ratings

## Context

This diagram scopes the operator goal of inspecting the nominal electrical ratings reported by
one charger module through Infypower command `0x0A`.

## Diagram

```mermaid
flowchart LR
    Operator[Operator]
    subgraph System[BusScope]
        UC1((Inspect module ratings))
        UC2((Inspect an invalid rating frame))
    end
    Operator --> UC1
    Operator --> UC2
    UC2 -. "extends" .-> UC1
```

## Notes

- The decoder exposes values with explicit units.
- Invalid payloads keep their raw frame and diagnostics.
