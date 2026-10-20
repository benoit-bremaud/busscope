# Project Log

Chronological operational logbook of `can-sniffer`. It complements `git log` and
[`CHANGELOG.md`](CHANGELOG.md): every merged pull request, tag, release, decision and direct
commit to `main` is recorded here with the context git does not capture. Entries from inception to
PR #57 were reconstructed retroactively (2026-10-20) from `git log`, merged pull requests, tags,
releases, `CHANGELOG.md` and the ADR register in [`docs/decisions/`](docs/decisions/README.md),
and checked against GitHub.

SHAs are 7-character merge (or squash) commits on `main`.

## 2026-09-01

- **Direct commit to `main`** (`a048e4a`) — `chore(repo): initialize project architecture`.
  Repository bootstrap before the PR workflow existed.
- **PR #2 merged** (`07a55d6`) — `feat(protocol): initialize CAN sniffer and decode Infypower frames`
  (branch `feat/initial-project-setup`). First decoder, independent of UI and CAN adapters.
- **PR #4 merged** (`f1118b3`) — `feat(protocol): decode individual module measurements`
  (`feat/decode-module-measurements`).
- **PR #6 merged** (`525d3a5`) — `feat(protocol): decode module AC input voltages`
  (`feat/decode-ac-input-voltage`).
- **PR #8 merged** (`f49dbfd`) — `docs(module-ratings): add UML design` (`docs/module-ratings-uml`),
  then **PR #9** (`da448ce`) — `feat(protocol): decode module ratings`
  (`feat/decode-module-ratings-v2`). First application of the design-before-code rule.
- **PR #11 merged** (`bea7d72`) — `docs(module-availability): add UML design`, then **PR #12**
  (`d781b8f`) — `feat(protocol): decode module availability`.

## 2026-09-02

- **PR #14 merged** (`f9be58e`) — `feat(capture): add read-only CAN capture UI`
  (`feat/can-capture-port`). PySide6 UI over a capture port; listen-only by default.
- **PR #16 merged** (`127dfd6`) — `feat(capture): add frame analysis controls and CSV export`.
- **PR #18 merged** (`2769b3b`) — `feat(capture): add temporal frame statistics`.
- **PR #20 merged** (`fdb2bb9`) — `feat(capture): add offline CSV replay`.
- **PR #21 merged** (`9d171bc`) — `docs(protocol): document individual module measurements`.
- **PR #22 merged** (`29be7a0`) — `ci(project): add quality and security workflows`
  (`codex/1-github-ci-quality-checks`). Quality, secrets, static analysis, dependency review and
  repository posture checks in GitHub Actions.
- **PR #24 merged** (`de7cd69`) — `docs(analysis/architecture): add cadence jitter design`, then
  **PR #25** (`2a86946`) — `feat(analysis): expose CAN cadence variation metrics`.

## 2026-09-03

- **PR #27 merged** (`c2e4def`) — `docs(settings/architecture): design persistent display preferences`.
- **PR #28 merged** (`a3c0ec5`) — `docs(settings/architecture): define preference loading validation`.
- **PR #29 merged** (`01c4b34`) — `feat(settings): add persistent display preferences`.

## 2026-09-04

- **PR #31 merged** (`600709f`) — `docs(release): prepare v0.1.0 documentation`.
- **PR #33 merged** (`b45e5ce`) — `docs(release): complete v0.1.0 publication prerequisites`.
- **Tag `v0.1.0`** on `b45e5ce`, GitHub release "can-sniffer v0.1.0" published. First release:
  read-only capture, decoding, replay, statistics, preferences (see `CHANGELOG.md`).
- **PR #35 merged** (`4371d30`) — `docs(architecture): design safe manual CAN transmission`, then
  **PR #36** (`096e16d`) — `feat(transmission): add guarded one-shot CAN sending`.
  - **Decisions**: `transmission fails closed` — disabled at startup, explicit confirmation per
    frame, refused unless controller `ONE-SHOT` mode is verified on physical interfaces.
- **PR #38 merged** (`1b3cb12`) — `docs(architecture): design module topology decoding`, then
  **PR #39** (`43455b5`) — `feat(protocol): decode module topology`.
- **PR #41 merged** (`7b1908e`) — `docs(architecture): design semantic replay decoding`, then
  **PR #42** (`1b2ca43`) — `feat(replay): preserve decoded protocol values`.
- **PR #44 merged** (`75c88a1`) — `chore(release): prepare v0.1.1`.
- **Tag `v0.1.1`** on `75c88a1`, GitHub release "can-sniffer v0.1.1" published.

## 2026-09-09

- **PR #46 merged** (`8c13409`) — `docs(bench/architecture): add ESP32-C3 CAN bench design`
  (`codex/45-esp32c3-bench-design`).

## 2026-09-11

- **PR #47 merged** (`3cfacde`) — `feat(bench): add the opt-in ESP32-C3 CAN test generator`.
- **PR #49 merged** (`f5c050b`, squash) — `feat(capture): add a native slcan backend with verified
  listen-only` (`codex/48-slcan-capture`).
  - **Decisions**: `listen-only verified or explicitly accepted` — SocketCAN capture fails closed
    unless the interface reports listen-only; slcan cannot confirm it, so the operator must accept
    the unverified mode deliberately.

## 2026-09-23

- **PR #51 merged** (`b928395`, squash) — `feat(firmware): add a receive-only slcan sniffer profile
  with hardware listen-only` (`codex/50-esp32-slcan-sniffer`).
  - **Decisions**: `silence enforced by the controller` — `TWAI_MODE_LISTEN_ONLY` rather than a
    command, and every transmit request refused in every state.
- **PR #52 merged** (`f625909`, squash) — `docs(changelog): record the four releases that were
  never written down` (`chore/changelog-slcan-sniffer`). Unreleased section brought up to date.

## 2026-10-20

- **PR #56 merged** (`a6c4f6f`) — `chore(sonar): configure local SonarQube analysis`
  (`chore/55-sonar-local`, closes #55). `sonar-project.properties` added; follow-ups documented the
  scanner prerequisite and token handling (`7d2145e`) and that the local analysis covers Python
  only (`e257c19`).
- **PR #57 merged** (`25eaabe`) — `docs(adr): record the multi-bus box, toolchain and UI decisions`
  (`docs/54-adr-multibus-box`, closes #54). MCDA totals corrected (`fff011a`); review round addressed scope, probe isolation and
  transmission wording (`fb1e2f4`); `main` merged in before merge (`84f7033`).
  - **Decisions** (ADR register, [`docs/decisions/`](docs/decisions/README.md)):
    - `ADR-0001` — adopt an ADR register; `docs/architecture/decisions.md` frozen.
    - `ADR-0002` — product scope: multi-bus, listen-only capture box plus one desktop application;
      the PySide6 monitor stays shipped until replaced.
    - `ADR-0003` — box MCU STM32G474, STM32H723 as fallback.
    - `ADR-0004` — one repository for board, firmware, core and UI.
    - `ADR-0005` — KiCad, ngspice, FreeCAD scripted in Python.
    - `ADR-0006` — Electron + React over the Python core, pending a throughput spike.
    - `ADR-0007` — AI agent as a read-only MCP server in the Python core.
    - `ADR-0008` — FX2 + PulseView through an isolated logic tap; Analog Discovery 3 later.
- **PROJECT_LOG.md created** (issue #59) — retroactive reconstruction from inception to PR #57.
