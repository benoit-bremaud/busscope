# Use-case diagram — protocol decoder

## Context

This diagram defines the operator goal for inspecting charger frames. It does not describe
internal modules or the graphical navigation.

## Diagram

```mermaid
flowchart LR
    Operator[Operator]
    subgraph System[BusScope]
        UC1((Inspect a received CAN frame))
        UC2((Identify charger faults))
        UC3((Inspect an unknown frame))
    end
    Operator --> UC1
    Operator --> UC2
    Operator --> UC3
    UC2 -. "includes" .-> UC1
    UC3 -. "extends" .-> UC1
```

## Notes

- The decoder must preserve the raw frame when a protocol field is unknown or invalid.
- Fault identification is an observable result of inspecting a frame, not a background actor.
