# Safe manual CAN frame transmission

> **Feature**: issue #34 — [add safe manual CAN frame transmission](https://github.com/benoit-bremaud/busscope/issues/34)
> **Status**: implemented — pending review
> **Protocol source**: Infypower Charger module CAN Communication Protocol V1.13, sections 1.1,
> 2.1, and 2.2

## Objective

Allow an operator to send one custom Infypower CAN frame through an explicitly selected SocketCAN
channel. The operation must be deliberate, validated, confirmed, synchronous, and independent
from live capture and offline replay.

## Protocol constraints

Infypower V1.13 defines CAN 2.0B at 125 kbit/s with a 29-bit extended identifier and an eight-byte
data field. Manual transmission therefore accepts only:

- an identifier from `0x00000000` through `0x1FFFFFFF`;
- the extended identifier format;
- exactly eight data bytes;
- a Classical CAN frame, never CAN FD, RTR, or an error frame.

The identifier and payload remain fully operator-defined within those structural constraints.
This feature does not interpret, build, or approve the semantic meaning of a charger command.

## Decisions

### D1 — Strict Infypower framing

The first transmission feature does not expose standard identifiers or variable-length payloads.
This matches the target protocol and avoids a generic CAN console that the project does not need.

### D2 — One-shot transmission only

One confirmation can produce at most one adapter call and one physical transmission attempt.
Periodic transmission, software retries, queues, macros, command builders, and replay-to-bus are
excluded. A physical CAN interface must also have controller-level automatic retransmission
disabled (`ONE-SHOT`); a finite userspace send timeout alone does not provide this guarantee.

### D3 — Two deliberate operator actions

The Transmission tab starts disabled on every application launch. The operator must first enable
manual transmission for the current process, then confirm every individual frame. The enabled
state is never persisted.

### D4 — Immutable confirmed request

Validation creates one immutable `ManualTransmission` containing the trimmed channel, parsed
identifier, and eight payload bytes. The confirmation displays that object, and acceptance sends
the same object. Editing widgets cannot change a request after confirmation begins.

### D5 — Fail closed before the adapter

The following inputs are rejected without calling the transmission port:

- an empty channel;
- an identifier that is empty, non-hexadecimal, or outside the 29-bit range;
- a payload that is not exactly eight whitespace-separated two-digit hexadecimal bytes;
- any attempt while manual transmission is disabled;
- a cancelled confirmation.

Adapter failures are shown as errors and never produce a success message or an automatic retry.

### D6 — Small inward-facing port

`CanTransmissionPort` exposes only `send(ManualTransmission)`. The PySide6 transmission panel
depends on that contract and the framework-independent request model. `SocketCanTransmitter`
implements the port with python-can at the infrastructure boundary. The application composition
root wires the concrete adapter.

The port is justified by the required fake implementation used to prove that rejected and
cancelled operations do not reach hardware.

### D7 — Independent, short-lived SocketCAN socket

Immediately before opening a transmit socket, the adapter asks a read-only readiness port to
verify the selected Linux interface. A virtual CAN interface is accepted for development. A
physical CAN interface is accepted only when its reported controller modes include `ONE-SHOT` and
exclude `LISTEN-ONLY`. Missing tools, inaccessible or malformed interface state, unsupported
controller modes, and inspection failures all reject the operation before a CAN socket is opened.

After readiness succeeds, the operation opens a CAN 2.0 SocketCAN bus for the request channel,
disables local loopback, submits exactly one extended frame with a finite timeout, and closes the
bus even on failure. Disabling local loopback prevents the existing capture socket from presenting
the locally sent frame as if it had been received from the charger. Actual charger replies remain
visible to live capture.

### D8 — No privileged interface management

The application never configures an interface and does not run `slcand`, firmware tools, or any
privileged command. The operator configures the Linux interface externally. The infrastructure
adapter may execute `ip -details -json link show dev <channel>` without a shell for a read-only,
immediate readiness check. It treats all ambiguous results as unsafe and reports an actionable
error without transmitting.

### D9 — Capture and replay isolation

Live capture may remain active while the operator sends a confirmed frame on the same channel.
Offline replay never receives a transmission dependency and cannot send imported records. Loading,
playing, pausing, stopping, or resetting a replay cannot enable transmission.

## Input format

The Transmission tab contains:

