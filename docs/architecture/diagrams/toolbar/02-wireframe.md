# Wireframe — capture toolbar

> **Feature**: issue #69. Icons are placeholders; tooltips give the text and shortcut.

## Live · Idle

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ [ Live | Replay ]  Backend [socketcan▾] Channel [can0]  Filter [_______]   │
│ (⏺)  (🗑) (💾)                                (● Idle)  🔒 Listen-only  (⋯) │
└────────────────────────────────────────────────────────────────────────────┘
```

## Live · Listening

```text
│ [ Live | Replay ]  Backend [socketcan▾] Channel [can0]  Filter [_______]   │
│ (⏹) (❄)  (🗑) (💾)                       (● Listening) 🔒  (⋯)    │
```

## Replay · Paused

```text
│ [ Live | Replay ]  capture-2026-10-20.csv                Filter [_______]   │
│ (▶) (⏹)  (💾)                                    (● Paused)     🔒  (⋯)     │
```

Overflow `(⋯)`: Refresh statistics · Reset replay (Replay mode only).

Tooltips: `Start capture (Space)`, `Stop capture (Space)`, `Freeze display`, `Clear frames (Ctrl+L)`,
`Export CSV (Ctrl+E)`, `Play replay (Space)`, `Pause replay (Space)`, `Stop replay`,
`Load CSV (Ctrl+O)`; Ctrl+M switches mode.

Icons: Lucide (lucide-static 0.460.0, ISC), bundled in `src/busscope/icons/` and recoloured
from the palette so they follow light and dark themes. The same glyphs exist in `lucide-react`
for the future UI (ADR-0006).
