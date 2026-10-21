# UI benchmark — protocol selection in PulseView, Wireshark and Modbus masters

Issue: #72. Date: 2026-10-20. Purpose: decide how BusScope lets the operator pick *what* to
listen to (source + protocol) before showing network-specific settings.

Evidence levels: **[verified]** = official docs / tool already used on this machine;
**[est.]** = community sources or recollection, to be confirmed with screenshots on the bench.

## PulseView (sigrok)

| Observation | Level |
|---|---|
| Decoders are added from a toolbar button opening a **filterable list** of decoders, each with a one-line description; selection then asks which channels feed it. | verified (installed, ADR-0008) |
| Decoders **stack** (e.g. nRF905 on SPI, rtc8564 on I²C); `sigrok-cli -P i2c,rtc8564 -S i2c,rtc8564`. Only the top decoder's annotations show by default. | verified ([sigrok-cli man page](https://manpages.org/sigrok-cli)) |
| The list is flat (≈ 130 decoders, alphabetical) — finding "the CAN one" is easy, finding "anything EV-charging" is not. | verified |

**Borrow:** search-as-you-type over name + description; protocol stacking as a model concept
(J1939 *on* CAN 2.0B, Modbus RTU *on* UART).
**Avoid:** flat alphabetical list without grouping; channel wiring as a modal step before data.

## Wireshark

| Observation | Level |
|---|---|
| Three panes: packet list / details tree (one node per protocol layer) / raw bytes. | verified ([User's Guide](https://www.wireshark.org/docs/wsug_html/)) |
| Display-filter bar with protocol-qualified fields (`can.id == 0x18ff50e5`), autocompletion, saved filters. | verified (guide ch. 6) |
| *Statistics → Protocol Hierarchy* (guide §8.4): tree of protocols actually seen, with packet / byte share. | verified |
| Capture interface is chosen first; protocol is *inferred* by dissectors, not chosen. | verified |

**Borrow:** layered details tree; protocol-qualified filter syntax later; a "protocols seen"
hierarchy as the natural reuse of our family tree.
**Avoid:** relying on inference only — on a raw CAN or RS-485 bus nothing tells us the
application protocol, so BusScope must let the operator choose it.

## Modbus masters (Doctor Modbus, Modbus Poll, ModbusScope)

"Doctor Modbus" has no official page we could find; observations below come from comparable
tools and are **[est.]** until we have the actual binary.

| Observation | Level |
|---|---|
| Named **connection profiles** (RTU: port, baud, parity, stop bits; TCP: host, port, unit id). | est. |
| Explicit **role** (master/poller vs slave/simulator) — we only ever *sniff*: role = listen-only. | est. |
| **Register tables** per function code (coils, discrete inputs, input/holding registers). | verified (Modbus spec) |

**Borrow:** saved connection profiles per transport; tabular view of decoded values.
**Avoid:** anything that polls or writes — BusScope is listen-only (ADR-0002).

## CAN-specific tools (added after the #72 critical review)

| Tool | Observation | Level |
|---|---|---|
| SavvyCAN | *Connection window* lists devices per driver; each bus enabled with its own bitrate (multi-bus). Main view toggles: auto-scroll, **overwrite mode** (one line per ID, latest frame), interpret frames (DBC), frame filtering by ID. | verified ([CSS Electronics guide](https://canlogger.csselectronics.com/canmod-intro/software-tools/savvycan), [man page](https://dyn.manpages.debian.org/unstable/savvycan/SavvyCAN.1)) |
| PCAN-View | **Connect dialog** = interface + bitrate + **listen-only checkbox** in one place; sortable receive list, hex/decimal IDs. | verified ([PEAK product page](https://www.peak-system.com/products/software/analysis-software/pcan-view/?L=1)) |
| Saleae Logic 2 | Analyzers added from a "+" in a side panel; one **data table** of all decoded analyzers, searchable, with per-analyzer exclusion. | data table verified ([Saleae guide](https://support.saleae.com/user-guide/using-logic/data-table-and-terminal)); "+" flow est. |

**Borrow:** compact source + protocol picker that opens on demand (PCAN-View connect, PulseView
decoder popup) instead of a permanent tree; overwrite mode per ID (SavvyCAN) as a follow-up;
one searchable decoded-data table across protocols (Saleae).
**Avoid:** transmit lists and periodic sending (PCAN-View) — out of scope, listen-only.

Screenshots: not embedded (third-party copyright); see the linked official pages.

## Synthesis for BusScope

1. **Source → protocol → transport settings**, in that order (wireframe in
   `diagrams/protocol-catalogue/03-wireframe.md`).
2. **Grouped + searchable catalogue** (families → sub-families → protocols), PulseView search
   on top of a Wireshark-like hierarchy, opened from a **compact picker button** so the frame
   list keeps the space.
3. Transport-specific fields (bitrate, CAN-ID filter, baud/parity…) appear **only** for the
   selected transport.
4. Every protocol carries an availability status (*available* / *planned*) so the catalogue
   documents the roadmap without pretending.
