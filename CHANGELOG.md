# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Renamed from can-sniffer to BusScope: the package, distribution and command are now
  `busscope`. Display preferences saved under the old application name are not migrated.

### Added

- Native slcan capture backend, so a serial CAN adapter can be used without configuring a
  SocketCAN interface first.
- Opt-in ESP32-C3 CAN test generator firmware for validating a capture chain against known
  traffic on a bench, with autonomous, button-driven, manual and receive-only profiles, plus a
  `NO_ACK` self-test image that proves the controller, transceiver and bit timing without needing
  a second node.
- ESP32-C3 receive-only slcan sniffer profile whose silence is enforced by the controller
  (`TWAI_MODE_LISTEN_ONLY`) rather than promised by a command, and which refuses every transmit
  request in every state.

### Changed

- Listen-only capture is now either verified or explicitly accepted rather than assumed. On
  SocketCAN the controller mode is read back from the interface and capture fails closed unless
  listen-only is confirmed; on slcan, where no adapter acknowledgement exists, the operator must
  accept the unverified mode deliberately.

## [0.1.1] - 2026-09-04

### Added

- Guarded one-attempt transmission of manually entered 29-bit extended CAN frames.
- Infypower module topology decoding for module count and group number.

### Changed

- Offline CSV replay now restores all supported semantic protocol values from raw CAN frames while
  preserving stored descriptions and current-first diagnostics. The presentation-only
  `decoded_values` column remains ignored.

### Security

- Manual transmission is disabled at startup, requires explicit confirmation for every frame, and
  fails closed unless controller-level `ONE-SHOT` mode is verified on physical interfaces.

## [0.1.0] - 2026-09-04

### Added

- Read-only SocketCAN capture for Linux CAN interfaces and virtual CAN testing.
- Infypower V1.13 decoding for system and module measurements, module state, AC input voltages,
  module ratings, and available output capacity.
- Graphical capture controls, identifier filtering, display pause, retained-history clearing, and
  deterministic CSV export.
- Per-identifier temporal statistics, including frequency, period, interval range, and maximum
  cadence deviation.
- Validated offline replay of exported CSV captures without opening a CAN interface.
- Persistent display preferences for identifier format, numeric precision, raw payloads, decoded
  values, diagnostics, and temporal statistics.
- Isolated Python development and test environments with pytest, Ruff, strict mypy, and a 90%
  coverage gate.

### Security

- CAN transmission is not exposed; the first release remains read-only and listen-only by default.
- GitHub Actions checks code quality, secrets, static analysis, dependency changes, and repository
  security posture.

[0.1.1]: https://github.com/benoit-bremaud/can-sniffer/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/benoit-bremaud/can-sniffer/releases/tag/v0.1.0
