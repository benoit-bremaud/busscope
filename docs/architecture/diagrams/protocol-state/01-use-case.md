# Use-case diagram — module state decoding

## Context

This diagram scopes the operator goal of identifying charger module health from a received
command `0x04` response. It does not model UI navigation or hardware access.

## Diagram

```mermaid
flowchart LR
    Operator[Operator]
    subgraph System[BusScope]
        UC1((Inspect a module state))
        UC2((Identify an active module fault))
    end
    Operator --> UC1
    Operator --> UC2
    UC2 -. "includes" .-> UC1
```

## Notes

- Every documented state bit must be represented by a stable, named result.
- A frame with no active bits is valid and must not be treated as an error.
