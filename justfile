# Local CI (#108, skill local-ci, ADR-0010): four tiers, one recipe each, no GitHub and no AI agent
# needed. GitHub Actions runs nothing: there is no production deploy, a release is a signed tag
# (CONTRIBUTING.md). Tools come from mise.toml (`just setup`); run through `mise x -- just <tier>`
# when the shell does not activate mise (the git hooks do). The Python checks run from `.venv-test`,
# the isolated environment the removed quality workflow used, with the configuration of pyproject.toml.
#
#   L0 fast     pre-commit hook                        staged files only                       < 10 s
#   L1 check    pre-push hook, review-local --push     lint + test + security + secrets        < 3 min
#   L2 gate     review-local § 2b, on the pushed head  check + SonarQube, then the attestation  5–15 min
#               before every merge
#   L3 nightly  systemd user timer                     check + TruffleHog + mise outdated
#
# Then: `just merge <pr>` (refuses without the gate attestation on the head SHA).

set shell := ["sh", "-eu", "-c"]

# The Qt widgets under test need no display (same as the removed workflow)
export QT_QPA_PLATFORM := "offscreen"

venv := ".venv-test/bin"

# L1 by default
default: check

# Once per clone: the pinned toolchain, the isolated test environment and the git hooks
setup:
    mise install
    [ -x {{venv}}/python ] || mise x -- python -m venv .venv-test
    {{venv}}/python -m pip install --quiet --upgrade pip
    {{venv}}/python -m pip install --quiet -e '.[dev]'
    mise x -- lefthook install

# L0 — the pre-commit checks on the staged files (< 10 s)
fast:
    lefthook run pre-commit

# Fail fast when `.venv-test` is missing or on another Python than mise.toml pins
[private]
venv-guard:
    @[ -x {{venv}}/python ] || { echo "no .venv-test: run just setup" >&2; exit 1; }
    @want=$(sed -n 's/^python = "\([0-9.]*\)".*/\1/p' mise.toml); got=$({{venv}}/python -c 'import platform; print(platform.python_version())'); [ "$got" = "$want" ] || { echo "Python $got in .venv-test, $want pinned in mise.toml: remove .venv-test and run just setup" >&2; exit 1; }

# Ruff (lint + format), strict mypy, docstring coverage >= 90 % (pyproject.toml), the hooks config
lint: venv-guard
    {{venv}}/ruff check .
    {{venv}}/ruff format --check .
    {{venv}}/mypy
    {{venv}}/interrogate src
    lefthook validate

# pytest with the coverage floor of pyproject.toml (>= 90 %), the local CI wiring tests
test: venv-guard
    {{venv}}/pytest
    sh scripts/test-local-ci.sh
    sh scripts/test-attest.sh

# SAST (Semgrep Community Edition, the python registry ruleset, replaces CodeQL) on the application
# and its tests, then known vulnerabilities in the installed dependencies, dev ones included
# (pip-audit, replaces Dependency review). EIO_BACKEND=posix: semgrep-core otherwise opens io_uring
# rings charged to RLIMIT_MEMLOCK with every Electron process, and dies intermittently.
# SAST (Semgrep CE on src and tests) + pip-audit on .venv-test (replaces CodeQL and Dependency review)
security: venv-guard
    EIO_BACKEND=posix semgrep scan --config p/python --error --metrics=off --quiet -j 4 src tests
    {{venv}}/pip-audit --progress-spinner off --skip-editable

# Secrets in the whole git history (replaces the gitleaks workflow)
secrets:
    gitleaks git --redact --no-banner .

# L1 — pre-push (< 3 min)
check: lint test security secrets

