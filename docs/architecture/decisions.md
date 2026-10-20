# Architecture decisions

> **Frozen on 2026-10-19.** New decisions are ADRs under [`docs/decisions/`](../decisions/README.md);
> the entries below stay valid until an ADR supersedes one of them.

## 2026-09-01 - Read-only first

The first milestone observes the charger bus in listen-only mode. Transmission is excluded
until its safety model, validation rules, and operator confirmation flow have been designed.

## 2026-09-01 - SocketCAN boundary

The application will depend on a small CAN port rather than importing python-can throughout the
domain. SocketCAN remains the preferred Linux adapter because it integrates with candump,
kernel filtering, and standard CAN error reporting.

## 2026-09-01 - Configuration boundary

The operator selects the SocketCAN channel in the UI. The application requests listen-only capture
at the protocol bitrate of 125 kbit/s, while the Linux interface state remains externally
configured. Display preferences are stored locally through the QSettings adapter, while stable
Infypower protocol definitions remain versioned documentation and code.

## 2026-09-04 - Safe manual transmission boundary

The first transmission capability is limited to one explicitly confirmed Infypower frame at a
time. Every frame uses a 29-bit extended identifier and exactly eight data bytes, matching the
V1.13 protocol. Transmission is disabled when the application starts, is never persisted, and
cannot be initiated by capture, replay, settings restoration, or a timer.

Validation produces one immutable request containing the channel, identifier, and payload before
the confirmation is shown. The exact same request is passed to a small transmission port after
confirmation. A SocketCAN adapter opens a separate CAN 2.0 socket with local loopback disabled,
sends once, reports any failure, and closes the socket. Linux interface configuration remains an
explicit external operation because the application must not require elevated privileges.

A single userspace send does not prevent a CAN controller from automatically retransmitting an
unacknowledged frame. Immediately before each send, a read-only Linux adapter therefore accepts
`vcan` for development or requires a physical interface to report `ONE-SHOT` without
`LISTEN-ONLY`. Unknown or unsupported state fails closed before the transmit socket is opened.
