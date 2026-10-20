# Use-case diagram — module topology decoding

> **Feature**: Issue [#37](https://github.com/benoit-bremaud/busscope/issues/37) — decode Infypower module topology information
> **Source specification**: [`module-topology.md`](../../specs/module-topology.md)

## Context

This diagram scopes the operator goal of inspecting topology information decoded from a live
Infypower frame. It excludes offline replay decoding, active discovery, query transmission, and
UI navigation.

## Diagram

```mermaid
flowchart LR
    Operator((Operator))
    subgraph SYSTEM ["BusScope"]
        subgraph ProtocolAnalysis ["Protocol analysis"]
            UC1(("Inspect module topology"))
        end
    end
    Operator --> UC1
```

## Notes

- The observable outcome is a module count or an individual module group number.
- Offline replay decoding is outside this feature and tracked by Issue
  [#40](https://github.com/benoit-bremaud/busscope/issues/40).
- No component, class, state, or data-flow diagram is warranted: the feature adds no boundary,
  lifecycle, sensitive data flow, or complex type relationship.
