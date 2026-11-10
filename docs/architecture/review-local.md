# Local review — busscope (local CI, #108)

- Date: 2026-11-10
- Commit: the head after round 3 (round 1 on c99865f, round 2 on 1f753fa, round 3 on 5415555)
- Scope: branch diff `origin/main...ci/108-local-ci-no-workflows` (`--push` mode)
- Checks run: adversarial (Opus, 4 rounds) · design · docs · tests · security · correctness
- Verdict: ship as-is · Must 0 · Should 3 (all applied) · Nice 6

## Adversarial review (#236)
- Round 1 on `c99865f`: Must 3 · Should 9 · Nice 5 · unverified 0 · Push gate: closed
- Round 2 on `1f753fa`: 17 fixed · 1 not fixed (N4, the PR number: the PR is opened after this
  report, on the next free number) · 0 regressed · new Must 0 · new Should 1 (sub-choice totals
  420/320/325, applied in `7213e9f`) · Push gate: open
- Round 3 on `5415555` (lefthook fix, a finding of the author: the first push of the branch went
  out with the pre-push job skipped, "no matching push files"): 4 fixed · 2 accepted follow-ups ·
  new Must 0 · new Should 2 (a real-push test, the report refresh: applied in the final commit) ·
  Push gate: open. The real-push cases (first push, empty commit, tag, deletion, dirty tree)
  fail on the c99865f config at the tag push and pass on the fixed one; the first-push skip seen
  on the real `ci/108` push was not reproduced in the scratch repository.
- Round 4 on `8541ba8`: 3 fixed · new Must 0 · new Should 0 · Nice 2 (wording, applied) ·
  **Push gate: open**
- Optional second review (owner's OpenAI account): ChatGPT/Codex not run (never a gate step)

## Pre-merge gate (head: the final commit of the branch)
| Step | Result |
|---|---|
| 0 CI mirror | n/a: no workflow is left (`.github/workflows/` deleted, ADR-0010) |
| 1 Tests | ✅ 433 pytest · ✅ test-local-ci 132 cases · ✅ test-attest 31 cases |
| 2 Coverage | tests 98.95 % lines (floor 90) · docs 96.1 % (Interrogate, floor 90) |
| 3 SonarQube | ⏸ deferred to the pre-merge run (`just gate` on the pushed head) |
| 4 Secrets | ✅ gitleaks clean (whole history) · no tracked .env · diff read: nothing sensitive (`allowed_signers` holds a public key only) |
| 5 E2E/smoke | n/a: desktop application, no E2E suite; widget tests run under `QT_QPA_PLATFORM=offscreen` |
- Gate: `--push`: **pre-push green** — `mise x -- just check` passed, SonarQube deferred to `just gate`

## 🔴 Must Have
_None._ (Round 1: branch protection absent while documented → applied via the API, `gate` status
required, strict; nightly drift check could never fail → `mise outdated --bump --json` with a
shape check, 7 cases; "Angular" commit wording vs the enforced type list → documented in
AGENTS.md, CONTRIBUTING.md, ADR-0010. All fixed in `1f753fa`.)

## 🟡 Should Have
- `docs/decisions/ADR-0010-local-first-ci.md:36` `[adversarial][docs]` · sub-choice totals were
  430/320/360 for scores summing to 420/320/325 · fixed in `7213e9f`.
- `lefthook.yml:24` `[correctness]` · lefthook skips a pre-push job when the push lists no file
  (proven red on a tag push): `files: echo justfile` + `: {files};` keep the tier on every
  push · fixed in `5415555`, proven by real pushes in `test-local-ci.sh` (round 3 Should).
- Round 1 Should (all fixed in `1f753fa`): bootstrap merge recorded; main-matrix totals
  475/335/205; squash + re-gate on `main` recorded; `LEFTHOOK=0` on the attestation push; CodeQL
  reason = skill rule 4; Semgrep registry trade-off; `jq` comment; `uv`, `libegl1`,
  `sonar-scanner`, mise prerequisites; systemd nightly units installed; test-local-ci rewritten
  (PR head fetched from origin, base fetch proven, every tripwire path, `GATE_CI_CHANGE` values,
  token file, `SONAR_HOST_URL`, pytest failure, nightly drift, log assertions on every case).

## 🔵 Nice to Have
- `justfile:149` `[adversarial]` · skipping the `python` row hides 3.12 patch releases · follow-up:
  a 3.12.x check in nightly or a dated reminder.
- `~/.config/systemd/user/busscope-nightly.service` `[adversarial]` · the nightly runs on the
  checked-out branch, not `main` · follow-up: a clean `main` worktree for the timer.
- Branch protection has `enforce_admins: false`: the owner can bypass from the web UI; only the
  `gh-merge-gate.sh` hook stops agents · intentional (bootstrap and emergency path).
- `CONTRIBUTING.md:15`, `AGENTS.md:20` `[docs]` · "Do not merge without explicit user approval"
  predates the 2026-11-07 rule (green gate merges without asking) · follow-up issue.
- `scripts/check-cassettes.sh` has no caller · kept verbatim with the set (ADR-0010).

## ⚪ Disagree / Intentional
- `justfile:149` · the Python minor stays 3.12 on purpose (bumped by hand with `requires-python`,
  `sonar.python.version=3.12`).

## Per-dimension summary
- Adversarial: 3 Must + 9 Should in round 1, all fixed, gate open in round 2 · Design: four
  tiers, one recipe each, no abstraction beyond the skill template · Docs: ADR-0010, CONTRIBUTING,
  README, AGENTS consistent on types, prerequisites and the merge path · Tests: 132 wiring cases
  with stubbed boundaries and real pushes, every refusal asserted on the log · Security: no secret, token never on
  the command line, offline TruffleHog · Correctness: `just check` green on every commit of the
  branch since round 1.
