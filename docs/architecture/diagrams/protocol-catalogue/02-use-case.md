# Protocol catalogue — use cases

```mermaid
flowchart LR
    op([Operator])
    subgraph Capture setup
        uc1((Find a protocol to test))
        uc2((Choose capture source and protocol))
        uc3((Set transport parameters))
        uc4((Start listen-only capture))
    end
    op --> uc1
    op --> uc2
    op --> uc4
    uc2 -. include .-> uc3
    uc1 -. extend .-> uc2
```

- **Find a protocol to test**: browse families / sub-families or type a search; planned
  protocols are shown greyed with their status.
- **Choose capture source and protocol**: only *available* protocols can be selected.
- **Set transport parameters**: fields depend on the protocol's transport (CAN → backend,
  channel, bitrate, ID filter).
- **Start listen-only capture**: unchanged; no transmit path is added.
