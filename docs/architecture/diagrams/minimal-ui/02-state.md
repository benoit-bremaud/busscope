# Minimal contextual UI — progressive disclosure state diagram

A control is shown only when the chosen protocol resolves the matching `Feature`
**and** the current state allows it. Listen-only stays the only capture mode.

```mermaid
stateDiagram-v2
    [*] --> NoProtocol
    NoProtocol --> ProtocolChosen : pick AVAILABLE protocol
    ProtocolChosen --> LiveIdle : choose Live [LIVE_SOURCE]
    ProtocolChosen --> ReplayIdle : choose Replay [REPLAY_SOURCE]
    LiveIdle --> ReplayIdle : switch source
    ReplayIdle --> LiveIdle : switch source
    LiveIdle --> Capturing : Start [backend + channel set]
    Capturing --> LiveIdle : Stop / poll error
    ReplayIdle --> Replaying : Load CSV + Play
    Replaying --> ReplayIdle : Stop / finished
    LiveIdle --> ProtocolChosen : change protocol [source not offered]
    ReplayIdle --> ProtocolChosen : change protocol [source not offered]
```

Notes:

- The protocol picker is locked while a source feeds the view (`Capturing`, `Replaying`).
- There is no way back to `NoProtocol`: a protocol, once picked, can only be changed.
- Changing protocol keeps the current source when the new protocol offers it.
- A protocol with a single source skips the choice: `ProtocolChosen` goes straight to it.
- `Accept unverified silence` lives inside `LiveIdle` and only when backend = slcan.
