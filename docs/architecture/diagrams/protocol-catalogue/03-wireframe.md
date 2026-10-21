# Protocol catalogue — network-neutral capture wireframe

```text
┌ Capture ───────────────────────────────────────────────────────────────┐
│ [toolbar: ▶ ■ ❄ 💾 …]                                                  │
│ [Protocol: CAN 2.0B ▾]   ← click opens the popup below                 │
│   ┌ popup ─────────────────────────────┐                               │
│   │ [🔍 search…            ]           │                               │
│   │ ▾ Fieldbus                         │                               │
│   │   ▾ CAN                            │                               │
│   │      ● CAN 2.0B        available   │                               │
│   │      ○ J1939           planned     │                               │
│   │ ▸ Serial / industrial  …           │                               │
│   └────────────────────────────────────┘                               │
│ ┌ CAN settings (shown only for CAN transport) ───────────────────────┐ │
│ │ Backend [socketcan▾]  Channel [can0]  ID filter [        ]          │ │
│ └────────────────────────────────────────────────────────────────────┘ │
│ Listen-only ✓ (fixed)                                                  │
│ [frame table …]                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

Behaviour: the popup closes on click or Enter on an available protocol (arrow keys only browse); the tree filters live on search; planned protocols are disabled (tooltip = status);
the settings group swaps by `Protocol.transport` (only the CAN group exists in this PR; other
groups are follow-up issues).