- a channel field, defaulting to `can0`;
- a hexadecimal identifier field that accepts an optional `0x` prefix;
- a payload field containing exactly eight byte tokens such as `01 02 03 04 05 06 07 08`;
- a non-persistent `Enable manual transmission` control;
- a `Send once` button disabled until manual transmission is enabled.

Hexadecimal letters are case-insensitive. Compact payloads, commas, brackets, missing bytes,
extra bytes, and tokens other than exactly two hexadecimal digits are rejected to keep parsing
unambiguous.

## Confirmation

The confirmation displays the immutable request in a stable form:

```text
Channel: can0
Extended identifier: 0x001ABCDE
Payload: 01 02 03 04 05 06 07 08
Frames to send: 1
```

Closing or rejecting the dialog cancels the operation. Confirmation is synchronous, so only one
manual send can be in progress from the window at a time.

## Hardware readiness — CANable 2.0 compatible adapter

The ordered adapter is sold as a CANable 2.0 compatible USB-C device. Its installed firmware must
be identified on arrival:

- candleLight firmware should expose `can0` directly through the Linux `gs_usb` driver;
- SLCAN firmware should expose a serial device such as `/dev/ttyACM0`, which must be attached to
  SocketCAN externally before starting the application.

The first physical session is receive-only. Verify the terminal labels, connect CANH to CANH and
CANL to CANL, avoid the adapter's 5 V output, and enable its 120-ohm termination only if the
adapter is physically at an unterminated end of the bus. Configure 125 kbit/s and kernel
listen-only mode before capture. Only after wiring and passive capture are validated may the
interface be reconfigured outside the application for an explicitly authorized transmission
test.

No firmware flashing is required by this feature. The application sees only the resulting
SocketCAN channel. The executable arrival checklist is maintained in
`docs/hardware/canable-2.0.md`.

## Verification strategy

### Unit tests

- Accept lower and upper 29-bit identifier boundaries and representative mixed-case hex input.
- Reject empty, malformed, negative, and out-of-range identifiers.
- Accept exactly eight two-digit hexadecimal byte tokens.
- Reject short, long, compact, bracketed, comma-separated, and malformed payloads.
- Preserve a trimmed non-empty channel in the immutable request.
- Verify the SocketCAN adapter builds one extended Classical CAN message, sends once, disables
  local loopback, uses a finite timeout, and always closes its bus.
- Accept `vcan` and physical interfaces reporting `ONE-SHOT` without `LISTEN-ONLY`.
- Reject missing, inaccessible, malformed, listen-only, and non-one-shot physical interfaces
  before opening the transmit bus.
- Verify bus-open and send failures propagate without retry or false success.

### UI component tests

- Verify transmission starts disabled and is not restored from display settings.
- Verify enabling only unlocks the send action and never transmits by itself.
- Verify invalid input and cancellation make zero port calls.
- Verify confirmation shows the exact channel, normalized identifier, payload, and frame count.
- Verify confirmation sends the same immutable request exactly once.
- Verify success and adapter failure produce distinct status messages.
- Verify capture and every replay control remain unable to invoke the transmission port.

### Integration tests

- Send one request through the real python-can virtual backend and receive exactly one matching
  extended eight-byte frame on a separate virtual bus.
- Perform the same one-shot test through `vcan0` before any physical-hardware test.

All tests remain deterministic, cover happy paths, sad paths, and edge cases, and keep total
coverage at or above 90%.

## Acceptance criteria

- The operator can enable manual transmission for the current process only.
- A valid request can be confirmed and sent exactly once.
- Invalid input, disabled state, and cancellation transmit nothing.
- Every transmitted frame is Classical CAN with a 29-bit extended identifier and eight bytes.
- The confirmed request cannot change between confirmation and adapter invocation.
- Adapter errors are actionable and cannot be mistaken for success.
- Physical transmission fails closed unless controller-level `ONE-SHOT` is verified immediately
  before the transmit socket is opened.
- Capture can observe charger replies without displaying a local transmit echo as a received frame.
- Replay remains structurally unable to transmit.
- The core remains independent from PySide6, python-can, SocketCAN, and filesystem I/O.
- The required automated checks and `vcan0` validation pass before physical testing.

## Out of scope

Standard 11-bit identifiers, variable-length payloads, CAN FD, RTR frames, periodic or scheduled
transmission, automatic retries, command builders, semantic command validation, transmission of
replayed captures, automatic SocketCAN configuration, firmware flashing, and persistence of the
enabled state or draft values.
