#!/bin/sh
# Tests for the local CI wiring (#108, skill local-ci rule 7, ADR-0010): the four tiers exist and
# compose (check = lint + test + security + secrets; nightly ⊇ check; the venv guard fronts every
# Python recipe), no GitHub workflow is left, the Python pin of mise.toml is what the venv guard
# reads, lefthook.yml is valid and wires the commit-msg and pre-push hooks, the commit-msg check
# accepts and refuses the right subjects; then, in a throwaway repository with stubbed boundaries
# (just steps, attest.sh, gh, sonar-scanner, curl, mise, the checkers): gate refuses a dirty tree, a
# HEAD behind the base (after fetching it), an unpushed HEAD or a branch changing any local CI file,
# runs check → sonar → attestation in that order, stops at the first failing step and attests
# nothing when a step fails or HEAD moved; merge refuses a non-numeric PR and a head without
# attestation, fetches the PR head from origin, merges with --squash --match-head-commit through the
# verifier of origin/main and propagates a gh failure; sonar refuses a missing scanner, token or
# server, failed tests and a failed quality gate, reads the token file; venv-guard refuses a missing
# or wrong-version venv; nightly fails on a stale pin, a changed JSON shape or TruffleHog, and
# ignores the Python line and other configs; L0 (`just fast`) passes a clean staged change but
# refuses a staged secret and a ruff error.
# Needs mise, just, lefthook, gitleaks and the project's .venv-test (`just setup`):
#   mise x -- sh scripts/test-local-ci.sh
set -e
# A hook (pre-push runs `just check`) exports these; they would aim git at the outer repository.
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_PREFIX GIT_OBJECT_DIRECTORY GIT_COMMON_DIR
# The gate of a branch that changes the local CI runs with GATE_CI_CHANGE=1; the guard cases
# below must not inherit it, nor the knobs of the stubs or a real SonarQube configuration.
unset GATE_CI_CHANGE SONAR_TOKEN SONAR_HOST_URL FAIL_STEP ATTEST_FAIL GH_FAIL SCANNER_FAIL SONAR_DOWN MOVE_HEAD VENV_PY PYTEST_FAIL MISE_JSON TRUFFLEHOG_FAIL
# The throwaway repositories must not inherit the machine's signing, hooks or URL rewrites.
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null

root=$(cd "$(dirname "$0")/.." && pwd)
work=$(mktemp -d)
# The L0 hooks run `mise x --` in the throwaway repo, which records a trust entry for its path: drop it.
trap 'rm -f "${MISE_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/mise}"/trusted-configs/*"$(basename "$work")"*; rm -rf "$work"' EXIT
n=0
fail() { echo "FAIL $1"; exit 1; }
ok() { n=$((n + 1)); }

# `mise x --` puts the tools on PATH but not mise itself (hooks and the throwaway repo need it).
command -v mise > /dev/null || { [ -x "$HOME/.local/bin/mise" ] && PATH="$HOME/.local/bin:$PATH" && export PATH || true; }
for bin in mise just lefthook gitleaks; do
  command -v "$bin" > /dev/null || fail "$bin not on PATH"
done
[ -x "$root/.venv-test/bin/ruff" ] || fail ".venv-test missing: run just setup"

# Tiers and their composition.
cd "$root"
for r in fast check gate nightly setup merge sonar; do
  just --show "$r" > /dev/null 2>&1 || fail "recipe $r missing"; ok
done
deps() { just --show "$1" | grep -E "^$1( |:)" | sed 's/.*: *//'; } # deps <recipe>
[ "$(deps check)" = "lint test security secrets" ] || fail "check must be exactly lint test security secrets"; ok
deps nightly | grep -qw check || fail "nightly does not depend on check"; ok
for r in lint test security sonar; do
  deps "$r" | grep -qw venv-guard || fail "$r does not run venv-guard first"; ok
