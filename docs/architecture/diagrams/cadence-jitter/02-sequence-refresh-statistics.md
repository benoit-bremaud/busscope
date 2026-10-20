# Sequence diagram — cadence jitter analysis — refresh statistics

> **Feature**: epic #23 — [Add CAN frame cadence jitter analysis](https://github.com/benoit-bremaud/busscope/issues/23)
> **Source specs**: `docs/architecture/specs/cadence-jitter-analysis.md` §Rules, §Presentation

## Context

This sequence clarifies the refresh path from the UI to the framework-independent analyzer,
including per-identifier grouping and interval filtering. It does not cover CAN capture or
CSV export.

## Diagram

```mermaid
sequenceDiagram
    actor Operator
    participant UI as Statistics view
    participant Analyzer as TemporalAnalyzer
    participant Records as Captured records

    Operator->>UI: Refresh statistics
    UI->>Records: Read retained capture
    UI->>Analyzer: summarize(records)
    loop For each arbitration identifier
        Analyzer->>Analyzer: Group frames in capture order
        Analyzer->>Analyzer: Calculate positive consecutive intervals
        Analyzer->>Analyzer: Calculate period, frequency, min, max, deviation
    end
    Analyzer-->>UI: IdentifierStatistics collection
    UI-->>Operator: Display cadence metrics
```

## Notes

- The analyzer receives plain captured records and has no dependency on PySide6 or SocketCAN.
- Non-increasing timestamps are excluded from interval metrics without reordering records.
- No transmission path is present in this read-only flow.
