# ESP32-C3 / 3.3 V transceiver / CANable bench

> **Status**: three-button firmware flashed. Blue scenario (`reference125`) accepted on
> 2026-09-10: ten `0x001ABCDE` frames at 1 Hz received by the CANable, ESP32 reporting
> `transmitted=10 failed=0` with `tx_error_counter=0` and `bus_error_count=0` throughout,
> clean stop and no eleventh frame. Confirmed in Cangaroo on ttyACM0 at 125 kbit/s over
> three consecutive series (30 frames, 0 failures), deltas measured 0.9995–1.0006 s. An LED
> flash on GPIO8 accompanies each frame the controller counts as transmitted — here, each
> acknowledged frame; under `esp32c3-buttons-noack` the same counter advances with nothing on
> the bus, so that image stutters the pulse instead. White scenario (`varied125`) accepted
> the same day: twelve frames, `run_transmitted=12 run_failed=0`, IDs rotating
> `…DE`/`…DF`/`…E0`, first byte `00`–`0B` with no gap, second byte tracking the ID, tail
> `AA 55 00 FF 12 34`, deltas 0.9991–1.0009 s. Red scenario (`reference250`) accepted the
> same day once the CANable had been set to 250 kbit/s **directly over slcan** (`C`, then
> `S5` on a closed channel, then `O`): ten frames at 1 Hz, `run_transmitted=10
> run_failed=0`, all error counters zero, proving the controller reconfigures its bitrate
> between series without a reset. All three button scenarios are therefore accepted.
>
> **Cangaroo does not apply its bitrate setting to this adapter.** Selecting 250000 in its
> interface dialog left the CANable at 125 kbit/s; the ESP32 then reported
> `arb_lost_count=1` and `rx_error_counter=1`, the signature of an active node at the wrong
> speed, as opposed to the `tx_error_counter=8` with silent receive counters seen when
> nothing is on the bus at all. Use Cangaroo to watch traffic, never to configure it.
>
> **Manual profile**, observed 2026-09-10 while isolating that fault: with the CANable opened
> directly over slcan at 125 kbit/s, `start` produced eight frames at 1 Hz, each received as
> `T001ABCDE80102030405060708`, the ESP32 reporting `transmitted=8 failed=0` with
> `tx_error_counter=0` and `bus_error_count=0`. That evidences emission and acknowledgement
> only; steps 5-9 of its checklist below — stop, USB-loss behaviour, the absent-ACK test and
> bus-off handling — have not been run, so manual acceptance stays **open**.
> **Autonomous profile**: the operator reported correct reception of the fixed series on
> 2026-09-10, with no counter-level record kept, so its acceptance stays **open** as well.
> **Scope**: isolated bench only, never connected to a charger or vehicle.

## Before power

- Stop Cangaroo and any other program using the CANable.
- Physically disconnect the CANable from the charger using the site's safe isolation procedure.
- Remove USB power from both boards before wiring. Use soldered headers or a suitable reliable
  prototype fixture; do not wedge loose wires into the unpopulated ESP32 holes.
- Verify the transceiver board labels and its 3.3 V supply. The photographs show those labels
  and a resistor marked `121` beside `120R`, but do not prove the IC identity or termination wiring.

| ESP32-C3 Super Mini | Transceiver board |
| --- | --- |
| `3.3` | `3.3V` |
| `G` | `GND` |
| GPIO `4` | `TX` (transceiver input) |
| GPIO `3` | `RX` (transceiver output) |

| Transceiver / common reference | CANable |
| --- | --- |
| `CANH` | `CAN-H` |
| `CANL` | `CAN-L` |
| Common `GND` | `GND` |

TX goes to TX, RX to RX on this transceiver, unlike crossing two UART endpoints.
Leave both boards' 5 V terminals unconnected to each other. Power each controller through its
own USB; power the transceiver from the ESP32 3.3 V rail only. Keep leads short and twist CANH/L.

Use one 120-ohm termination at each end. Verify whether the transceiver's resistor is connected
before adding another. Enable the CANable termination only after identifying its switch position.
If a meter is available, measure with the entire bench unpowered: approximately 60 ohms between
H and L indicates two parallel 120-ohm terminators. Do not claim this is verified from photos.
The transceiver's two yellow CANH/CANL pins are **not** a termination-enable jumper: never short them.

## Autonomous reception session