done
just --show test | grep -q 'scripts/test-attest.sh' || fail "test does not run the attestation tests"; ok
just --show lint | grep -q 'interrogate src' || fail "lint does not measure the docstring coverage"; ok
[ -z "$(find .github -path '*/workflows/*' -name '*.y*ml' 2>/dev/null)" ] || fail "a GitHub workflow is left (ADR-0010: none)"; ok
grep -qE '^python = "3\.[0-9]+\.[0-9]+"' mise.toml || fail "mise.toml does not pin an exact Python"; ok
grep -qE '^ +run: sh scripts/check-commit-msg.sh \{1\}' lefthook.yml || fail "commit-msg hook does not run check-commit-msg.sh on the message file"; ok
grep -qE '^ +mise x -- just check$' lefthook.yml || fail "pre-push hook does not run just check"; ok
grep -qF 'git status --porcelain' lefthook.yml || fail "pre-push hook does not refuse a dirty tree"; ok
grep -qE '^ +files: echo ' lefthook.yml || fail "pre-push hook is skipped on a first push (no push files) without a constant files list"; ok
lefthook validate > /dev/null || fail "lefthook validate"; ok

# commit-msg subjects.
msg() { # msg <expected-exit> <subject>
  printf '%s\n' "$2" > "$work/msg"
  rc=0; sh scripts/check-commit-msg.sh "$work/msg" > /dev/null 2>&1 || rc=$?
  [ "$rc" -eq "$1" ] || fail "commit-msg '$2': exit $rc, expected $1"; ok
}
msg 0 'ci(workflows): move every check to local CI'
msg 0 'feat: no scope'
msg 0 'feat(ui)!: the capture tab drops the legacy toolbar'
msg 0 'Merge branch main into feat/1'
msg 0 'fixup! feat: x'
msg 0 'Revert "feat: x"'
msg 1 'Wire just'
msg 1 'ci(repo): ends with a period.'
msg 1 'wip(repo): not a listed type'
msg 1 'feat(Game): uppercase scope'
msg 0 "feat(ui): $(printf 'x%.0s' $(seq 90))" # exactly 100 characters
msg 1 "feat(ui): $(printf 'x%.0s' $(seq 91))" # 101
msg 1 ''

