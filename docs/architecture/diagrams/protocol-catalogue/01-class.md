# Protocol catalogue — class diagram

Qt-free registry (`src/busscope/protocol_catalogue.py`), immutable data, reusable by the future
React UI (ADR-0006) through a plain dict/JSON export.

```mermaid
classDiagram
    class Transport {
        <<enumeration>>
        CAN
        SERIAL
        ETHERNET
        CONTROL_PILOT
        POWERLINE
        LOGIC
    }
    class Availability {
        <<enumeration>>
        AVAILABLE
        PLANNED
    }
    class Family {
        +key: str
        +name: str
        +sub_families: tuple[SubFamily, ...]
    }
    class SubFamily {
        +key: str
        +name: str
        +protocols: tuple[Protocol, ...]
    }
    class Protocol {
        +key: str
        +name: str
        +description: str
        +transport: Transport
        +availability: Availability
        +carried_by: str | None
        +keywords: tuple[str, ...]
        +matches(text) bool
    }
    class ProtocolCatalogue {
        +families: tuple[Family, ...]
        +protocols() tuple[Protocol, ...]
        +get(protocol_key) Protocol
        +search(text) tuple[Protocol, ...]
        +to_dict() dict
    }
    ProtocolCatalogue "1" o-- "*" Family
    Family "1" *-- "*" SubFamily
    SubFamily "1" *-- "*" Protocol
    Protocol --> Transport
    Protocol --> Availability
    Protocol ..> Protocol : carried_by (stacking)
```

Invariants: keys unique across the catalogue; `carried_by` names an existing protocol; no
cycles; `search` matches name, description and keywords case-insensitively.
