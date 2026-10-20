# ESP32-C3 CAN bench generator

**Bench only. Physically disconnect every charger before powering or using this firmware.**
It emits synthetic test frames; it is neither a charger simulator nor a diagnostic command tool.
The [approved design](../../docs/architecture/specs/esp32c3-can-bench.md) is tracked by
[Issue #45](https://github.com/benoit-bremaud/busscope/issues/45).

## Software-only preparation

Run these commands from this directory on Linux with Python 3.12, GCC/gcov and a working
internet connection for the initial dependency download. No hardware is needed.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-tools.txt
.venv/bin/pio run -e esp32c3
.venv/bin/pio run -e native -t clean
.venv/bin/pio test -e native
.venv/bin/gcovr .pio/build/native --txt
```

The clean target only removes generated native build artifacts. It prevents stale coverage
counters from previous builds contaminating the report. Do not run native clean and tests
concurrently. PlatformIO caches its SDK packages outside the project; the Python tools remain
in this directory's ignored `.venv`, independent of the desktop app's two environments.
Only commands containing `upload` flash a device; none of the commands above do so.

The native tests compile **all authored production C++**, including `setup()`/`loop()` and
`TwaiPort`, against narrow Arduino/TWAI doubles in `test/support/`. The same sources compile
against the real pinned ESP32 SDK in the `esp32c3` environment. Coverage includes `lib/bench/`
and `src/`, not the test doubles or vendor libraries; `gcovr.cfg` fails below 90% line coverage.
Native branch coverage is also reported, excluding compiler-generated unreachable/throw branches.
Passing these tests does not validate USB electrical behavior, the transceiver, ACKs or wiring.

## Layout

- `lib/bench/`: bounded command parser, fixed frame and controller policy with injected time/CAN.
- `src/twai_port.*`: the small SDK adapter implementing `CanPort`.
- `src/main.cpp`: USB input/output and composition. Input work is capped per loop; log writes
  are space-checked with a short SDK timeout. Dropped logs are counted instead of blocking CAN control.
- `test/test_bench/`: native unit and component tests. No attached hardware is opened by these tests.

## Hardware and upload (deferred acceptance)

Follow the [bench wiring and acceptance checklist](../../docs/hardware/esp32c3-can-bench.md)
before connecting anything. No upload was performed during software preparation.

The `esp32-c3-devkitm-1` profile is a generic build profile, **not a verified identification**
of a Super Mini. It assumes 4 MB flash. Confirm the actual ESP32-C3 and flash capacity before
uploading; stop if they differ. Native USB uses GPIO18/19; the CAN GPIOs are explicitly 4/3.

Identify the ESP32 USB serial path by connecting **the ESP32 alone** and checking Linux's
`/dev/serial/by-id/` or PlatformIO's device list. The CANable also exposes an ACM port: never
choose an upload port by guessing `ttyACM0` versus `ttyACM1`.

After confirming the target, substitute its explicit path below (do not use the CANable path):

```bash
.venv/bin/pio run -e esp32c3 -t upload --upload-port /dev/serial/by-id/ESP32_DEVICE
.venv/bin/pio device monitor --port /dev/serial/by-id/ESP32_DEVICE --baud 115200 --eol LF
```

If automatic upload reset fails, consult the board's boot procedure before using BOOT/RESET;
do not change the CANable firmware. USB disconnection/re-enumeration may change the port name.

## Autonomous profile (explicit opt-in)

The default `esp32c3` build remains manual. `esp32c3-autonomous` instead starts a single
series **10000 ms after every MCU boot/reset**, with no serial command or USB host required.
It submits at most ten of the same fixed frames at 1 Hz, waits for the final completion,
then stops. Any failure/250 ms timeout stops the series early without retry.

The delay is a bench convenience, not a safety interlock. **Never connect this image to a
charger or vehicle.** Reset, brownout and the reset after uploading all arm another series.
Compile/test first and upload with CAN physically disconnected:

```bash
.venv/bin/pio run -e native -e native-autonomous -t clean
.venv/bin/pio test -e native -e native-autonomous
.venv/bin/gcovr .pio/build/native --txt
.venv/bin/gcovr .pio/build/native-autonomous --txt
.venv/bin/pio run -e esp32c3 -e esp32c3-autonomous
# Only after identifying the ESP32 and disconnecting CAN:
.venv/bin/pio run -e esp32c3-autonomous -t upload --upload-port /dev/serial/by-id/ESP32_DEVICE
```

The autonomous native environment runs the actual entrypoint with SDK doubles, including
operation without a USB host and connection changes during the series. Report coverage for
each environment separately; these tests still do not prove electrical operation.

`stop` cancels the countdown or current series permanently until reset; `start` is rejected.
`status`/`help` remain available when connected to a computer. Unlike the manual profile,
USB loss does **not** stop this series: USB may be power-only. Logging never gates emission.
During the countdown, controller status is `stopped`; this does not mean the series is cancelled.
To cancel it, send `stop` or remove power. Opening a monitor must not intentionally reset the MCU.

For reception, start the CANable in Cangaroo at 125 kbit/s, **normal mode on the isolated bench**,
before powering the ESP32 from a separate USB supply. No simultaneous ESP32 data connection is
required. Expect up to ten extended `0x001ABCDE` frames, one per second, beginning after ten
seconds. A missing ACK can end the series on the first attempt. Reset/power-cycle to repeat
only after checking the bench. To restore manual behavior, reflash `esp32c3` with CAN disconnected.

## Three-button profile (explicit opt-in)

The [approved button design](../../docs/architecture/specs/esp32c3-button-tests.md)
is implemented by `esp32c3-buttons`. It never starts CAN or emits data frames at boot.
Wire normally-open contacts from blue GPIO0, red GPIO1 and white GPIO5 to GND; firmware
uses internal pull-ups. No 5 V on these inputs. GPIO4/3 remain CAN TX/RX.

The onboard GPIO8 LED (active low) flashes 250 ms each time the transmitted counter
increments, in every profile except `esp32c3-receiver`. Leave GPIO8 externally unwired: it
is a strapping pin, driven only after boot. Read it as an activity indicator, not a state
display — it stays dark for a frame that was queued but never acknowledged, which is what a
bitrate mismatch looks like. It mirrors the controller's TX_SUCCESS accounting and nothing
more, so under `esp32c3-buttons-noack` that accounting is fabricated and the pulse is
stuttered to say so.

| Button | Bitrate | Series (extended Classical CAN, DLC 8) |
| --- | --- | --- |
| Blue | 125 kbit/s | 10 attempts, ID `0x001ABCDE`, bytes `01 02 03 04 05 06 07 08` |
| Red | 250 kbit/s | Same 10 attempts |
| White | 125 kbit/s | 12 attempts, cycling IDs `0x001ABCDE`, `0x001ABCDF`, `0x001ABCE0` |

All series run at 1 Hz, first attempt one second after the debounced press. White payloads
are `[n, n % 3, AA, 55, 00, FF, 12, 34]`, with `n` from 0 to 11. These are not charger measurements.
Counts are upper limits: any initialization/transmission/timeout/cleanup error ends the run.

After boot or completion, release all buttons for at least 30 ms, then press exactly one.
Holding a button never repeats a test; simultaneous presses are rejected; busy presses are
ignored, not queued. Fault requires MCU reset, which returns to silent release-wait.
The red button selects a test; it is **not** an emergency stop.

USB is optional and only accepts `help`, `status`, `stop`. USB `start` is rejected, and USB
loss does not stop a button-selected series. `stop` cancels a healthy series; it cannot clear
the runner's fault latch. Status includes the selected bitrate/scenario, runner state and
per-run `run_queued`, `run_transmitted`, `run_failed`, `run_aborted` alongside lifetime counters.

```bash
.venv/bin/pio run -e native -e native-autonomous -e native-buttons -t clean
.venv/bin/pio test -e native -e native-autonomous -e native-buttons
.venv/bin/gcovr .pio/build/native --txt
.venv/bin/gcovr .pio/build/native-autonomous --txt
.venv/bin/gcovr .pio/build/native-buttons --txt
.venv/bin/pio run -e esp32c3 -e esp32c3-autonomous -e esp32c3-buttons
# Only after identifying the ESP32 and physically disconnecting CAN:
.venv/bin/pio run -e esp32c3-buttons -t upload --upload-port /dev/serial/by-id/ESP32_DEVICE
```

The profile flags `BENCH_AUTONOMOUS` and `BENCH_BUTTONS` cannot both be enabled.
Compiling does not update the board: an existing autonomous image still emits after reset
until it is replaced. Follow the [button acceptance session](../../docs/hardware/esp32c3-can-bench.md#three-button-acceptance-session).

## Receiver profile (inverse bench test)

`esp32c3-receiver` starts with CAN stopped. After opening a USB monitor, `start` enables
normal-mode reception at 125 kbit/s on GPIO4 TX / GPIO3 RX and reports `receiver=ready`.
This profile has no application data-frame emission path, but the controller supplies ACK
and error signaling. **It is not listen-only. Never connect it to a charger or vehicle.**
The profile cannot be combined with autonomous/buttons flags. Buttons have no function here.

On the isolated bench, prepare CANable at the same bitrate and send one known extended frame
only after the ESP32 reports ready. Expected output includes:

```text
rx_id=0x001abcde extended=1 rtr=0 dlc=8 data=[01 02 03 04 05 06 07 08 ]
```

`status` reports `received`, the last frame and retained TWAI diagnostics. Received count
saturates at UINT32_MAX. Standard/extended Classical CAN and DLC 0–8 are accepted; RTR is
identified and never displayed as payload data. Invalid ID/DLC or SDK errors stop capture.
An empty queue is normal. At most one message is consumed per loop, and only the last frame
is retained. This is a low-rate bench tool, not a lossless traffic recorder.

USB loss does not stop an explicitly started receiver; results remain available after reopening
the monitor. Logging is bounded and best-effort. `stop` ends reception without clearing results;
a fresh start from stopped clears the count and last frame. Repeated start while ready is a no-op.
Fault requires explicit stop/cleanup before restart; bus-off requires MCU reset.

```bash
.venv/bin/pio test -e native-receiver
.venv/bin/gcovr .pio/build/native-receiver --txt
.venv/bin/pio run -e esp32c3-receiver
# Only after identifying ESP32 and physically disconnecting CAN:
.venv/bin/pio run -e esp32c3-receiver -t upload --upload-port /dev/serial/by-id/ESP32_DEVICE
```

Build/test all four profiles before publication. The previous firmware still governs the board
until flashing succeeds; an existing autonomous image can transmit on reset. Disconnect CAN
before powering for upload, then reconnect the isolated bench with power removed.

## Sniffer profile (slcan, receive only)

`esp32c3-slcan` turns the board into a CAN adapter that speaks the LAWICEL slcan protocol
over its USB CDC link, so `busscope` reaches it through the application's slcan backend
with no change. It is the only profile meant to face a bus the operator does not own.

Two properties make that acceptable, and both are enforced rather than promised:

- **It cannot transmit.** `t`, `T`, `r`, `R` and `x` are answered with BEL in every state and
  no code in the profile submits a frame.
- **`L` is a controller mode**, `TWAI_MODE_LISTEN_ONLY`, which the SDK defines as making no
  transmissions and no acknowledgments. `O` opens in normal mode, which does acknowledge, and
  exists for the two-node bench where nothing else would acknowledge the generator.

Every command is answered — CR accepted, BEL refused — so "applied" is never confused with
"ignored". The profile writes protocol bytes and nothing else: opening a serial monitor shows
silence until you type a command, because a banner would arrive inside the frame stream and
the host would parse it as traffic.

| Command | Answer |
| --- | --- |
| `S0`-`S6`, `S8` | CR — 10k, 20k, 50k, 100k, 125k, 250k, 500k, 1M |
| `S7`, `S9` | BEL — 83.3k is absent from the SDK, and S7 means 800k to LAWICEL but 750k to python-can |
| `S<n>` while open | BEL — the controller cannot retime a running channel |
| `O` / `L` | CR — normal / listen-only |
| `O` / `L` while open | BEL — close first |
| `C` | CR, including on an already closed channel |
| `F` | `F<hh>` — overrun, error-passive, arbitration lost, bus error, bus-off |
| `V` | `V0100` |
| `t` `T` `r` `R` `x` | BEL, always |

```bash
.venv/bin/pio test -e native-slcan
.venv/bin/pio run -e esp32c3-slcan
# Only after identifying the ESP32 and physically disconnecting CAN:
.venv/bin/pio run -e esp32c3-slcan -t upload --upload-port /dev/serial/by-id/ESP32_DEVICE
```

The link carries text: an extended frame costs 27 characters. That is comfortable at bench
cadence, but a saturated bus will outrun it and slcan reports neither the loss nor any bus
error — `F` is polled, never pushed. For exhaustive capture and real error frames, use an
adapter exposing a native CAN interface.

## No-ACK self-test (diagnostic only, never an acceptance test)

`esp32c3-buttons-noack` is the three-button image built with `TWAI_MODE_NO_ACK`. The
controller reports every transmission as successful **without any acknowledgement on the
bus**. It exists for one question only: when a normal-mode run fails with `TX_FAILED`,
`tx_error_counter=8` and `bus_error_count=1`, is the fault inside the ESP32/transceiver, or
beyond it? Bitrate, pins, frame and single-shot behaviour are identical to `esp32c3-buttons`.

Read the result strictly:

| Blue button in NO_ACK | Conclusion |
| --- | --- |
| 10 frames reported transmitted | Controller, transceiver and bit timing are sound. The fault is beyond the transceiver: CANH/CANL/GND wiring, termination, or the receiver's configuration. |
| Still `TX_FAILED` | The fault is at or before the transceiver: its 3.3 V supply, the TX line, or the transceiver itself. Nothing about the receiver is proven either way. |

Both the banner and every `status` sample carry `selftest=no_ack ack_required=0`, so a
captured log can never be mistaken for an acknowledged run. Both of those need a USB host,
and this image is routinely used without one — so the activity LED, the only output left in
that case, stutters its pulse here instead of emitting the steady flash of a genuine
acknowledged run. A "pass" here says nothing about
the receiver or the wiring beyond the transceiver, and this image must never be used to
declare hardware acceptance. Reflash `esp32c3-buttons` as soon as the diagnostic is done.

```bash
.venv/bin/pio test -e native-noack
.venv/bin/pio run -e esp32c3-buttons-noack
# Only after identifying the ESP32 and physically disconnecting CAN:
.venv/bin/pio run -e esp32c3-buttons-noack -t upload --upload-port /dev/serial/by-id/ESP32_DEVICE
```

## Operator commands (manual profile)

Wait for the `BENCH ONLY` banner before entering commands. On a newly detected USB connection,
buffered input is discarded so old commands cannot activate transmission. Send lowercase commands
terminated by LF (or CRLF); terminal settings that send CR alone will not execute a command.

| Command | Behavior |
| --- | --- |
| `help` | Show the bench-only warning, fixed frame and commands; never transmit |
| `status` | Show state, configuration, counters, last fault and dropped log count |
| `start` | Assert charger disconnection, start the controller and wait one second before first attempt |
| `stop` | Cease controller activity and abort pending work; safe to repeat |

The frame is extended Classical CAN ID `0x001ABCDE`, DLC 8, bytes
`01 02 03 04 05 06 07 08`, at 125 kbit/s, at most once per second.
Repeated `start` does not accelerate it. No CAN FD, RTR, editable payload or automatic retries.
An invalid command does not change the current state: use `stop` explicitly to stop a running test.
Lines longer than 32 characters are rejected in full, including any apparent command at the end.

On the isolated two-node bench, the CANable must supply ACK (normal mode). A genuinely
listen-only receiver does not ACK. Single-shot transmission may then fail even if it received
the frame. **Never copy this normal-mode receiver configuration to a charger bus.**

`queued` counts accepted submissions, not successful transfers. `transmitted` increments only
after the controller reports TX_SUCCESS; inspect the receiving application separately.
`failed` counts rejected submissions or failed/timed-out pending attempts. `aborted` counts
operator/USB-loss cancellations. Counters and last fault are process-lifetime diagnostics
(reset with the MCU), not persisted. Faults without a pending attempt do not inflate failed counts.

Any failure or 250 ms completion timeout latches Fault and stops the controller. A simultaneous
error wins over success. A completion observed at/after the deadline is conservatively treated
as a timeout because the SDK alert has no per-frame timestamp. There is no automatic restart.
After inspecting the bench, `stop` retries cleanup; only successful cleanup without bus-off allows
a fresh `start`. Bus-off requires an MCU reset. `TX_FAILED` alone cannot identify a missing ACK.
Stopping during an on-wire frame can truncate it; a peer may report an error for that final attempt.

USB loss stops transmission **when the SDK reports disconnection**. Closing a terminal while
leaving USB powered is host/driver dependent and is not a guaranteed interlock. Always send
`stop` before closing the monitor, and verify physical behavior during acceptance. Reopening the
terminal never intentionally restarts emission. Power-up/reset GPIO behavior before `setup()` is
outside the firmware's control: never connect this generator to a charger.

## Desktop application checks

### Retained CAN diagnostics

Every `status` also reports `twai_snapshot=last_poll` and raw alert bits, followed by
the retained controller state and error counters. The snapshot is taken during polling,
before fault cleanup; it survives driver uninstall and late USB attachment, not MCU reset.
It is not a live measurement after stopping. A new permitted start clears it.
`twai_snapshot=unavailable` means no poll yet; `alerts=unavailable` or
`twai_status=unavailable` means that SDK read failed, not that counters are zero.

`twai_state` uses the pinned SDK values: 0 stopped, 1 running, 2 bus-off, 3 recovering.
Counters include TX/RX error counters, failed TX, missed/overrun RX, lost arbitration and
bus errors. They are clues only: none uniquely proves a missing ACK or bad wiring.
Output remains best-effort and bounded. If USB was absent or full, request `status` again
after connecting; this never starts CAN. Activation and stop-on-first-error are unchanged.

From the repository root, keep running the existing checks independently:

```bash
QT_QPA_PLATFORM=offscreen .venv-test/bin/pytest
.venv-test/bin/ruff check .
.venv-test/bin/mypy
```

The existing CI remains Python-focused; native firmware tests and cross-compilation are manual
checks in this change. No CI pipeline was modified.
