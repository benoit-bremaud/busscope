# ADR-0001: Adopt an ADR register; freeze the historical decision log

**Status:** Accepted — 2026-10-19

## Context

Decisions so far live as dated paragraphs in `docs/architecture/decisions.md`. They record the
outcome but not the options compared, and they cannot be superseded explicitly. The project is
growing from a CAN monitor into a hardware box plus a desktop application, which brings many
structural choices (MCU, toolchains, UI stack) whose reasoning must stay auditable. Other projects
of the same owner use one ADR per decision with the scoring that produced it.

## Decision

Decisions are recorded under `docs/decisions/` as Nygard ADRs with their MCDA scoring and their
fallback. `docs/architecture/decisions.md` is frozen as the historical log: its entries remain
valid and are not rewritten; a change to one of them is made by a new ADR that cites it.

## Consequences

- Every structural decision from now on is an ADR, reviewed in its own pull request.
- The safety decisions of the historical log (read-only first, guarded manual transmission) keep
  applying to the box and the new UI until an ADR supersedes them.
