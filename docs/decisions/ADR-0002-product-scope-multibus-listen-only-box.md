# ADR-0002: Product scope — a multi-bus, listen-only capture box driven by one desktop application

**Status:** Accepted — 2026-10-19

## Context

The application was built for one Infypower power module on one CAN bus. Field work on a DC
charger in September 2026 showed what a diagnostic tool for EV charging equipment actually meets:

- the module bus carried a second, J1939-shaped protocol besides the vendor's;
- addresses are allocated at runtime, so topology must be learned from traffic, not assumed;
- polling a charger's bus during boot left its HMI stuck — passive listening is the safe mode;
- days were lost because nothing proved the adapter received at all;
- the fault data needed sits on several buses at once: power modules, meters, the vehicle link.

The buses found in chargers and e-mobility equipment, by likelihood: CAN / CAN FD (power modules,
CHAdeMO, GB/T 27930, CANopen), RS485 (Modbus RTU meters, insulation monitors, HMIs), the Control
Pilot / Proximity Pilot pair (IEC 61851), HomePlug Green PHY on the CP line (ISO 15118,
DIN 70121), Ethernet (Modbus TCP, OCPP), RS232 and UART TTL service consoles.

## Decision

The project becomes **one USB box plus one desktop application** that listens to every bus of a
charger at once, on a common timestamp clock.

Box, revision 1:

| Port | Count | Purpose |
|---|---|---|
| CAN / CAN FD | 3 | power modules, CHAdeMO, GB/T, CAN FD modules |
| RS485 | 2 | Modbus RTU meter, IMD or HMI |
| RS232 | 1 | service consoles |
| UART TTL 3.3/5 V | 1 | board-level debug |
| CP / PP measurement | 1 | IEC 61851 state, duty cycle, cable rating |
| Logic tap header | 8 ch | isolated 3.3 V copies of each receiver line and of the CP comparator (ADR-0008) |
| SPI expansion | 1 | HomePlug Green PHY modem (QCA7000 class), revision 2 |

Non-negotiable properties: galvanic isolation on every port; transmit paths disabled in hardware
by default, so listen-only does not depend on software; switchable 120 Ω termination on CAN and
RS485; one timestamp clock for every port.

Out of the box: Ethernet is captured with a port-mirroring switch and Wireshark; ISO 15118 waits
for revision 2 as a separate module. The application's existing CAN capture (SocketCAN, slcan)
keeps working without the box.

## Consequences

- A single USB protocol between box and application, multi-bus and timestamped, becomes the
  contract that the board, the firmware and the application all depend on. slcan cannot carry it.
- The CP/PP front end and the PLC coupling touch circuits tied to the vehicle and to ±12 V; they
  get a dedicated high-voltage design review before the CDR.
- Protocol decoders become per-vendor and pluggable; until a second decoder exists, only that seam
  is introduced.
