# Contributing

## Workflow

1. Start from an Issue with an explicit scope and acceptance criteria.
2. Create a dedicated branch from an up-to-date `main` before editing any project file.
3. Add or update proportional UML documentation before implementing behavior or architecture.
4. Obtain design approval before implementation.
5. Keep changes focused and follow Clean Architecture, SOLID, KISS, DRY, and YAGNI.
6. Use Conventional Commits, `type(scope): description`, with a type among `feat fix docs chore
   refactor test ci build perf` and a subject of 100 characters at most; the commit-msg hook
   refuses anything else.
7. Open a pull request linked to the Issue and address all review comments before merging.
8. Merge only after explicit maintainer approval, then remove the merged branch.

Documentation-only changes do not require new UML when they do not alter behavior or architecture.
CAN transmission requires a dedicated safety design and remains disabled by default.

## Versioned public surface

Semantic Versioning covers the installed `busscope` command, documented application behavior,
the exported CSV format accepted for replay, and documented protocol-decoding results. Internal
Python modules are not a stable library API.

## Release workflow

1. Select the version according to Semantic Versioning and keep the version in `pyproject.toml`
   without a `v` prefix.
2. Prepare the version and matching `CHANGELOG.md` section in a reviewed pull request.
3. Merge the preparation pull request into `main` with `just merge <pr>`, then run `just gate`
   on the new `main` commit so it carries its own attestation (the squash commit is new and
   unattested until then).
4. Create an annotated, signed `vMAJOR.MINOR.PATCH` tag from that exact `main` commit.
5. Push only the release tag and publish a GitHub release using the matching changelog section.

Published versions are immutable: never move, delete, or reuse a release tag. Tag protection is
defined in [`.github/tag-protection.md`](.github/tag-protection.md).

## Validation

Every check runs locally ([ADR-0010](docs/decisions/ADR-0010-local-first-ci.md), skill
`local-ci`); there is no GitHub workflow. Once per clone, install the pinned toolchain of
`mise.toml`, the isolated `.venv-test` environment and the git hooks. Prerequisites outside
mise: [mise](https://mise.jdx.dev) itself, `uv` (mise installs Semgrep through it), `git`, `gh`,
`curl`, the Qt runtime (`libegl1` on Debian/Ubuntu) and, for `just gate`, `sonar-scanner`:

```bash
mise x -- just setup
```

The tiers, each one a `just` recipe (`just --list` describes them):

| Tier | Recipe | When | Holds |
|------|--------|------|-------|
| L0 | `just fast` | pre-commit hook | staged secrets (gitleaks), Ruff on the staged files; the commit-msg hook checks the subject |
| L1 | `just check` | pre-push hook, before a pull request | Ruff lint and format, strict mypy, Interrogate ≥ 90 %, pytest with coverage ≥ 90 %, the wiring and attestation tests, Semgrep CE, pip-audit, gitleaks on the history |
| L2 | `just gate` | on the pushed head, before every merge | `check`, then SonarQube with the quality-gate wait, then the signed `gate` attestation |
| L3 | `just nightly` | systemd user timer | `check`, TruffleHog, toolchain drift |

Run the recipes as `mise x -- just <recipe>` from a shell that does not activate mise. The
pre-push hook refuses a dirty working tree before running `check`.

`just gate` needs the shared SonarQube server at `http://localhost:9000`, the global analysis
token in `SONAR_TOKEN` (or in `~/.config/sonar-tokens/busscope`), and the
[SonarScanner CLI](https://docs.sonarsource.com/sonarqube-server/latest/analyzing-source-code/scanners/sonarscanner/)
on `PATH`, which is not part of `.venv-test` nor of `mise.toml`. The project settings live in
`sonar-project.properties`; the recipe refreshes `coverage.xml` itself before the scan. Never pass
the token on the command line (`-Dsonar.token=...` lands in the shell history and the process
list), and do not share the output of a debug run (`-X`).

A pull request is merged only with `just merge <pr>`, which verifies the `gate` attestation on
the exact head SHA (a signed note on `refs/notes/gate`, checked against
`.github/allowed_signers` of `main`, plus the `gate` commit status required by the branch
protection). Signing is SSH: `git config gpg.format ssh` and `user.signingkey` set to a public key
listed in `.github/allowed_signers`.

New features must maintain at least 90% total coverage and include happy-path, sad-path, and
edge-case tests. Never commit credentials, `.env` files, real captures, or charger-identifying
data.

## Pull requests

Describe the change and its validation, link the Issue with `Closes #<number>`, and complete this
checklist:

- [ ] The design documentation is current and approved when required.
- [ ] Happy paths, sad paths, and edge cases are covered when behavior changes.
- [ ] `just check` passes (tests with at least 90% total coverage, Ruff, strict mypy, Interrogate,
      Semgrep, pip-audit, gitleaks).
- [ ] No credentials, captures, or charger-identifying data are included.
