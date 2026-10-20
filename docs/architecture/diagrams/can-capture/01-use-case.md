# Use-case diagram — CAN capture

## Context

This diagram scopes the operator goal of starting and stopping a read-only CAN capture. It does
not describe the future graphical layout.

## Diagram

```mermaid
flowchart LR
    Operator[Operator]
    subgraph System[BusScope]
        UC1((Start a read-only CAN capture))
        UC2((Stop a CAN capture))
        UC3((Inspect a capture error))
    end
    Operator --> UC1
    Operator --> UC2
    Operator --> UC3
    UC3 -. "extends" .-> UC1
```

## Notes

- Listen-only is mandatory for the first adapter implementation.
- Adapter failures must be observable and must not be silently swallowed.
