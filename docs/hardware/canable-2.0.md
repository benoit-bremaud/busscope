# CANable 2.0 compatible adapter bring-up

This checklist prepares the ordered USB-C CANable 2.0 compatible adapter for BusScope. Treat
the board as a clone until its USB identity, firmware, terminal labels, and termination switch are
verified on arrival.

## Safety prerequisites

- Perform identification with the CAN terminal disconnected.
- Verify the terminal labels on the received board instead of relying on the product photo.
- Treat the low-cost clone as non-isolated until its schematic or a physical inspection proves
  galvanic isolation. Verify the charger's CAN reference before connecting grounds.
- Never connect the adapter's 5 V output unless a separately reviewed target-powering procedure
  explicitly requires it.
- Connect only CANH, CANL, and the signal reference required by the charger documentation.
- Enable the onboard 120-ohm termination only when the adapter is at an otherwise unterminated end
  of the bus. Do not add a third terminator to an already terminated bus.
- Validate passive capture before changing the interface to a transmission-capable mode.

## 1. Identify the installed firmware

Connect USB only, then record:

```bash
lsusb
sudo dmesg --follow
ip -details link show
find /dev -maxdepth 1 \( -name 'ttyACM*' -o -name 'ttyUSB*' \) -print
```

Interpret the result:

- a native `can0` interface normally indicates candleLight firmware using the Linux `gs_usb`
  driver;
- a new `/dev/ttyACM*` or `/dev/ttyUSB*` without `can0` normally indicates SLCAN firmware.

For a native interface, confirm the driver when supported:

```bash
ethtool -i can0
```

Do not flash firmware merely because the adapter uses SLCAN. Both paths can expose a SocketCAN
channel to the application.

## 2A. Configure native candleLight / gs_usb for passive capture

```bash
sudo ip link set can0 down
sudo ip link set can0 type can bitrate 125000 listen-only on
sudo ip link set can0 up
ip -details -statistics link show can0
```

Observe traffic before starting BusScope:

```bash
candump -e -x can0
```

## 2B. Handle SLCAN firmware before passive capture

The CANable 2.0 SLCAN firmware documents speed `4` as 125 kbit/s, but its published command list
does not guarantee the LAWICEL `L` listen-only command and the firmware provides no serial command
acknowledgement. Therefore, do not treat `slcand -l` or a successfully created network interface
as proof that this clone is electrically silent.

Keep the CAN terminal disconnected and identify the exact USB identifiers, MCU, firmware source,
and supported silent-mode command. If silent mode cannot be proven, use an isolated CAN test bench
or install a verified compatible candleLight firmware before connecting to the live charger. Do
not silently fall back to normal mode for the first physical session.

## 3. Validate read-only BusScope operation

With valid passive traffic visible in `candump`, start the application and select `can0`:

```bash
.venv/bin/busscope
```

Confirm that extended Infypower frames contain eight bytes and that decoded values are plausible.
Record no real capture in the repository.

## 4. Prepare an explicitly authorized transmission session

Complete this step only after wiring and passive capture are validated. Stop BusScope and
`candump` before reconfiguring the interface.

For candleLight / `gs_usb`:

```bash
sudo ip link set can0 down
sudo ip link set can0 type can bitrate 125000 listen-only off one-shot on
sudo ip link set can0 up
ip -details -statistics link show can0
```

The final output must contain `ONE-SHOT` and must not contain `LISTEN-ONLY`. The one-shot mode
disables controller-level automatic retransmission; calling a userspace send function once does
not disable CAN controller retries by itself.

For SLCAN, transmission remains disabled unless the exact firmware and Linux driver combination
exposes a verifiable `ONE-SHOT` mode through SocketCAN. If `one-shot on` is rejected or the mode is
absent from the detailed interface state, use verified candleLight/`gs_usb` firmware instead.

The application never executes these privileged configuration commands. It performs only a
read-only `ip -details -json` readiness check immediately before sending and fails closed if
`ONE-SHOT` cannot be verified. Its Transmission tab remains disabled at startup and still
requires confirmation for each eight-byte extended frame.

## 5. Recovery and evidence

If the interface enters `BUS-OFF`, reports growing errors, or disappears, stop transmission,
disconnect the CAN terminal, and collect only non-sensitive diagnostics:

```bash
ip -details -statistics link show can0
dmesg | tail -n 50
```

Do not commit logs containing charger identifiers or captured payloads.

## References

- [CANable getting started](https://canable.io/getting-started.html)
- [CANable 2.0 SLCAN firmware commands](https://github.com/normaldotcom/canable2-fw)
- [candleLight gs_usb-compatible firmware](https://github.com/candle-usb/candleLight_fw)
- [Linux SocketCAN documentation](https://docs.kernel.org/networking/can.html)
- [Linux can-utils](https://github.com/linux-can/can-utils)
