# Architecture Decision Records

Nygard format, one file per decision, `ADR-NNNN-<slug>.md`. A decision is changed only by a
superseding ADR. Every ADR records the options studied and the weighted scoring (MCDA, weights
summing to 100, scores 0–5, totals out of 500) that led to the choice, and names the runner-up
kept as the fallback, so the reasoning can be re-examined when the context changes.

Decisions taken before this register existed stay in
[`docs/architecture/decisions.md`](../architecture/decisions.md), which is now frozen.

The project name is still open; ADRs say "the project" until it is chosen.

| ADR | Title | Status |
|-----|-------|--------|
| [0001](ADR-0001-adr-register.md) | Adopt an ADR register; freeze the historical decision log | Accepted |
| [0002](ADR-0002-product-scope-multibus-listen-only-box.md) | Product scope: a multi-bus, listen-only capture box driven by one desktop application | Accepted |
| [0003](ADR-0003-mcu-stm32g474.md) | Box MCU: STM32G474, STM32H723 as fallback | Accepted |
| [0004](ADR-0004-monorepo.md) | One repository for board, firmware, core and UI | Accepted |
| [0005](ADR-0005-electronics-and-enclosure-toolchain.md) | Toolchain: KiCad, ngspice, FreeCAD scripted in Python | Accepted |
| [0006](ADR-0006-ui-electron-react-python-core.md) | UI: Electron + React over the existing Python core | Accepted, pending the throughput spike |
| [0007](ADR-0007-ai-agent-read-only-mcp.md) | AI agent: a read-only MCP server in the Python core | Accepted |
| [0008](ADR-0008-signal-level-tooling.md) | Signal-level tooling: FX2 + PulseView through an isolated logic tap, Analog Discovery 3 later | Accepted |
