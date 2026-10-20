# Project instructions

## Scope

`busscope` is a Linux desktop application for monitoring Infypower charger CAN traffic.
The first release is read-only and targets CAN 2.0B extended frames at 125 kbit/s.

The project is growing into a listen-only multi-bus USB box for EV-charging equipment plus a
desktop application (see [`docs/decisions/`](docs/decisions/README.md), ADR-0002). The current
PySide6 CAN monitor stays the shipped application until the new UI replaces it.

## Workflow

- Work from an Issue and a dedicated branch.
- Add or update UML design documentation before implementing a feature.
- Use Angular Conventional Commits: `type(scope): description`.
- Run tests, linting, and type checks before opening a pull request.
- Every feature must maintain at least 90% test coverage with happy-path, sad-path, and edge-case tests.
- Do not merge pull requests without explicit user approval.

## Safety

- Listen-only is the default operating mode.
- Frame transmission must remain disabled until explicitly designed, reviewed, tested, and enabled.
- Never commit `.env`, captures, credentials, or charger-identifying data.

## Project-specific architecture

Keep protocol decoding independent from PySide6, python-can, SocketCAN, and filesystem I/O.
Concrete CAN and UI adapters belong at the application boundary and depend inward on small
domain contracts. Prefer the smallest structure that supports testing and substitution.
