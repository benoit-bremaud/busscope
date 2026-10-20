# BusScope

**The stethoscope for your buses.**

BusScope is a multi-bus observation tool for EV-charging equipment: a USB box with
isolated CAN / CAN FD, RS485, RS232, UART and CP/PP ports, driven by one desktop application.
Like a stethoscope, it listens to a bus: capture is listen-only by default, and the only way
to send a frame is the guarded manual transmission described below, disabled at every startup. The box is being designed
(see [`docs/decisions/`](docs/decisions/README.md)); this release ships the CAN monitor below.

Today BusScope is a graphical CAN bus monitor for Infypower charger modules on Linux.

The charger protocol documented in the supplied V1.13 specification uses CAN 2.0B,
29-bit extended identifiers, 8-byte payloads, and a bitrate of 125 kbit/s.

The application supports read-only SocketCAN capture, Infypower frame decoding, capture filtering,
temporal statistics, CSV export, offline CSV replay, persistent display preferences, and guarded
one-attempt manual transmission.

Display preferences are available from the **Settings** tab. They control identifier format,
numeric precision, raw payloads, decoded values, diagnostics, and temporal statistics. Changes
are stored locally and restored on the next launch; they never affect captured data or CAN bus
operation.

Manual transmission is disabled at every startup. Each request must contain one 29-bit extended
identifier and exactly eight bytes, then requires explicit confirmation. Physical interfaces must
be configured externally with controller-level `ONE-SHOT` enabled; the application verifies this
state immediately before sending and otherwise fails closed. See
[`docs/hardware/canable-2.0.md`](docs/hardware/canable-2.0.md) before connecting hardware.

## Development

Never commit credentials, local configuration, or real captures.

Install the project and development dependencies in the work environment with:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

Use the separate test environment for isolated validation:

```bash
python3 -m venv .venv-test
.venv-test/bin/python -m pip install -e '.[dev]'
```

Run the quality checks from `.venv-test`:

```bash
.venv-test/bin/pytest
.venv-test/bin/ruff check .
.venv-test/bin/mypy
```

The same quality checks run automatically on pushes to `main` and on pull requests. GitHub
Actions also runs secret detection, CodeQL analysis, dependency review, and OpenSSF Scorecard.

Start the graphical application from the work environment:

```bash
.venv/bin/busscope
```

For a hardware-free smoke test, create a virtual CAN interface and run the application on
`vcan0`:

```bash
sudo modprobe vcan
sudo ip link add dev vcan0 type vcan
sudo ip link set vcan0 up
.venv/bin/busscope
```

The current protocol decoder covers the documented Infypower system measurements, individual
module measurements, AC input voltages, module ratings, and available output capacity. The
module-measurement mapping is documented in
`docs/architecture/specs/module-measurements.md`.

## Contributing

For a standalone hardware test generator, see the
[ESP32-C3 CAN bench firmware](firmware/esp32c3-can-bench/README.md).
It is separate from the desktop application and restricted to a bench physically
disconnected from every charger. Its manual, three-button and receiver profiles stay silent
until an explicit operator action; the autonomous profile is the exception and deliberately
arms one bounded series after each boot or reset, so it is flashed only with CAN
disconnected. The three-button profile was hardware-accepted on 2026-09-10; the other
profiles have been observed working but their acceptance checklists remain open.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the project workflow and validation requirements.

## License

This project is licensed under the MIT License. See [`LICENSE`](LICENSE).
