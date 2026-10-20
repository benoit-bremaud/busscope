# ESP32-C3 three-button bench tests

> **Status**: implemented and hardware-accepted on 2026-09-10. All three scenarios were
> verified on the isolated bench — blue and white at 125 kbit/s, red at 250 kbit/s — with
> zero error counters; see the [bench log](../../hardware/esp32c3-can-bench.md).
> **Related work**: [bench Issue #45](https://github.com/benoit-bremaud/busscope/issues/45).
> The additional bitrate/button scope needs its own GitHub tracking before publication;
> this local specification is the current work item. No issue/PR has been created for it.

## Purpose and boundary

Select repeatable CAN reception tests using three physical momentary buttons, with the
ESP32 powered independently of a USB host. This is an isolated low-voltage bench only:
never connect the generator to a charger or vehicle. The Python application is unchanged.

The opt-in `esp32c3-buttons` build replaces boot-triggered emission with physical
activation. Existing manual and autonomous build profiles retain their behavior and tests.
Flashing is what changes the board: compiling a profile never displaces the resident image.

## Scenarios

All messages are Classical CAN, extended 29-bit identifiers, DLC 8, no RTR or CAN FD.
Normal mode requires another correctly configured node to ACK. Counts are upper limits
on attempts, not guaranteed successful receptions: stop early on any error.

| Button | Scenario | CAN bitrate | Attempts | Interval | Contents |
| --- | --- | --- | --- | --- | --- |
| Blue | Reference125 | 125000 | 10 | 1000 ms | ID `0x001ABCDE`, bytes `01 02 03 04 05 06 07 08` |
| Red | Reference250 | 250000 | 10 | 1000 ms | Same fixed ID/data |
| White | Varied125 | 125000 | 12 | 1000 ms | Cycle three IDs with a deterministic counter |

For Varied125, attempt index `n` runs from 0 through 11. Let `j = n % 3`:

- IDs by `j`: `0x001ABCDE`, `0x001ABCDF`, `0x001ABCE0` (four attempts per ID).
- Payload: `[n, j, 0xAA, 0x55, 0x00, 0xFF, 0x12, 0x34]` (all bytes).
- These are generic synthetic data, not simulated charger measurements.

Using 1 Hz throughout isolates bitrate/content variation from throughput variation.
The twelve-attempt white sequence covers each of three IDs equally; it is not a load test.
These are project-specific test choices, not CAN-standard requirements.

## GPIO wiring proposal

| Button | ESP32-C3 GPIO | Other contact |
| --- | --- | --- |
| Blue | 0 | GND |
| Red | 1 | GND |
| White | 5 | GND |

Use normally-open, potential-free momentary contacts, short leads and `INPUT_PULLUP`.
Released is HIGH; pressed shorts only the corresponding input to GND (LOW). No 5 V
or external voltage is applied to the inputs. For four-leg buttons, verify which two
contacts actually switch; same-side pins may already be connected. Illuminated buttons
need a separate wiring review; do not connect their lamp supply to a GPIO.

GPIO4/3 stay dedicated to CAN TX/RX. GPIO8 drives the onboard LED (B11) and is configured
only in `setup()`, after boot has released its strapping function; it must stay externally
unwired. Avoid the remaining strapping pins GPIO2/9, USB GPIO18/19 and flash
pins. GPIO5 also has a JTAG function, but this bench uses native USB Serial/JTAG and no
external GPIO JTAG probe. Confirm the prototype carrier does not use GPIO0/1/5 itself.
The supplied Super Mini photo exposes these labels; it does not prove the carrier wiring.

Wire only with both boards unpowered and the charger physically disconnected. Flash
with CAN disconnected, particularly while the previous autonomous image may still boot.

## Requirements and state rules

- B1: No controller start or data-frame emission at boot/reset or USB connection. No USB
  host is required. Input configuration must not touch CAN pins or strapping pins.
- B2: Require all three buttons released and stable for 30 ms after boot, completion or
  reset before accepting a new selection. A held-at-boot button never launches a test.
- B3: Debounce the complete three-bit pressed mask for 30 ms using unsigned elapsed time.
  Accept one stable single-button press per release cycle. Zero is release, multiple
  simultaneous presses are rejected and require another full release. Thirty milliseconds
  is a conservative bench default, to validate against actual switch bounce, not a standard.
- B4: One test at a time. During Running, ignore button selections, never queue them.
  On completion, require a new full release followed by a new press. Holding a button or
  pressing during a test cannot launch an unexpected later series.
- B5: A valid press selects the entire scenario atomically, starts CAN at its bitrate,
  and schedules the first attempt after 1000 ms. No ten-second autonomous countdown here.
  Subsequent attempts are at least 1000 ms apart, with no catch-up bursts and one pending.
- B6: Never change bitrate while CAN is running. Stop/uninstall must succeed before a new
  installation at 125 or 250 kbit/s. Only these enum-selected bitrates are allowed; reject
  invalid scenarios, do not silently default. Report selected bitrate and scenario in status.
- B7: Preserve single-shot, no TX software queue, nonblocking submission and 250 ms completion
  deadline. Error takes precedence over success; queued is not transmitted. Wait for the final
  completion before stopping. Keep per-run outcome counts separate from lifetime diagnostics.
- B8: Initialization, submission, TX_FAILED, timeout, bus-off or cleanup error ends the run
  in latched Fault. No automatic retry/restart. In this profile, no button clears Fault:
  inspect the setup and use MCU reset before another test. Reset returns to release-wait,
  not emission. USB `stop` may retry cleanup but cannot re-arm a faulted runner.
- B9: USB is diagnostic only: support `status`, `help`, `stop`; reject `start` to avoid a
  second selection path. `stop` cancels a healthy run and returns to release-wait after cleanup.
  USB connect/disconnect does not cancel or restart a button-selected run. Log backpressure
  must never block button sampling or CAN deadline processing.
- B10: No physical emergency-stop claim. The red button selects Reference250, not stop.
  Operator can reset/remove ESP32 power; a frame already on wire cannot be recalled.
  No long-press gestures, persistent settings, arbitrary frame editor or bitrate scan.
- B11 (approved 2026-09-10, after operator feedback): exactly one output, the onboard GPIO8
  LED. It pulses 250 ms each time the transmitted counter increments, so a USB-less run is
  observable at all. It is an activity indicator, never a state display: it stays dark for a
  queued-but-unacknowledged frame, and it must never gate, delay or reorder emission.
  Under `BENCH_NO_ACK` the pulse is deliberately stuttered so it cannot be read as proof of
  acknowledgement (N3).

## Use cases

### UC1 — Run a reference or variable-content reception test

Primary actor: Operator. Preconditions: isolated bench, compatible transceiver and termination,
CANable capture prepared at the desired bitrate, all buttons released.

1. Operator powers the ESP32; controller stays stopped.
2. Operator presses exactly one colored button.
3. Firmware validates the debounced selection and configures the matching scenario.
4. Firmware attempts the bounded series; the operator observes CANable reception.
5. Firmware stops after final completion and waits for released buttons before another selection.

Extensions: held/ambiguous press is rejected; presses during a run are discarded; any CAN fault
stops and latches Fault; USB stop cancels. Postcondition: no queued future test, no automatic restart.

### UC2 — Inspect or cancel an active test

Operator may use optional USB status/help/stop. Inspection does not transmit. Stop attempts
cleanup, reports the result and disarms button selection until a full release. Fault still
requires reset. This is not a hardware interlock or a substitute for physical isolation.

## Architecture and implementation plan

Keep existing pure control logic plus thin adapters; no framework of polymorphic tests.
Three present scenarios justify a small enum/table and pure frame generation, not a class per test.

| Area under `firmware/esp32c3-can-bench/` | Planned change |
| --- | --- |
| `lib/bench/scenarios.h/.cpp` | Scenario enum, fixed validated definitions, deterministic frame-at-index function |
| `lib/bench/buttons.h/.cpp` | Whole-mask debounce/release gate and ButtonTestRunner lifecycle, injected time/raw mask |
| `lib/bench/bench.h/.cpp` | Reuse completion/error/cadence handling; allow scenario-selected bitrate/frame per attempt and per-run accounting while preserving old-profile defaults |
| `src/twai_port.h/.cpp` | Accept validated bitrate selection on install; map 125/250 to SDK timing constants; no configuration writes during a running session |
| `src/main.cpp` | Compose buttons profile, sample GPIO0/1/5 each bounded loop, route optional USB diagnostics and report actual scenario |
| `platformio.ini` | Add `esp32c3-buttons` and `native-buttons`; reject incompatible profile flags at compile time |
| `test/` | Pure scenario/debounce/state tests, SDK adapter assertions, real-entrypoint tests with boundary doubles, regressions for the existing profiles |
| `README.md`, hardware guide | Wiring, per-button expected trace, fault/reset behavior and profile-specific startup warning |

Loop ordering: service CAN faults, process bounded USB input (including stop), then sample
GPIO and pass the raw mask/time to the runner, which owns debounce/selection and schedules
at most one frame. Debounce stays inside the pure runner rather than the application adapter
so every caller observes the same release gate. SDK/GPIO/USB imports remain outside the pure library.
Preserve the current manual and autonomous contracts, including their different USB-loss rules.
No edits to the desktop GUI, Cangaroo, dependency versions or CI pipelines are part of this plan.

## Verification and traceability

| Requirement | Automated evidence planned | Hardware evidence needed |
| --- | --- | --- |
| B1–B3 | Startup held/released, input bounce, 29/30 ms boundary, invalid masks, clock rollover | Each physical contact, pull-up wiring, no boot transmission |
| B4–B5 | Repeated/held presses, busy press discarded, release gate at end, 999/1000 ms, late loop | One series per press, next series only after a new press |
| B6 | 125/250 SDK register configuration, invalid selection rejected, install/cleanup failures | Matching receiver bitrate, verify setting actually applied |
| B7–B8 | All IDs/data/counts, final completion/timeout, conflicting alerts, no retry, no button fault bypass | Complete count and stop; controlled wrong-bitrate error and reset |
| B9–B10 | No USB host, reconnect, log backpressure, stop priority, rejected USB start | Standalone power and observable stop/reset behavior |

Require at least 90% coverage of authored executable production code per native profile,
and report coverage separately. Build all three ESP32 profiles; rerun Python pytest/coverage,
Ruff and mypy. Native doubles cannot prove electrical behavior or successful ACKs.

Receiver tests: blue/125 and red/250 are positive cases; blue/250 and red/125 are negative
cases only after verifying the receiver applied its selected bitrate. White/125 should show
twelve frames, four per ID, counters 0 through 11. A blank trace alone does not prove Fault.

## Conception review

- Requirements/traceability: accepted colors map to finite scenarios; detailed defaults above
  are approved. B1–B10 cover selection, busy/error behavior, shutdown and hardware limits.
- Clean/SOLID: GPIO/USB/TWAI adapters depend on small pure contracts; no SDK dependency enters
  scenario generation, debounce or scheduling. Reuse the existing CAN fault policy.
- KISS/YAGNI/DRY: fixed enum scenarios and one debouncer/runner; no task queue, input gestures,
  persistent config or speculative extension system. No duplicated transmission engine.
- Pattern fit: existing injectable CanPort seam is justified by SDK testing. Scenario selection
  uses a table/switch; no class hierarchy or extra layers. UML use-case, sequence and state
  views answer operator goals, timing and lifecycle; no standalone class/PII view is needed.

## References

- [Base bench specification](esp32c3-can-bench.md)
- [ESP32-C3 GPIO restrictions](https://docs.espressif.com/projects/esp-idf/en/stable/esp32c3/api-reference/peripherals/gpio.html)
- [Arduino ESP32 GPIO pull-ups](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/gpio.html)
