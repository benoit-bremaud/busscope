# ESP32-C3 slcan sniffer profile

> **Feature**: [Issue #50](https://github.com/benoit-bremaud/busscope/issues/50)
> **Status**: conception approved 2026-09-11 and implemented in the same pull request.
> The protocol was exercised on the board; capture against real traffic is outstanding.

## Purpose and boundary

Turn the ESP32-C3 into a receive-only CAN adapter whose silence is guaranteed by the
controller rather than promised by a command, so `busscope` can observe a bus nobody owns
through the backend shipped in #49, with no application change.

It does not transmit, decode charger protocols, determine an unknown bitrate, or deliver bus
error frames. The bench generator profiles are untouched.

## Problem

`docs/hardware/canable-2.0.md` records that the CANable's SLCAN firmware does not guarantee
the LAWICEL `L` command and acknowledges no command at all, which is why #49 had to make
listen-only an explicit operator acceptance rather than a verified fact. The adapter also
stopped communicating on 2026-09-11.

The ESP32-C3 already on the bench offers what that firmware cannot. The SDK defines
`TWAI_MODE_LISTEN_ONLY` as a controller mode that "will not influence the bus (No
transmissions or acknowledgments) but can receive messages" — enforced by the peripheral.

## Requirements

- L1: No transmit path exists. `t`, `T`, `r`, `R` and `x` are answered with BEL in every
  state, and no code in the profile submits a frame. This is what makes the image pointable
  at a bus the operator does not own, unlike the generator profiles. `N`, the serial-number
  query, is refused too: this adapter carries no serial number, and answering with a version
  would be a wrong answer wearing the shape of a right one.
- L2: `L` installs `TWAI_MODE_LISTEN_ONLY`; `O` installs `TWAI_MODE_NORMAL`, which
  acknowledges and exists for the two-node bench where nothing else would acknowledge the
  generator. The active mode is reported, never assumed.
- L2b: A latched bus-off forbids reopening in normal mode, as it does for every transmitting
  profile, but not in listen-only: that mode cannot influence the bus, so refusing it would
  only strand the operator with no way to observe what went wrong, on a profile that
  deliberately prints no diagnostic. The latch is dropped only once a listen-only start has
  actually succeeded — a failed attempt must leave it standing, or the next normal-mode open
  would slip through a guard the bus-off still holds shut — and is re-raised by the next poll
  if the controller is still off the bus.
- L3: Every command is answered — CR on success, BEL on refusal — including a bare
  terminator, which python-can writes on every `set_bitrate`. A silent adapter makes
  "applied" indistinguishable from "ignored", which is what made the CANable undiagnosable
  and cost a full day of bench time, so the rule admits no exception.
- L4: Only rates the controller can produce are accepted. It offers 10k, 20k, 50k, 100k,
  125k, 250k, 500k, 800k and 1M, so exactly two codes are refused: `S9` at 83.3k, absent from
  the SDK, and `S7`, which LAWICEL and the SDK read as 800k while python-can sends it for
  750k. An ambiguous code is refused rather than resolved by assumption, and no code is ever
  substituted by a neighbour.
- L5: A bitrate is accepted only while the channel is closed, and opening an open channel is
  refused. The controller cannot retime a running channel, so accepting either would report a
  configuration that was never applied.
- L6: `C` always reaches the driver and reports what cleanup actually returned. Closing a
  closed channel succeeds, but the command is never short-circuited: an earlier cleanup may
  have failed with the driver still installed, and `C` is the only command able to retry it.
- L6b: The receive queue holds 32 frames in listen-only mode. One slot suits the generator
  profiles, which keep a single frame in flight; a sniffer must absorb a burst between two
  loop iterations, and the driver silently counts what it drops.
- L6c: A protocol line is written whole or not at all. Half a frame would be parsed by the
  host as a different frame and half a reply as no reply, so a line the link cannot take is
  refused and reported on LAWICEL bit 0, the receive-queue overrun — which is exactly what a
  dropped frame line is. Draining stops at the first refusal rather than pulling frames out
  of the driver only to discard them, which would hide the loss from its own counters.
- L7: The profile writes protocol bytes and nothing else. No banner, no status line, no
  logger — any human-readable output would arrive inside the frame stream and be parsed by
  the host as traffic.
