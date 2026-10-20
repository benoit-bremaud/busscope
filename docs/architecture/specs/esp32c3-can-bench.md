# ESP32-C3 CAN bench generator

> **Feature**: [Issue #45](https://github.com/benoit-bremaud/busscope/issues/45)
> **Status**: conception approved by the maintainer on 2026-09-09 — implemented, with the
> three-button profile hardware-accepted on 2026-09-10 (all three scenarios, counters
> recorded). The manual and autonomous profiles have each been observed transmitting and
> being acknowledged, but their acceptance checklists are not complete and both stay open;
> the evidence actually recorded is in the [bench log](../../hardware/esp32c3-can-bench.md).
> `BENCH_NO_ACK` (N1-N3) stays diagnostic-only and is never an acceptance path.

## Purpose and boundary

Validate reception of known frames through a CANable on a standalone, low-voltage bench.
The ESP32-C3, 3.3 V transceiver and CANable must be physically disconnected from every charger.
This firmware does not diagnose a charger, determine an unknown bitrate, or prove listen-only
operation. The existing desktop application and its transmission policy are unchanged.

## Requirements

The following R1–R10 describe the default **manual** profile. The maintainer approved
the additional autonomous profile below on 2026-09-10; it deliberately changes activation
and USB-loss behavior only for that explicitly selected build.

- R1: No CAN controller start or transmission at boot. Commands arrive through native USB CDC.
- R2: Use Classical CAN, extended ID `0x001ABCDE`, DLC 8 and payload
  `01 02 03 04 05 06 07 08`. Use 125000 bit/s, GPIO4 TX and GPIO3 RX.
- R3: Accept case-sensitive `start`, `stop`, `status` and `help`, terminated by LF or CRLF.
  Trim surrounding spaces/tabs. Ignore empty lines. Reject unknown commands. Limit a command
  to 32 characters excluding its terminator; discard an overlong line through LF, never execute
  its suffix. Do not accumulate commands while the USB terminal is disconnected.
- R4: `start` is the operator's assertion that the bench is disconnected from the charger.
  Print this prerequisite in the boot banner and help. It is not physically enforceable in software.
  Start the controller in normal mode with per-frame single-shot enabled, then schedule the first
  attempt after 1000 ms. Repeated `start` while running does not reset the schedule or send early.
- R5: Allow at most one pending transmission and one attempt per 1000 ms. Never catch up missed
  periods with bursts. Use wrap-safe unsigned millisecond elapsed-time comparisons.
- R6: Queue acceptance is logged as `queued`, never as success. Only TWAI TX_SUCCESS means
  `transmitted`; that does not prove Cangaroo displayed the frame. Use a zero-length TX software
  queue and nonblocking submission. Bound completion waiting to 250 ms.
- R7: Submission failure, TX_FAILED, bus-off, initialization failure or completion timeout
  latches Fault and stops the controller. Error wins over success if both arrive together.
  TX_FAILED alone must not be described as proof of missing ACK: it has multiple possible causes.
  No automatic retries or bus-off recovery. Bus-off requires a device reset after bench inspection.
- R8: Process `stop` and faults before scheduling another frame. Stop aborts pending transmission
  through the driver, clears pending results and enters Stopped only after confirmed cleanup.
  A frame already on the wire cannot be recalled. Cleanup failure remains Fault.
  Repeated `stop` is harmless. From Fault, `start` alone is rejected; `stop` may return to Stopped
  only after successful cleanup and when bus-off is not latched. A fresh `start` is then required.
- R9: USB terminal disconnection stops the controller and clears partial commands. Reconnection
  does not restart emission. Loss detection depends on USB CDC connection reporting and is not a
  hardware interlock. MCU reset always returns to Stopped.
- R10: `status` and `help` never transmit. Status reports state, configuration, queued/succeeded/
  failed attempt counters and last fault. Completion timeout counts as one failed attempt;
  late results cannot count it again. An operator-aborted pending attempt is reported as aborted,
  not as confirmed success or a diagnosed bus fault.

## Design and toolchain

### Inverse bench reception (approved 2026-09-10)

UC6 — Verify CANable transmission with the ESP32 receiver. Primary actor: Operator.
Precondition: isolated low-voltage bench, never connected to a charger or vehicle.
Success: the ESP32 records the expected extended ID, DLC and bytes after a known CANable
transmission. Failure/absence is not a unique diagnosis of hardware failure.

- RX1: Opt-in `esp32c3-receiver`, exclusive with autonomous/buttons flags. No CAN start
  at boot. USB `start` explicitly starts normal-mode reception at 125 kbit/s, GPIO4/3.
  Normal mode supplies ACK/error signaling; this is not listen-only and not for chargers.
- RX2: The receiver application never constructs or calls the emission controller. It
  never submits a data frame. `start` while ready is idempotent, with no counter reset.
- RX3: `BenchReceiver` in the hardware boundary reuses `TwaiPort` configuration, polling
  diagnostics and cleanup. Its nonblocking service reads at most one frame per loop.
  It retains a saturating count and the last valid Classical CAN frame in RAM. It supports
  standard/extended, DLC 0–8 and RTR (no data display for RTR); malformed ID/DLC faults.
- RX4: `status` prints ready/stopped/fault, count, last frame and retained diagnostics.
  Individual reception also prints the last frame. USB absence/slow output never blocks
  reception or loses the retained last frame. Disconnect discards commands, not capture.
  Reconnection never starts/restarts CAN. No unbounded application capture buffer.
- RX5: `stop` closes CAN, retaining results. A new start from stopped clears them. Start
  from fault is rejected until explicit stop successfully cleans up, except bus-off which
  requires reset. Initialization, SDK read, malformed frame and polled driver errors stop
  capture; empty RX queue is normal. No retries or bus recovery. Cleanup failure stays fault.
- RX6: Tests use real application/receiver/adapter with SDK doubles, including no-data,
  exact frames, invalid fields, faults, stop, restart, USB backlog/loss and zero TX calls.
  Build all four profiles and maintain >=90% authored native line coverage per profile.

The receiver is a small hardware-boundary collaborator, not protocol-domain logic. It adds
no SDK dependency to `lib/bench`, no new general-purpose service or abstract factory. The
existing adapter seam and SDK doubles suffice. The review finds requirements/test traceability,
inward domain dependencies, bounded storage/work, and no need for an additional design pattern.
See the [receiver sequence](../diagrams/esp32c3-can-bench/02-sequence-receiver.md).

### Retained TWAI diagnostics (approved 2026-09-10)

- D1: `TwaiPort` retains the latest polling snapshot in RAM: raw alert bits, separate
  alert/status read availability, controller state, TX/RX error counters, failed TX,
  missed/overrun RX, lost arbitration and bus error counts. No SDK type enters the domain.
- D2: Polling captures the snapshot before returning a fault to `BenchController`.
  Cleanup and subsequent polls on an uninstalled driver preserve it. A new permitted
  start attempt clears it, including when installation fails. Rejected starts preserve it.
  Before any poll the snapshot is explicitly unavailable; it is not a live status query.
- D3: `status` renders the retained snapshot after cleanup or late USB attachment.
  Failed reads are explicitly unavailable, never represented as zero errors. Logs remain
  bounded and best-effort; the snapshot survives dropped logs but not MCU reset.
- D4: No change to pins, timing, activation, single-shot transmission or fail-stop policy.
  These counters are clues, not a unique diagnosis of missing ACK or wiring failure.
- D5: Native tests cover success, fault retention, invalid reads, cleanup, new-session reset,
  late USB retrieval and maximum counter formatting. Build all three firmware profiles and
  maintain at least 90% authored line coverage in each native profile.

The [diagnostic sequence](../diagrams/esp32c3-can-bench/02-sequence-diagnostics.md)
captures the ordering. This reuses the existing adapter and USB boundary: no new service,
domain port or persistence is needed. Requirements/sequence/tests agree on snapshot lifetime;
dependencies stay inward; scope is limited to observation; no additional pattern is justified.

### Autonomous bench profile (approved 2026-09-10)

- A1: `esp32c3-autonomous` is opt-in at build time; `esp32c3` remains manual/default.
  Power-up/reset is the operator's trigger. Never connect this image to a charger or vehicle.
- A2: Wait 10000 ms from MCU boot before starting CAN and scheduling the first frame.
  Use the same frame, pins and bitrate as R2. Submit at most 10 single-shot attempts,
  spaced at least 1000 ms apart, with no catch-up bursts. Do not require USB enumeration.
- A3: Preserve R6/R7 error and completion semantics. Wait for the final completion (or
  its 250 ms deadline) before cleanup. Stop on the first failure, even if fewer than ten
  frames were sent. Successful cleanup after ten completions leaves the controller stopped.
- A4: One series per boot. Completion, error or `stop` permanently consumes the series
  until MCU reset/power cycle. USB open/close/reconnect never restarts it. `start` is rejected
  in this profile; `stop` also cancels the initial countdown. Status/help remain available.
- A5: USB absence is expected and does not cancel this autonomous series. Logging remains
  bounded and optional. A USB connection is not an interlock. Reset (including an upload
  reset or brownout) arms a new series; flash only with CAN physically disconnected.
- A6: Unit tests cover countdown boundaries, counter limits, late ticks/rollover,
  final completion, cancellation, faults and cleanup. Compile and test both profiles;
  exercise the autonomous entrypoint with no USB host and with USB reconnection.

### No-ACK self-test (`BENCH_NO_ACK`, diagnostic only)

- N1: The flag composes with any one profile and changes a single thing — the controller is
  installed in `TWAI_MODE_NO_ACK`, so a transmission is reported successful with no
  acknowledgement on the bus. Bitrate, pins, frame, single-shot behaviour and every runner
  are identical to the profile it extends. Only `esp32c3-buttons-noack` is a reviewed image;
  combining the flag with the autonomous profile is rejected at compile time, because that
  image would emit after every boot, report fabricated success and need no USB host.
- N2: It answers exactly one question, and only when a normal-mode run fails with
  `TX_FAILED`: is the fault inside the ESP32 and its transceiver, or beyond them? Success
  proves the controller, the transceiver and the bit timing. It proves nothing whatsoever
  about the receiver, the wiring past the transceiver, or the bus.
- N3: Because a pass here is not evidence, every output channel must be self-labelling. The
  help banner announces the image, every `status` sample carries
  `selftest=no_ack ack_required=0`, and the B11 LED pulse is stuttered so it cannot be
  mistaken for the steady flash of an acknowledged run — the banner and the marker both
  require USB, and this image is used without a host. Results are recorded as diagnostic
  observations, never as acceptance, and the normal image is reflashed immediately after.

`BurstRunner` owns the one-shot lifecycle and delegates CAN policy to `BenchController`.
The latter exposes `start_immediately()` to schedule a first attempt after the external
countdown, without duplicating transmission/error handling. The USB adapter selects one
runner at compile time. No new hardware interface, runtime mode switch or persistence.
The manual sequence is unchanged; the autonomous sequence/state view is maintained separately.

Use PlatformIO Core 6.1.19, espressif32 6.12.0 and the installed Arduino ESP32 framework
2.0.17 with its ESP-IDF TWAI driver. Pin platform/tool dependencies during implementation.
Use the ESP32-C3 target with explicit GPIOs and native USB CDC flags. A generic C3 board profile
is a build starting point, not proof of this Super Mini's flash size or upload settings; verify
the connected MCU and flash before upload. Do not install into system Python or alter the desktop
`.venv` / `.venv-test`. Use the firmware directory's isolated `.venv` for PlatformIO tools.

Implementation files under `firmware/esp32c3-can-bench/`:

- `platformio.ini`: firmware and native test configurations, pinned dependencies.
- `lib/bench/`: fixed frame, bounded command parser and BenchController state/cadence logic.
- `src/main.cpp`: composition and USB CDC adapter, with no duplicated policy.
- `src/twai_port.*`: TWAI adapter, separately compiled against SDK doubles in native tests.
- `test/`: native unit/component tests and fake boundary implementations.
- `README.md`: reproducible build, test, coverage and upload instructions.

BenchController receives time, commands and driver results rather than importing Arduino or TWAI.
A small CanPort boundary exposes initialization/start, single submission, result polling and stop.
The production adapter and a deterministic fake implement it. This boundary exists for error-path
testing, not for hypothetical hardware support. Use an enum for the state, not a hierarchy of State
classes. USB parsing and logging remain bounded and must not block control processing indefinitely.

## Bench acceptance procedure (deferred until hardware is ready)

1. Confirm physical separation from the charger and secure connections, with USB power removed.
2. Connect 3.3 V to the transceiver supply, common ground, GPIO4 to TX, GPIO3 to RX,
   CANH to CANH and CANL to CANL. Do not connect either board's 5 V output to the other board.
3. Verify a 120-ohm termination at each end; do not short CANH/CANL with a jumper.
   Board photos alone do not electrically validate the termination or the chip identity.
4. Identify the ESP32 serial port separately from the CANable before any upload.
5. Open CANable capture at 125 kbit/s in normal mode on this isolated bench to supply ACK.
   A genuinely listen-only receiver does not ACK; single-shot failures in that setup do not prove
   the transmitter emitted no frame. Never use this normal-mode bench recipe on the charger.
6. Confirm boot/status/help produce no data frames. Enter `start`; verify one matching extended
   frame per second, then `stop` and verify no new attempts. Check USB disconnect/reset behavior.
7. Perform controlled receiver-absent and fault tests with power removed before rewiring.
8. First validate Cangaroo. Then, with Cangaroo stopped, configure a compatible SocketCAN interface
   separately for busscope reception. Its GUI cannot directly use the SLCAN serial port.

## Verification and traceability

| Requirement | Automated evidence | Hardware evidence |
| --- | --- | --- |
| R1, R4, R8, R9 | Boot, repeated start/stop, reconnect, cleanup failures | No startup frames, stop/reset/disconnect |
| R2 | Exact ID, format, DLC, bytes, adapter configuration assertions | Matching received frame |
| R3 | LF/CRLF, whitespace, empty/invalid, length 32/33, fragmented input | USB terminal commands |
| R5 | Fake time at 999/1000 ms, rollover, late ticks, pending operation | Approximately 1 Hz, no bursts |
| R6, R7, R10 | Queued vs success, timeout boundary, late/conflicting events, failures | ACK/no-ACK, disconnect and fault behavior |

Measure at least 90% coverage of authored executable bench code in native tests, including the
adapter behavior through SDK boundary doubles where feasible. Do not count SDK/library code.
If a hardware-dependent entrypoint cannot be instrumented natively, report it explicitly and
do not claim whole-firmware coverage from the pure core alone. Any scope exception requires
approval. Cross-compilation complements coverage but does not prove electrical behavior.
Run the existing Python pytest/coverage, Ruff and mypy checks before the implementation PR.
No CI changes or uploads are included in the conception work.

The UML views in `../diagrams/esp32c3-can-bench/` cover actor goals (01), the cross-boundary
transmission sequence (02), and the controller lifecycle (05). No class diagram is needed for
this small control loop; no capture files or identifying charger data are stored.

Regenerate the committed SVGs without embedded source metadata (which introduces CRLF lines
with the installed renderer):

```bash
JAVA_TOOL_OPTIONS=-Djava.awt.headless=true plantuml -nometadata -tsvg \
  docs/architecture/diagrams/esp32c3-can-bench/*.puml
```

## Conception review

- Requirements: fixed frame and explicit activation match the bench need; fault and ACK semantics
  prevent treating a successful enqueue as a successful physical test.
- Dependencies: pure control policy depends on a small testable boundary; SDK code stays outside.
- Simplicity: one fixed frame, one cadence, no editor, persistence, bitrate scan or retry engine.
- Patterns: a fakeable hardware boundary is justified; a state enum is sufficient.

## References

- [ESP32-C3 TWAI driver](https://docs.espressif.com/projects/esp-idf/en/v4.4.7/esp32c3/api-reference/peripherals/twai.html)
- [SN65HVD230](https://www.ti.com/product/SN65HVD230)
- [Existing CANable guide](../../hardware/canable-2.0.md)
