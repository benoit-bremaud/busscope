# Protocol catalogue — network-neutral capture wireframe

```text
┌ Capture ───────────────────────────────────────────────────────────────┐
│ [toolbar: ▶ ■ ❄ 💾 …]                                                  │
│ Protocol  [🔍 search…            ]                                     │
│  ▾ Fieldbus                                                            │
│     ▾ CAN                                                              │
│        ● CAN 2.0B (extended)          available                        │
│        ○ J1939                        planned   (on CAN 2.0B)          │
│  ▸ Serial / industrial                                                 │
│  ▸ EV charging                                                         │
│  ▸ Generic logic tap                                                   │
│ ─ Selected: CAN 2.0B — Extended 29-bit identifiers, 125 kbit/s…        │
│ ┌ CAN settings (shown only for CAN transport) ───────────────────────┐ │
│ │ Backend [socketcan▾]  Channel [can0]  ID filter [        ]          │ │
│ └────────────────────────────────────────────────────────────────────┘ │
│ Listen-only ✓ (fixed)                                                  │
│ [frame table …]                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

Behaviour: tree filters live on search; planned protocols are disabled (tooltip = status);
the settings group swaps by `Protocol.transport` (only the CAN group exists in this PR; other
groups are follow-up issues).