# Recipes with their boundaries stubbed, in a throwaway repository with a bare origin. The real
# `just` runs the recipe; a stub `just` first on PATH records the steps the recipe delegates to
# (check, sonar) and fails the one named in FAIL_STEP; stub attest.sh, gh, sonar-scanner, curl,
# mise, the checkers and a fake .venv-test log their arguments to $LOG. Every refusal must leave
# no "attest write" / "gh pr merge" / "sonar-scanner" line.
real_just=$(command -v just)
box="$work/box"; mkdir -p "$box/origin" "$box/stub" "$box/home"
git -C "$box/origin" init -q --bare -b main
git clone -q "$box/origin" "$box/repo" 2> /dev/null; cd "$box/repo"
git config user.email t@example.com && git config user.name t
cp "$root/justfile" "$root/mise.toml" "$root/mise.lock" . && mkdir -p scripts src .venv-test/bin
printf '[project]\nname = "x"\nversion = "0.0.0"\n' > pyproject.toml
want=$(sed -n 's/^python = "\([0-9.]*\)".*/\1/p' mise.toml)
cat > .venv-test/bin/python <<EOF2
#!/bin/sh
echo "\${VENV_PY:-$want}"
EOF2
cat > .venv-test/bin/pytest <<'EOF2'
#!/bin/sh
echo "pytest $*" >> "$LOG"; [ "${PYTEST_FAIL:-0}" = 0 ]
EOF2
for b in ruff mypy interrogate pip-audit; do printf '#!/bin/sh\necho "%s $*" >> "$LOG"\n' "$b" > ".venv-test/bin/$b"; done
for b in semgrep gitleaks lefthook; do printf '#!/bin/sh\necho "%s $*" >> "$LOG"\n' "$b" > "$box/stub/$b"; done
for b in test-local-ci test-attest; do printf '#!/bin/sh\necho "%s $*" >> "$LOG"\n' "$b" > "scripts/$b.sh"; done
cat > scripts/attest.sh <<'EOF2'
#!/bin/sh
echo "attest $*" >> "$LOG"; [ "${ATTEST_FAIL:-0}" = 0 ]
EOF2
cat > "$box/stub/just" <<'EOF2'
#!/bin/sh
echo "just $*" >> "$LOG"
[ "${FAIL_STEP:-}" != "$1" ] || exit 1
[ "$1" != sonar ] || [ -z "${MOVE_HEAD:-}" ] || git commit -q --allow-empty -m 'chore: moved' --no-verify
EOF2
cat > "$box/stub/gh" <<'EOF2'
#!/bin/sh
echo "gh $*" >> "$LOG"; [ "${GH_FAIL:-}" != "$2" ] || exit 1
case "$*" in "pr view"*) echo "$PR_HEAD" ;; esac # the PR head: a commit that exists on origin only
EOF2
cat > "$box/stub/sonar-scanner" <<'EOF2'
#!/bin/sh
echo "sonar-scanner $* token=${SONAR_TOKEN:-none}" >> "$LOG"; echo "sonar-scanner $*"; [ "${SCANNER_FAIL:-0}" = 0 ]
EOF2
cat > "$box/stub/curl" <<'EOF2'
#!/bin/sh
echo "curl $*" >> "$LOG"; [ "${SONAR_DOWN:-0}" = 0 ] && echo '{"status":"UP"}'
EOF2
cat > "$box/stub/trufflehog" <<'EOF2'
#!/bin/sh
echo "trufflehog $*" >> "$LOG"; [ "${TRUFFLEHOG_FAIL:-0}" = 0 ]
EOF2
cat > "$box/stub/mise" <<'EOF2'
#!/bin/sh
echo "mise $*" >> "$LOG"; printf '%s' "$MISE_JSON"
EOF2
chmod +x scripts/attest.sh .venv-test/bin/* "$box/stub"/*
export MISE_TRUSTED_CONFIG_PATHS="$box/repo" LOG="$work/log"
git add -A && git commit -qm 'chore: init' --no-verify && git push -q origin main 2> /dev/null
box_run() { # box_run <expected-exit> <label> <text the output or log must hold> -- <env>… <just args>
  want=$1 label=$2 text=$3; shift 4
  : > "$LOG"; rc=0; env PATH="$box/stub:$PATH" "$@" > "$work/out" 2>&1 || rc=$?
  [ "$rc" -eq "$want" ] || { cat "$work/out" "$LOG"; fail "$label: exit $rc, expected $want"; }
  grep -qF -- "$text" "$work/out" "$LOG" || { cat "$work/out" "$LOG"; fail "$label: output lacks '$text'"; }
  ok
}
expect() { grep -q "$1" "$LOG" || { cat "$LOG"; fail "$2"; }; ok; }    # expect <log regex> <failure>
no_line() { ! grep -q "$1" "$LOG" || { cat "$LOG"; fail "$2"; }; ok; } # no_line <log regex> <failure>
steps() { [ "$(tr '\n' ' ' < "$LOG")" = "$1 " ] || { cat "$LOG"; fail "$2: $(tr '\n' ' ' < "$LOG")"; }; ok; } # steps <exact log> <failure>

# gate: refusals first, then the order of the steps, then the late refusals.
echo dirty > src/d && box_run 1 "gate: dirty tree refused" "commit or set aside" -- "$real_just" gate main
no_line '^just check' "gate ran check on a dirty tree"; rm src/d
git commit -q --allow-empty -m 'chore: unpushed' --no-verify
box_run 1 "gate: unpushed HEAD refused" "push HEAD first" -- "$real_just" gate main
no_line '^just check' "gate ran check on an unpushed HEAD"
git push -q origin main 2> /dev/null
head=$(git rev-parse HEAD)
box_run 0 "gate: green path" "attest write gate $head" -- "$real_just" gate main
steps "just check just sonar attest write gate $head" "gate steps or order"
box_run 1 "gate: failing sonar stops it" "" -- env FAIL_STEP=sonar "$real_just" gate main
steps "just check just sonar" "gate went past a failed sonar"
box_run 1 "gate: failing check stops it" "" -- env FAIL_STEP=check "$real_just" gate main
steps "just check" "gate went past a failed check"
box_run 1 "gate: failed attestation propagates" "" -- env ATTEST_FAIL=1 "$real_just" gate main
expect "^attest write gate $head\$" "gate did not reach the attestation"
box_run 0 "gate: default base" "attest write gate $head" -- "$real_just" gate
# Every tripwire path, and the flag accepts exactly 1.
for p in justfile lefthook.yml mise.toml mise.lock scripts/new.sh .github/allowed_signers pyproject.toml sonar-project.properties .gitleaks.toml .gitleaksignore .semgrepignore; do
  mkdir -p "$(dirname "$p")" && echo "# $p" >> "$p" && git add "$p" && git commit -qm "ci(repo): touch $p" --no-verify && git push -q -f origin HEAD:ci 2> /dev/null
  box_run 1 "gate: a branch changing $p refused" "changes the local CI itself ($p)" -- "$real_just" gate origin/main
  no_line '^just check' "gate ran check on a branch changing $p"
  git reset -q --hard origin/main
done
echo '# x' >> justfile && git commit -qam 'ci(repo): ci change' --no-verify && git push -q -f origin HEAD:ci 2> /dev/null
for v in 0 true yes; do
  box_run 1 "gate: GATE_CI_CHANGE=$v still refused" "changes the local CI itself" -- env GATE_CI_CHANGE=$v "$real_just" gate origin/main
done
box_run 0 "gate: the same branch gated after reading" "attest write gate $(git rev-parse HEAD)" -- env GATE_CI_CHANGE=1 "$real_just" gate origin/main
git reset -q --hard origin/main
box_run 1 "gate: HEAD moved during the run" "HEAD moved" -- env MOVE_HEAD=1 "$real_just" gate main
no_line '^attest' "gate attested a HEAD that moved"
git reset -q --hard origin/main
# The base is fetched first: a main moved on origin by another clone is seen without a pull.
git clone -q "$box/origin" "$box/other" 2> /dev/null && git -C "$box/other" config user.email o@example.com && git -C "$box/other" config user.name o
git -C "$box/other" commit -q --allow-empty -m 'chore: elsewhere' --no-verify && git -C "$box/other" push -q origin main 2> /dev/null
box_run 1 "gate: HEAD behind a base moved on origin refused" "behind origin/main" -- "$real_just" gate origin/main
no_line '^just check' "gate ran check on a HEAD behind the base"
git pull -q --ff-only origin main 2> /dev/null
box_run 0 "gate: green again once up to date" "attest write gate $(git rev-parse HEAD)" -- "$real_just" gate origin/main

# merge: argument shape, the attestation, the PR head fetched from origin, the exact gh command.
git -C "$box/other" commit -q --allow-empty -m 'feat: pr head' --no-verify && git -C "$box/other" push -q origin HEAD:refs/heads/pr 2> /dev/null
export PR_HEAD; PR_HEAD=$(git -C "$box/other" rev-parse HEAD)
[ -n "$PR_HEAD" ] || fail "no PR head"
git cat-file -e "$PR_HEAD" 2> /dev/null && fail "the PR head must not be in the checkout before merge fetches it"; ok
box_run 1 "merge: non-numeric PR refused" "usage just merge" -- "$real_just" merge --help
no_line '^gh' "merge called gh on a bad argument"
box_run 1 "merge: unattested head refused" "" -- env ATTEST_FAIL=1 "$real_just" merge 7
expect "^attest verify gate $PR_HEAD\$" "merge did not verify the head SHA"
no_line 'gh pr merge' "merge merged an unattested head"
box_run 0 "merge: attested head merged" "gh pr merge 7 --squash --match-head-commit $PR_HEAD" -- "$real_just" merge 7
steps "gh pr view 7 --json headRefOid -q .headRefOid attest verify gate $PR_HEAD gh pr merge 7 --squash --match-head-commit $PR_HEAD" "merge steps or order"
git cat-file -e "$PR_HEAD" || fail "merge did not fetch the PR head from origin"; ok
printf '#!/bin/sh\nexit 1\n' > scripts/attest.sh
box_run 0 "merge: verifier of origin/main, not the checkout's" "gh pr merge 7" -- "$real_just" merge 7
git checkout -q scripts/attest.sh
box_run 1 "merge: gh pr view failure propagates" "" -- env GH_FAIL=view "$real_just" merge 7
steps "gh pr view 7 --json headRefOid -q .headRefOid" "merge went on after gh pr view failed"
box_run 1 "merge: gh pr merge failure propagates" "" -- env GH_FAIL=merge "$real_just" merge 7
expect '^gh pr merge' "merge did not reach gh pr merge"

# sonar: the guards, then the call with the token in the environment and the gate wait.
mkdir "$box/bare" && for b in sh git sed cat grep; do ln -s "$(command -v "$b")" "$box/bare/$b"; done
box_run 1 "sonar: no scanner" "not on PATH" -- env PATH="$box/bare" HOME="$box/home" "$real_just" sonar
box_run 1 "sonar: no token" "no token" -- env HOME="$box/home" "$real_just" sonar
no_line sonar-scanner "sonar ran the scanner without a token"
box_run 1 "sonar: server down" "not UP" -- env HOME="$box/home" SONAR_TOKEN=t0k SONAR_DOWN=1 "$real_just" sonar
no_line sonar-scanner "sonar ran the scanner against a server that is down"
box_run 1 "sonar: failing tests stop it" "" -- env HOME="$box/home" SONAR_TOKEN=t0k PYTEST_FAIL=1 "$real_just" sonar
no_line sonar-scanner "sonar ran the scanner after failing tests"
box_run 0 "sonar: fresh coverage, then the scan with the gate wait" "sonar-scanner -Dsonar.host.url=http://localhost:9000 -Dsonar.projectVersion=0.0.0 -Dsonar.qualitygate.wait=true token=t0k" -- env HOME="$box/home" SONAR_TOKEN=t0k "$real_just" sonar
expect '^pytest .*--cov-report=xml:coverage.xml' "sonar did not refresh coverage.xml before the scan"
grep -q 't0k' "$work/out" && fail "sonar passed the token on the command line"; ok
box_run 0 "sonar: SONAR_HOST_URL honoured" "curl -sf -m 5 http://sq.test:9999/api/system/status" -- env HOME="$box/home" SONAR_TOKEN=t0k SONAR_HOST_URL=http://sq.test:9999 "$real_just" sonar
expect 'sonar-scanner -Dsonar.host.url=http://sq.test:9999 ' "sonar did not pass SONAR_HOST_URL to the scanner"
mkdir -p "$box/home/.config/sonar-tokens" && printf 'f1l3tok\n' > "$box/home/.config/sonar-tokens/busscope"
box_run 0 "sonar: token file read when SONAR_TOKEN is unset" "token=f1l3tok" -- env HOME="$box/home" "$real_just" sonar
box_run 1 "sonar: failed quality gate fails the recipe" "" -- env HOME="$box/home" SONAR_TOKEN=t0k SCANNER_FAIL=1 "$real_just" sonar
expect '^sonar-scanner' "sonar did not reach the scanner"

# venv-guard: a wrong Python or a missing venv is refused before any step runs.
box_run 1 "venv-guard: wrong Python refused" "pinned in mise.toml" -- env VENV_PY=3.1.0 "$real_just" lint
no_line '^ruff' "lint ran ruff on the wrong Python"
mv .venv-test "$box/venv-aside"
box_run 1 "venv-guard: missing venv refused" "run just setup" -- "$real_just" lint
mv "$box/venv-aside" .venv-test

# nightly: check first, TruffleHog offline, then the drift read from the JSON of this mise.toml.
here="$box/repo/mise.toml"
row() { printf '"%s":{"current":"%s","latest":"%s","source":{"path":"%s"}}' "$1" "$2" "$3" "$4"; } # row <tool> <current> <latest> <path>
box_run 0 "nightly: up to date" "toolchain up to date" -- env MISE_JSON='{}' "$real_just" nightly
expect '^trufflehog git file://.* --no-verification --fail --no-update$' "nightly did not run TruffleHog offline"
expect '^mise outdated --bump --json$' "nightly did not read mise outdated"
grep -q '^ruff check' "$LOG" && grep -q '^semgrep' "$LOG" && grep -q '^gitleaks git' "$LOG" || { cat "$LOG"; fail "nightly did not run check first"; }; ok
box_run 1 "nightly: stale pin refused" "just 1.0.0 -> 2.0.0" -- env MISE_JSON="{$(row just 1.0.0 2.0.0 "$here")}" "$real_just" nightly
box_run 0 "nightly: the Python line is ignored" "toolchain up to date" -- env MISE_JSON="{$(row python 3.12.0 3.14.0 "$here")}" "$real_just" nightly
box_run 0 "nightly: another config's row is ignored" "toolchain up to date" -- env MISE_JSON="{$(row just 1.0.0 2.0.0 "$box/home/mise.toml")}" "$real_just" nightly
box_run 1 "nightly: a changed JSON shape refused" "changed shape" -- env MISE_JSON='[]' "$real_just" nightly
box_run 1 "nightly: a row without source refused" "changed shape" -- env MISE_JSON='{"just":{"current":"1","latest":"2"}}' "$real_just" nightly
box_run 1 "nightly: TruffleHog finding fails it" "" -- env TRUFFLEHOG_FAIL=1 MISE_JSON='{}' "$real_just" nightly
no_line '^mise' "nightly read the drift after a TruffleHog failure"
unset MISE_TRUSTED_CONFIG_PATHS LOG PR_HEAD

# L0 in a throwaway repository holding this repository's hook config, scripts and real venv.
repo="$work/repo"
mkdir -p "$repo" && cd "$repo"
git init -q -b main && git config user.email t@example.com && git config user.name t
cp -R "$root/scripts" "$root/lefthook.yml" "$root/justfile" "$root/mise.toml" "$root/mise.lock" "$root/pyproject.toml" .
ln -s "$root/.venv-test" .venv-test
export MISE_TRUSTED_CONFIG_PATHS="$repo" # not `mise trust`: it would leave a permanent entry for a deleted /tmp path
git add -A && git commit -qm init --no-verify
mkdir notes

fast() { # fast <expected-exit> <label> [<text the output must hold>]
  rc=0; just fast > "$work/out" 2>&1 || rc=$?
  [ "$rc" -eq "$1" ] || { cat "$work/out"; fail "$2: exit $rc, expected $1"; }
  [ -z "${3:-}" ] || grep -qF "$3" "$work/out" || { cat "$work/out"; fail "$2: output lacks '$3'"; }
  ok
}

echo 'Plain notes.' > notes/a.txt && git add notes/a.txt
fast 0 "clean staged change"

key="AKIA$(printf seed | sha256sum | cut -c1-16 | tr 'a-f0-9' 'A-FG-P')"
printf 'token %s\n' "$key" > notes/leak.txt && git add notes/leak.txt
fast 1 "staged secret refused" "leaks found"
git rm -q --cached notes/leak.txt

printf 'import os\n' > notes/bad.py && git add notes/bad.py
fast 1 "staged ruff error refused" "F401"

echo "test-local-ci: $n cases passed"