- L8: `F` answers the LAWICEL status byte built from the driver counters: receive overrun,
  error-passive derived from the 128 threshold, arbitration lost, bus error and bus-off. When
  no snapshot is readable it reports no flags rather than inventing them.
- L8b: Counter flags describe what happened **since the previous read**; state flags describe
  the controller **now**. Real slcan firmware clears its flags on read, and the driver's
  counters only ever grow: reporting them raw would mean one arbitration loss at startup
  pinned that bit for the rest of the session, so the host could never observe the bus
  recovering. A new session starts from a clean slate rather than inheriting the last one's.
- L9: A start that fails releases the driver, so a later open cannot fail for a reason
  unrelated to the bus. `F` on a closed channel reports no flags rather than replaying the
  previous session's, since the driver snapshot deliberately survives cleanup. A frame with a non-compliant DLC is clamped to eight rather than
  driving a read past the payload: ISO 11898-1 makes 9-15 legal, each meaning eight data
  bytes, so a sniffer shows the frame where a generator treats it as a fault worth stopping
  for. The policy travels with the call, leaving the generator profiles strict.

## Design

`lib/bench/slcan.{h,cpp}` holds the protocol: a line parser, a frame encoder, the status byte
and the session that drives a channel. It includes no SDK header, so all of it runs under the
native suite. The session talks to `SlcanChannelPort`, whose two implementations are
`TwaiSlcanChannel` in production and a double in tests — the same shape as `CanPort`.

`bench::Bitrate` was extended to name every rate the controller can produce and is now the
single source of truth shared by the codec, the adapter and the scenarios; `TwaiPort` maps
each to its SDK timing config and refuses anything outside the enum.

`BENCH_SLCAN` selects the profile, mutually exclusive with the other four and rejected at
compile time alongside `BENCH_NO_ACK`, which fabricates acknowledgements and is the opposite
of what a receive-only sniffer promises. The loop reads a
bounded number of input bytes, then drains a bounded number of frames, and writes only what
the session returns.

## Verification and traceability

| Requirement | Automated evidence | Hardware evidence |
| --- | --- | --- |
| L1 | Transmit refused in every state; `sdk.transmits` stays zero | `T…` and `t…` answered BEL on the board |
| L2 | Mode reaching the driver asserted per request | `L` accepted, mode installed |
| L3 | Every command's exact reply asserted | Every reply observed over USB |
| L4 | Each supported code maps to its own timing config; `S7`/`S9` refused | `S4` accepted, `S7`/`S9` refused |
| L5, L6 | Bitrate and reopen refused while open; close idempotent, reaches the port, and a refused cleanup is reported | Both observed on the board |
| L7 | Output asserted byte-exact, empty until spoken to | No human-readable byte seen |
| L8, L8b | Each counter mapped to its flag; a settled fault clears on the next read while a state persists; unreadable snapshot yields zero | `F00` before and after a session |
| L2b | Normal-mode reopen refused after bus-off, listen-only allowed and the latch re-raised | — |
| L9 | Failed start uninstalls; DLC above eight clamped | — |

Native coverage of authored code stays at or above 90%; all six images must build.

### What the bench can and cannot prove

The protocol was exercised on the board and every designed behaviour matched. Capture against
real traffic was **not** proven: the bench holds a single node, since the ESP32 is the sniffer
and the CANable that would generate traffic is disconnected and suspected faulty. Zero frames
captured is the expected result there, not a passing test.

That `L` actually silences the adapter on the wire also remains unproven, and can only be
shown on a bus carrying two other active nodes. The difference from #49 is the nature of the
guarantee: here silence is a controller mode the SDK defines, not a command a third-party
firmware may ignore.

## Known limitation

slcan is text over a serial link. An extended frame costs 27 characters, so the USB CDC link
is comfortable at bench cadence but a saturated bus will outrun it, and the protocol reports
neither the loss nor any bus error — `F` is polled, not pushed. Exhaustive capture and real
error frames need an adapter exposing a native CAN interface.

## References

- [UML views](../diagrams/esp32c3-slcan/)
- [Issue #50](https://github.com/benoit-bremaud/busscope/issues/50)
- [CANable 2.0 notes](../../hardware/canable-2.0.md)
- [slcan capture backend](slcan-capture.md)
