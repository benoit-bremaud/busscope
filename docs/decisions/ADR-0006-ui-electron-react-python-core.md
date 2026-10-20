# ADR-0006: UI — Electron + React over the existing Python core

**Status:** Accepted, pending the throughput spike — 2026-10-19

## Context

The application is a PySide6 desktop UI over a tested Python core: capture adapters, Infypower
decoders, statistics, CSV replay, 210 tests at 97 % coverage. The owner wants the user interface
built like their dock-n-roll project — Electron, React, TypeScript, a GNOME tray entry, a
dashboard, live logs, a hardened IPC and a `.deb` package — and wants logs, editable reports and
an AI agent link (ADR-0007). The UI must show live frame tables of tens of thousands of rows,
charts, logs and a report editor.

Verified on 2026-10-19: the npm `socketcan` package is maintained (4.3.2) and `serialport` 13
covers slcan; Electron 44.9 and Tauri 2.12 are both current; the MCP SDK exists in Python and
TypeScript; PySide6 alone weighs 650 MB in the current virtual environment, while the dock-n-roll
`.deb` weighs 95 MB.

## Options and scoring

| # | Criterion | Weight | PySide6 | PySide6 + QML | **Electron + Python core** | Electron, all TS | Local web app | Tauri + Python core |
|---|---|---|---|---|---|---|---|---|
| 1 | Consistency with dock-n-roll | 20 | 1 | 1 | 5 | 5 | 3 | 3 |
| 2 | Reuse of the tested Python core | 20 | 5 | 5 | 5 | 0 | 5 | 5 |
| 3 | Hardware access | 15 | 5 | 5 | 4 | 4 | 4 | 4 |
| 4 | UI richness | 15 | 3 | 4 | 5 | 5 | 5 | 5 |
| 5 | AI agent link | 10 | 4 | 4 | 5 | 4 | 5 | 5 |
| 6 | Packaging and security | 10 | 3 | 3 | 5 | 5 | 3 | 5 |
| 7 | Simplicity | 10 | 5 | 4 | 2 (two languages) | 4 | 3 | 1 (three languages) |
| | **Total / 500** | **100** | 360 | 365 | **455** | 365 | 405 | 405 |

Doubling simplicity (taken from consistency) keeps Electron first: 425 against 405 for the local
web app (PySide6 400).

## Decision

**Electron + React + TypeScript for the UI, the existing Python core kept as a local service.**
Electron's main process starts the core as a child process; the renderer talks to it through a
minimal preload API; the core alone opens hardware and captures listen-only by default. The guarded single-frame
transmission of 2026-09-04 stays a valid decision and remains in the current PySide6 application;
it is not exposed in the new UI until a dedicated ADR ports it with the same safeguards; on the box it stays
impossible while transmit paths are disabled in hardware. Commands use
JSON-RPC; frames are streamed in batches (about every 50 ms), never one message per frame.

**Fallback: the local web app** — same core, same React, without Electron — reachable without
rewriting the UI.

## Consequences

- **Gate:** a throwaway spike must show the core-to-UI link sustaining about 50 000 frames/s into
  a virtualised table before detailed design. If it fails, this ADR is reopened and the local web app
  fallback is evaluated first.
- PySide6 leaves the core's dependencies once the Electron UI reaches parity.
- The core-to-UI protocol is a second contract next to the box's USB protocol; both are specified
  and versioned.
- Live logs, session recording and the report editor are UI features over core services.
