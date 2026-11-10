# ADR-0010: Local-first CI — every check runs on the laptop, no GitHub workflow

**Status:** Accepted — 2026-11-10

## Context

Five GitHub workflows ran on every push and pull request: Python quality (pytest with the
coverage floor, Ruff, mypy, Interrogate), Gitleaks, CodeQL, Dependency review and OpenSSF
Scorecard. GitHub Actions minutes now bill the owner, and the owner rule of 2026-11-07 (every
repository) states that every check runs locally and that the only workflow allowed is a
production deploy triggered by a signed release tag. This repository has no production deploy: a
release is a signed tag and a GitHub release built by hand (CONTRIBUTING.md). The pre-merge gate
already ran locally (SonarQube Community Build, issue #100); the workflows duplicated it on a
budget the project no longer has. Tracked by benoit-bremaud/agents-skills#259.

## Options and scoring

| # | Criterion | Weight | **A. Zero workflow, four local tiers** | B. Keep the GitHub-only jobs (CodeQL, Scorecard) | C. Keep every workflow, add the local tiers |
|---|---|---|---|---|---|
| 1 | Owner rule 2026-11-07 (no Actions minutes) | 35 | 5 | 2 (still bills on every push) | 0 |
| 2 | Fidelity of the checks (same tool, config, floor) | 25 | 4 (Semgrep CE and pip-audit replace CodeQL and Dependency review) | 5 | 5 |
| 3 | Determinism and reproducibility (pinned toolchain, attested SHA) | 20 | 5 | 4 | 3 (two sources of truth) |
| 4 | Simplicity (one place to read and fix) | 20 | 5 | 3 | 1 |
| | **Total / 500** | **100** | **475** | 335 | 205 |

Sensitivity: with fidelity at 40 and the owner rule at 20, A still leads (A 460, B 380).

Dependency scan, a sub-choice:

| # | Criterion | Weight | **pip-audit on `.venv-test`** | osv-scanner | No scan |
|---|---|---|---|---|---|
| 1 | Fidelity (what is actually installed) | 35 | 5 | 2 (no lockfile: it would read the `pyproject.toml` ranges only) | 0 |
| 2 | Simplicity (one `dev` extra, one recipe line) | 30 | 4 | 3 | 5 |
| 3 | Pinning (version under our control) | 20 | 4 (range in `pyproject.toml`) | 5 (mise) | 5 |
| 4 | Cost (runtime, network) | 15 | 3 (PyPI advisory fetch) | 4 | 5 |
| | **Total / 500** | **100** | **430** | 320 | 360 |

## Decision

- **A.** `.github/workflows/` is deleted entirely. The checks move to four `just` tiers (skill
  `local-ci`): `fast` on pre-commit (staged secrets, Ruff on the staged files; the commit-msg
  hook checks the subject separately: types `feat fix docs chore refactor test ci build perf`,
  100 characters at most), `check` on pre-push (Ruff lint and format, strict mypy, Interrogate ≥ 90 %, pytest
  with coverage ≥ 90 %, the wiring and attestation tests, Semgrep Community Edition `p/python`,
  pip-audit, gitleaks on the whole history), `gate` before every merge on the pushed head
  (`check`, then pytest with `coverage.xml` and `sonar-scanner` waiting for the quality gate,
  then the signed attestation), `nightly` on a systemd user timer (`check`, TruffleHog, toolchain
  drift).
- The toolchain is pinned in `mise.toml` and `mise.lock` (Python 3.12 as the removed workflow,
  just, lefthook, gitleaks, trufflehog, jq, Semgrep); the Python checkers stay in the `dev` extra of
  `pyproject.toml` and run from `.venv-test`. `just setup` installs everything once per clone.
- `main` is merged only through `just merge <pr>`, which verifies the `gate` attestation
  (agents-skills ADR-0003: a signed git note on `refs/notes/gate` checked against
  `.github/allowed_signers` of `origin/main`, plus the `gate` commit status). Branch protection on
  `main` requires that status only. The merge is a squash: one `main` commit per pull request,
  which carries no attestation of its own, so `just gate` runs again on `main` after the merge.
- Bootstrap: the first merge of this change happens before `.github/allowed_signers` and
  `scripts/attest.sh` exist on `main`, so its attestation cannot be verified against `main`;
  that one merge goes through `gh pr merge --squash` with a recorded waiver (PROJECT_LOG.md).
  Every later merge uses `just merge`.
- `scripts/{attest,test-attest,check-commit-msg,check-cassettes}.sh` are verbatim copies of
  `~/.claude/scripts` (skill `local-ci` § Apply, step 1), kept byte-identical so a fix lands in one
  place and is re-copied; `check-cassettes.sh` has no caller here yet (no `record` recipe: the
  project calls no third-party API) and stays with the set rather than diverging from it.
- Dropped without replacement: OpenSSF Scorecard (it needs GitHub) and CodeQL itself (skill
  `local-ci` rule 4: free open-source tools only, and the CodeQL CLI terms limit it to GitHub
  use; Semgrep CE covers SAST). The Semgrep `p/python` ruleset is fetched from the registry on
  each run: the rules can change without a commit here, and `security` needs the network.
  Accepted over vendoring the rules (which would freeze known-bad gaps and need its own
  update chore).
- **Fallback: B** if a check proves impossible to run locally for a class of contributors.

## Consequences

- No Actions minute is spent; a push with a red `check` is refused by the pre-push hook, and a
  merge without a green `gate` on the exact head SHA is refused by `just merge`.
- The hooks must be installed (`just setup`) in every clone; a clone without them can push red
  code, which `gate` then refuses to attest.
- The `pipx:semgrep` entry is pinned by version only: its Python dependencies are resolved at
  install time (mise cannot lock them without uv ≥ 0.12.10), an accepted gap.
- `pip-audit` audits what is installed in `.venv-test`, dev tools included; its first run found
  pytest 8.4.2 (PYSEC-2026-1845), fixed by moving the range to pytest 9.
- System prerequisites outside mise: `uv` (the `pipx` backend of mise installs Semgrep through
  it), `sonar-scanner`, and the Qt runtime (`libegl1`) for the widget tests under
  `QT_QPA_PLATFORM=offscreen`. CONTRIBUTING.md lists them.
- The release checklist of CONTRIBUTING.md no longer waits for GitHub checks: the green `gate`
  attestation on the `main` commit replaces them.
