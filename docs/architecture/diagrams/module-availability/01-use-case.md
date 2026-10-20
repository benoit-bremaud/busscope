# Use-case diagram — module availability

## Context

This diagram scopes the operator goal of inspecting the external voltage and available current
reported by one charger module through Infypower command `0x0C`.

## Diagram

```mermaid
flowchart LR
    Operator[Operator]
    subgraph System[BusScope]
        UC1((Inspect module available output capacity))
        UC2((Identify a powered-off module))
    end
    Operator --> UC1
    Operator --> UC2
    UC2 -. "includes" .-> UC1
```

## Notes

- A zero available current is a documented power-off condition, not automatically a CAN error.
