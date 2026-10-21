# Minimal contextual UI — wireframe per state

`✓` visible, `·` hidden. Frames table and status bar are always present. Once a source is
chosen, the toolbar actions inside it follow the existing rules of `toolbar.py` (#69).

| Control | NoProtocol | ProtocolChosen | LiveIdle | Capturing | ReplayIdle | Replaying |
| --- | --- | --- | --- | --- | --- | --- |
| Protocol picker | ✓ | ✓ | ✓ | ✓ locked | ✓ | ✓ locked |
| Listen-only badge | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Live / Replay switch | · | ✓ if both sources | ✓ | ✓ disabled | ✓ | ✓ disabled |
| Backend (socketcan/slcan) | · | · | ✓ `CAN_BACKEND` | ✓ locked | · | · |
| Channel | · | · | ✓ `CAN_CHANNEL` | ✓ locked | · | · |
| Accept unverified silence | · | · | ✓ only slcan | ✓ locked, only slcan | · | · |
| Toolbar (Start/Stop, Load/Play, Freeze, Clear, Export) | · | · | ✓ | ✓ | ✓ | ✓ |
| ID filter | · | · | ✓ `CAN_FILTER` | ✓ | ✓ `CAN_FILTER` | ✓ |
| Statistics panel | · | · | ✓ `STATISTICS` + pref | ✓ | ✓ `STATISTICS` + pref | ✓ |

```text
NoProtocol                         LiveIdle (slcan)
┌──────────────────────────────┐   ┌──────────────────────────────────────────────────┐
│ [ Protocol ▾ ]   🔒Listen-only │   │ [CAN 2.0B ▾] (Live|Replay) [slcan▾] [/dev/ttyACM0]│
│                              │   │ ☐ Accept unverified silence           [▶ Start]  │
│   Pick a protocol to begin   │   │                                                  │
└──────────────────────────────┘   └──────────────────────────────────────────────────┘
```

Filter and statistics appear as soon as a source is chosen and the protocol resolves them
(owner decision 2026-10-21, MCDA 420 vs 410): discoverable before the first frame.