Use the explicitly selected [autonomous firmware profile](../../firmware/esp32c3-can-bench/README.md#autonomous-profile-explicit-opt-in)
when the ESP32 is powered separately instead of connected to a PC data port.

1. With all USB power removed, disconnect CAN before flashing. The upload reset arms a series.
2. Flash the identified ESP32 with `esp32c3-autonomous`, then remove its USB power.
3. Restore the isolated bench wiring, with both boards unpowered. Keep the charger disconnected.
4. Connect only the CANable to the PC. Start Cangaroo reception at 125 kbit/s in normal mode.
5. Power the ESP32 via a separate USB supply. Do not connect the boards' 5 V pins together.
6. After about ten seconds, expect ten extended `0x001ABCDE` frames with bytes `01` through `08`,
   approximately one second apart, then no more frames. An error can stop the series early.
7. Observe for several more seconds after completion to confirm there is no eleventh frame.
8. Remove ESP32 power before any wiring changes. Reset/power cycling intentionally re-arms one
   series; opening a serial monitor is unnecessary. Never transfer this automatic image to a charger bus.

The operator reported approximately 60 ohms between H and L with power removed on 2026-09-10.
This is consistent with the expected termination, not proof of correct wiring or communication.

## Three-button acceptance session

Use the [buttons profile](../../firmware/esp32c3-can-bench/README.md#three-button-profile-explicit-opt-in),
not the autonomous image. The maintainer approved GPIO0/1/5 and reported wiring completed;
this is not an electrical verification of the prototype carrier or switch contacts.

1. Remove USB power before wiring changes; keep this entire bench disconnected from the charger.
   Blue connects GPIO0 to GND, red GPIO1 to GND, white GPIO5 to GND, using normally-open contacts.
   For four-leg switches, identify the switching pair: some legs are already electrically common.
2. Identify the ESP32's stable USB path and flash `esp32c3-buttons` with CAN disconnected.
   The old autonomous firmware may emit on reset until replaced. Do not flash the CANable.
3. Power down, restore the isolated bench wiring, then prepare CANable reception in normal mode
   at 125 kbit/s. Clear old traces and disable aggregation when checking exact frame counts.
4. Power the ESP32. With buttons released, expect no generated frames, even after ten seconds.
   Optional USB `status` should report `buttons=ready scenario=none` after the release interval.
5. Press blue: expect ten `0x001ABCDE` frames with bytes `01 02 03 04 05 06 07 08`, at 1 Hz.
   First frame is approximately one second after the press; no eleventh frame. Holding blue
   must not restart the series. Release and press again to run another series.
6. Stop capture, apply 250 kbit/s on the receiver, restart capture and clear old traces.
   Press red: expect the same ten frames. Optional ESP32 status must show `bitrate=250000`
   and `scenario=reference250`. The receiver must actually apply its setting; the previous
   screenshot labelled 250 kbit/s while receiving the old 125-kbit/s image does not prove this.
7. Return receiver to 125 kbit/s, start a clean capture, then press white: expect twelve frames,
   four each for IDs `0x001ABCDE`, `0x001ABCDF`, `0x001ABCE0`. The first data byte increments
   from `00` through `0B`; second byte cycles `00`, `01`, `02`; remaining bytes are
   `AA 55 00 FF 12 34`.
8. Check held-at-boot, simultaneous presses, and presses during a running series: no unexpected
   series may start. Release all buttons before trying another deliberate press.
9. Only on this isolated bench, test a deliberately mismatched receiver bitrate after verifying
   settings are applied. Expect no valid new reception at that receiver; ESP32 should stop on
   failure/timeout without retry. Inspect its status instead of diagnosing from a blank trace.
   Correct receiver configuration, then reset ESP32 and release buttons before retrying.
10. Verify optional USB `stop` cancels a run, and unplugging the USB data connection (while
    maintaining power) does not. A faulted runner remains faulted after `stop`; reset is required.

Record results as hardware observations separately from native test results. Software tests
do not prove switch wiring, electrical timing, CAN acknowledgement or receiver configuration.

## No-ACK self-test session (diagnostic, not acceptance)

Use the [no-ACK self-test image](../../firmware/esp32c3-can-bench/README.md#no-ack-self-test-diagnostic-only-never-an-acceptance-test)
only to localise a persistent transmission failure. It reports success without any bus
acknowledgement, so it can never establish that a receiver or the wiring works.

1. Remove USB power, keep the charger disconnected, and physically disconnect CAN before
   flashing `esp32c3-buttons-noack`. Do not flash the CANable.
2. Restore the isolated bench wiring with both boards unpowered. The receiver may stay off:
   this test does not need one, which is precisely the point.
3. Power the ESP32, open the USB monitor, confirm the banner and `selftest=no_ack` in `status`.
4. Press blue alone. Ten reported transmissions mean the controller, the transceiver and the
   bit timing are sound, and the fault lies beyond the transceiver — wiring, termination or
   receiver configuration. A `TX_FAILED` here means the fault is at or before the transceiver.
5. Record the outcome as a diagnostic observation only, then reflash `esp32c3-buttons` before
   any further acceptance work. Never leave this image on a board that could reach a bus.

Observed on 2026-09-10, before this test existed: with Cangaroo at 125 kbit/s and listen-only
disabled, a blue press produced `alerts=0x00000400`, `tx_error_counter=8`,
`bus_error_count=1`, `arb_lost_count=0`, with all counters clean at driver install. That is an
acknowledgement error, and it did not change after the operator retightened the prototype
contacts.

The self-test was then run on 2026-09-10 with the bench wired as-is: blue press, ten of ten
frames reported transmitted, `run_failed=0`, and `tx_error_counter=0`, `bus_error_count=0`,
`arb_lost_count=0` throughout, ending on `alerts=0x00000002` (TX_SUCCESS) and a clean stop
after exactly ten. The controller, the transceiver and the bit timing are therefore sound,
and the TX/RX loop through the transceiver is electrically consistent. This does **not**
prove that the differential pair reaches the CANable: the remaining fault domain is the
CANH/CANL/GND wiring between transceiver and CANable, the termination, and the CANable's own
configuration. `esp32c3-buttons` was reflashed immediately afterwards.

Root cause, found on 2026-09-10 after the self-test: **the transceiver had lost its 3.3 V
supply**, compounded by a stale `slcand` that had held the CANable's tty since 2026-09-09
11:16 without any `-s` bitrate option. The stale line discipline silently swallowed every
later configuration attempt, including Cangaroo's `S<n>`/`O` sequence — which is why a
capture labelled 250 kbit/s had still shown 125-kbit/s traffic. Two diagnostic traps cost
time and are worth remembering: `candump` echoes locally sent frames, so only
`ip -s link show can0` RX counters prove reception; and an unpowered transceiver reads
0 V on both CANH and CANL at rest instead of the ~2.4 V recessive bias, while still passing
a NO_ACK self-test performed before the supply was disturbed. The ESP32 firmware was never
at fault: its pins, timing, frame and single-shot behaviour never changed.

## Manual-profile acceptance session

1. Identify the ESP32 alone over USB and confirm MCU/flash before uploading the
   [bench firmware](../../firmware/esp32c3-can-bench/README.md). Never flash the CANable by mistake.
2. With the completed bench powered, open Cangaroo on the CANable at 125 kbit/s, normal mode
   to provide ACK. This is allowed only on the physically separate bench. Do not click Send.
3. Open the ESP32 monitor, wait for the bench-only banner and run `status`. State must be stopped.
   Confirm no generated frames before `start`, including after `help` and repeated `stop`.
4. Run `start`. Expect the first extended frame after about one second, then approximately 1 Hz:
   `0x001ABCDE [01 02 03 04 05 06 07 08]`. Compare both USB counters and the receiver trace.
5. Run `stop`. Verify the counter stops increasing and no new attempts appear at the receiver.
6. Verify USB loss/reset stops emission, and reconnect does not restart it. Test terminal close
   separately: the SDK's connected indication is host-dependent. Always stop before closing it.
7. For an absent-ACK test, stop and power down before disconnecting the receiver's CAN leads.
   Restart the ESP32 test. Expect failure/timeout and Fault with no automatic retries. The
   exact error cannot be diagnosed from TX_FAILED alone. Stop and power down before reconnecting.
8. After cleanup, a fresh `start` is required. Bus-off requires MCU reset and inspection.
9. Only after Cangaroo reception succeeds, stop it and configure the CANable's compatible
   SocketCAN path separately. Then select that interface in busscope. Never run two serial
   clients on the CANable simultaneously; the desktop app does not accept `ttyACM*` directly.

Record pass/fail and software versions locally, without identifying charger data. Hardware
acceptance remains open until these observations have actually been made.

## References

- [Approved bench specification](../architecture/specs/esp32c3-can-bench.md)
- [ESP32-C3 TWAI](https://docs.espressif.com/projects/esp-idf/en/v4.4.7/esp32c3/api-reference/peripherals/twai.html)
- [SN65HVD230](https://www.ti.com/product/SN65HVD230)
- [CANable identification and safety](canable-2.0.md)

## Bench outage, 2026-09-11

After both USB cables were replaced and the CAN wiring reseated, the bench stopped
communicating in either direction. The evidence, in the order it was gathered:

- Transceiver supply 3.3 V present; CANH and CANL biased to 2.3 V at its terminal.
- CANH to CANL measures 68 ohms with everything unpowered, as it did when the bench worked,
  so both terminations are in circuit and the pair is continuous end to end.
- Continuity confirmed CANH to CAN-H and CANL to CAN-L, with no crossing.
- The ESP32 reports `tx_error_counter=8`, `bus_error_count=1`, `rx_error_counter=0` on every
  attempt: an acknowledgement error with nothing else on the bus.
- The reverse direction is equally silent — `cansend` frames leave the kernel and the ESP32
  receiver records `received=0` with **all error counters at zero**, meaning no signal at all
  reaches its RX pin, not even malformed signal.
- Three independent host-side methods behave identically: raw pyserial at 1 Mbaud with pauses
  (the exact sequence that produced ten of ten frames earlier the same day), python-can's
  slcan backend at 1 Mbaud, and the same at its default 115200. That rules out the host
  software, including the capture work of #48.

Leading hypothesis, untested: the CANable's CAN transceiver is dead while its USB side still
enumerates and answers `V`. A termination resistor is passive and still measures 68 ohms on
the same pins, and a high-impedance node produces no bus errors — which is consistent with
every observation above. The discriminating measurement is to isolate the CANable from the
bench, leave it USB-powered, and read CANH and CANL against its own ground: a healthy
transceiver biases them to roughly 2.5 V, a dead one reads 0 V.

A transceiver can be destroyed by a brief contact between CANH/CANL and a supply rail during
rewiring, which is the manipulation that immediately preceded the outage.
