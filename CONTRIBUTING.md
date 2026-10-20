# Contributing

## Workflow

1. Start from an Issue with an explicit scope and acceptance criteria.
2. Create a dedicated branch from an up-to-date `main` before editing any project file.
3. Add or update proportional UML documentation before implementing behavior or architecture.
4. Obtain design approval before implementation.
5. Keep changes focused and follow Clean Architecture, SOLID, KISS, DRY, and YAGNI.
6. Use Angular Conventional Commits: `type(scope): description`.
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
3. Merge the preparation pull request into `main` and wait for all checks to pass.
4. Create an annotated, signed `vMAJOR.MINOR.PATCH` tag from that exact `main` commit.
5. Push only the release tag and publish a GitHub release using the matching changelog section.

Published versions are immutable: never move, delete, or reuse a release tag. Tag protection is
defined in [`.github/tag-protection.md`](.github/tag-protection.md).

## Validation

Use the isolated test environment and run:

```bash
.venv-test/bin/pytest
.venv-test/bin/ruff check .
.venv-test/bin/mypy
```

Before a pull request, also run the local SonarQube analysis. It needs the shared server at
`http://localhost:9000`, the global analysis token exported as `SONAR_TOKEN`, and the
[SonarScanner CLI](https://docs.sonarsource.com/sonarqube-server/latest/analyzing-source-code/scanners/sonarscanner/)
on `PATH`, which is not part of `.venv-test`. The project settings live in
`sonar-project.properties`. Run both commands from the repository root, in this order, so the
scan reads a fresh coverage report:

```bash
.venv-test/bin/pytest --cov-report=xml:coverage.xml
sonar-scanner -Dsonar.qualitygate.wait=true
```

The scan must end with `QUALITY GATE STATUS: PASSED`. Never pass the token on the command line
(`-Dsonar.token=...` lands in the shell history and the process list), and do not share the
output of a debug run (`-X`).

New features must maintain at least 90% total coverage and include happy-path, sad-path, and
edge-case tests. Never commit credentials, `.env` files, real captures, or charger-identifying
data.

## Pull requests

Describe the change and its validation, link the Issue with `Closes #<number>`, and complete this
checklist:

- [ ] The design documentation is current and approved when required.
- [ ] Happy paths, sad paths, and edge cases are covered when behavior changes.
- [ ] Tests pass with at least 90% total coverage.
- [ ] Ruff and strict mypy checks pass.
- [ ] No credentials, captures, or charger-identifying data are included.