# L2 — pre-merge, called by review-local § 2b (base: the branch to integrate into), 5–15 min.
# Ends with the gate attestation (agents-skills ADR-0003): commit status `gate` + signed note on
# HEAD, which must already be pushed and up to date with `base`, so it runs on the pushed head only;
# the clean-tree and pushed checks run first, not after 10 minutes in `attest.sh write`.
# L2 — pre-merge on the pushed head: check + SonarQube, then the attestation (5–15 min)
gate base="origin/main":
    #!/bin/sh
    set -eu
    base={{quote(base)}}
    [ -z "$(git status --porcelain)" ] || { echo "gate: commit or set aside local changes first" >&2; exit 1; }
    case "$base" in origin/*) git fetch --quiet origin "${base#origin/}" ;; esac
    git merge-base --is-ancestor "$base" HEAD || { echo "gate: HEAD is behind $base, merge or rebase it first" >&2; exit 1; }
    # The gate runs the branch's own recipes and scripts with the owner's keys and tokens: a branch
    # that changes them is gated only after a human read those files (GATE_CI_CHANGE=1).
    ci=$(git diff --name-only "$base...HEAD" -- justfile lefthook.yml mise.toml mise.lock scripts .github/allowed_signers pyproject.toml sonar-project.properties .gitleaks.toml .gitleaksignore .trufflehog-exclude)
    [ -z "$ci" ] || [ "${GATE_CI_CHANGE:-0}" = 1 ] || { echo "gate: this branch changes the local CI itself ($(printf '%s' "$ci" | tr '\n' ' ')): read those files, then run GATE_CI_CHANGE=1 just gate" >&2; exit 1; }
    [ -n "$(git branch -r --contains HEAD)" ] || { echo "gate: push HEAD first (the attestation is written on the pushed head)" >&2; exit 1; }
    # `check` runs from the body, not as a dependency, so the HEAD it checked is the one attested.
    start=$(git rev-parse HEAD)
    just check
    just sonar
    [ "$(git rev-parse HEAD)" = "$start" ] || { echo "gate: HEAD moved during the gate ($start checked), run it again" >&2; exit 1; }
    sh scripts/attest.sh write gate "$start"

# SonarQube analysis on the local Community Build (sonar-project.properties, CONTRIBUTING.md) with
# the global analysis token from SONAR_TOKEN or ~/.config/sonar-tokens/busscope, waiting for the
# quality gate. The scanner reads coverage.xml, written by pytest here so it is never stale.
# SonarQube analysis with quality-gate wait (step of gate)
sonar: venv-guard
    #!/bin/sh
    set -eu
    command -v sonar-scanner > /dev/null || { echo "sonar: sonar-scanner not on PATH (system tool, skill local-ci rule 2)" >&2; exit 1; }
    SONAR_TOKEN="${SONAR_TOKEN:-$(cat "$HOME/.config/sonar-tokens/busscope" 2>/dev/null || true)}"
    [ -n "$SONAR_TOKEN" ] || { echo "sonar: no token in SONAR_TOKEN or ~/.config/sonar-tokens/busscope" >&2; exit 1; }
    url="${SONAR_HOST_URL:-http://localhost:9000}"
    curl -sf -m 5 "$url/api/system/status" | grep -q '"status":"UP"' || { echo "sonar: SonarQube is not UP at $url, start it first" >&2; exit 1; }
    QT_QPA_PLATFORM=offscreen {{venv}}/pytest --quiet --cov-report=xml:coverage.xml
    version=$(sed -n 's/^version = "\([^"]*\)".*/\1/p' pyproject.toml)
    SONAR_TOKEN="$SONAR_TOKEN" sonar-scanner -Dsonar.host.url="$url" -Dsonar.projectVersion="$version" -Dsonar.qualitygate.wait=true

# Merge a PR only when its exact head SHA carries the gate attestation (agents-skills ADR-0003).
# The verifier is read from origin/main. Squash, as every merge of this repository. Same-repository
# PRs only (the head is fetched from origin).
# Merge a PR whose exact head SHA carries the gate attestation (the only merge path)
merge pr:
    #!/bin/sh
    set -eu
    pr={{quote(pr)}}
    case "$pr" in ''|*[!0-9]*) echo "merge: usage just merge <pr number>" >&2; exit 1 ;; esac
    sha=$(gh pr view "$pr" --json headRefOid -q .headRefOid)
    git fetch --quiet origin main "$sha"
    # The verifier of origin/main, never the checkout's: a branch cannot ship its own.
    verifier=$(mktemp); trap 'rm -f "$verifier"' EXIT
    git show origin/main:scripts/attest.sh > "$verifier"
    sh "$verifier" verify gate "$sha"
    gh pr merge "$pr" --squash --match-head-commit "$sha"

# L3 — nightly, systemd user timer (no time budget): deep secret history (TruffleHog, offline) and
# toolchain drift: `mise outdated` exits 0 whatever it finds, so the rows of this mise.toml (not
# the global config) are read from its JSON and any of them fails the tier.
# L3 — nightly (systemd timer): check + TruffleHog + toolchain drift
nightly: check
    #!/bin/sh
    set -eu
    trufflehog git "file://$PWD" --no-verification --fail --no-update
    stale=$(mise outdated --json | jq -r --arg here "$PWD/mise.toml" 'to_entries[] | select(.value.source.path == $here) | "\(.key) \(.value.current) -> \(.value.latest)"')
    [ -z "$stale" ] || { printf 'nightly: bump mise.toml, then mise install && mise lock:\n%s\n' "$stale" >&2; exit 1; }
    echo "nightly: toolchain up to date"
