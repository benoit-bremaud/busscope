# Project Log

Chronological operational logbook of `can-sniffer`. It complements `git log` and
[`CHANGELOG.md`](CHANGELOG.md): every merged pull request, tag, release, decision and direct
commit to `main` is recorded here with the context git does not capture. Entries from inception to
PR #57 were reconstructed retroactively (2026-10-20) from `git log`, merged pull requests, tags,
releases, `CHANGELOG.md` and the ADR register in [`docs/decisions/`](docs/decisions/README.md),
and checked against GitHub.

SHAs are 7-character. The SHA right after a PR number is that PR's merge (or squash) commit
on `main`; `a048e4a` is the direct root commit; SHAs cited inside an entry's narrative are
ordinary commits from that PR's branch.

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
- **PR #60 merged** (`28bd033`) — `docs(log): create PROJECT_LOG.md` (`docs/59-project-log`,
  closes #59). Retroactive reconstruction from inception to PR #57. One review round: the SHA
  convention was scoped to PR merge commits (`bd8ffa8`). Docstring coverage (79.8 %, floor 90)
  found below the floor on `main` during the local review; tracked in #61.
- **PR #62 merged** (`8d0e32e`) — `docs(log): record PR #60 in the project log`
  (`docs/59-project-log-pr60`). Adds the PR #60 entry above.
- **PR #63 merged** (`11bad35`) — `docs(src): raise docstring coverage to the 90 % floor`
  (`docs/61-docstring-coverage`, closes #61). 34 docstrings added (interrogate 79.8 % → 100 %);
  interrogate pinned with `fail-under = 90` and enforced in the quality workflow. Format drift
  found during the gate tracked in #64. GitHub Project "can-sniffer" created as the kanban.
- **PR #65 merged** (`f6b2c49`) — `docs(log): record PR #63 in the project log`
  (`docs/63-project-log-pr63`). Adds the PR #63 entry above.
- **PR #67 merged** (`f28a51f`) — `refactor: rename the project to busscope`
  (`refactor/53-rename-busscope`, closes #53). Review finding on the README listen-only claim
  fixed in `da00aef`. Post-merge: GitHub repository renamed to `busscope` and the local directory
  moved; the diagnostics repository switched to `BUSSCOPE_SRC` (can-sniffer-diagnostics#1,
  `b482807`). #66 closed as not planned: CP/PP measurement belongs to V-SEA.
- **PR #68 merged** (`ec83491`) — `style(src): fix ruff format drift in source files`
  (`style/64-ruff-format`, closes #64). `ruff format` applied to `src` and `tests` (`54a13fc`);
  `ruff format --check` now enforced in `quality.yml` (`678af61`). Codex review: no findings.
- **PR #70 merged** (`0f61770`) — `feat(ui): context-aware icon toolbar for capture and replay`
  (`feat/69-icon-toolbar`, closes #69). Lucide SVG icons, Qt-free toolbar rules
  (`toolbar.py`), Ctrl+M mode switch; Codex P2 findings fixed in `4465b93`. Follow-ups in #71.

## 2026-10-21

- **PR #76 merged** (`ceb6b9e`) — `feat(ui): protocol catalogue and compact protocol picker`
  (`feat/72-protocol-catalogue`, closes #72). Qt-free `protocol_catalogue.py` (families →
  sub-families → protocols, `carried_by` stacking with invariant checks, JSON export for the
  React UI); `protocol_selector.py` is a compact "Protocol: X ▾" button opening a searchable popup
  tree. CAN 2.0B and Infypower available, the rest planned. UI benchmark and UML under
  `docs/architecture/`. Codex P2 (Infypower must be available) fixed in `7d8e099`. Follow-ups:
  #73 (non-CAN transport settings), #74 (decoders), #75 (protocol hierarchy statistics), #77
  (minimalist contextual UI).
- **PR #79 merged** (`effb5c8`) — `feat(ui): minimalist contextual UI on an inheritable domain tree`
  (`feat/77-minimal-contextual-ui`, closes #77). The protocol catalogue became a recursive tree
  whose nodes inherit Feature sets; the capture tab now uses progressive disclosure (protocol
  first, then source, then only the controls the resolved features grant), with the listen-only
  badge always visible. Gotcha: a CAN protocol filed outside fieldbus/can (e.g. CHAdeMO under EV
  charging) must grant the CAN features itself (`cbc1311`).
- **PR #85 merged** (`5d98f39`) — `fix(ui): wrap status messages and name the slcan acceptance
  checkbox` (`fix/84-wrap-status-message`, closes #84). Long status messages wrap instead of
  widening the window. Codex P1 fixed in `e2319a0`: never recommend `slcand -l` for a live bus —
  only verified native SocketCAN interfaces are suggested for live capture.
- **PR #98 in review** — `feat(ai): multi-provider AI diagnosis assistant` (`feat/83-ai-assistant`,
  closes #83). New "AI assistant" tab: Anthropic (default `claude-opus-5-5`), OpenAI, Mistral,
  Google and local OpenAI-compatible models through stdlib HTTP adapters behind a Qt-free
  `LlmProvider` port; API key only in the OS keyring (`busscope-ai`); every send is previewed
  (redacted: pseudonymised addresses, relative time, payloads masked unless actually decoded) and
  confirmed. TLS required off-PC, no redirects, proxies bypassed for loopback. Two Opus critical
  reviews (7 + 8 fixes, `841939c`, `2939ede`); Codex P1/P2 fixed after them (malformed payloads
  stay masked, the whole loaded replay is exposed to the assistant, replies in flight are dropped
  on any provider/model/endpoint change). Gate: 383 tests, 99 % coverage, SonarQube PASSED. Note:
  the non-Anthropic wire formats come from public docs (Context7 quota was exhausted).
