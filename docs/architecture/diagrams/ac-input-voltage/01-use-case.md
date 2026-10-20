# Use-case diagram — module AC input voltage

## Context

This diagram scopes the operator goal of inspecting the AC input voltages reported by one
charger module through Infypower command `0x06`.

## Diagram

```mermaid
flowchart LR
    Operator[Operator]
    subgraph System[BusScope]
        UC1((Inspect module AC input voltages))
        UC2((Inspect an invalid AC measurement frame))
    end
    Operator --> UC1
    Operator --> UC2
    UC2 -. "extends" .-> UC1
```

## Notes

- The decoder must expose the raw integer values and their 0.1 V interpretation.
- Single-phase and three-phase responses share the same command and payload shape.
