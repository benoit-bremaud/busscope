# ADR-0007: AI agent — a read-only MCP server in the Python core

**Status:** Accepted — 2026-10-19

## Context

The owner wants to connect an AI agent such as Claude to speed up diagnosis: reading sessions,
decoded values, statistics and logs, and drafting reports. The Model Context Protocol is the
standard way for Claude Code, Claude Desktop and other clients to reach local tools; SDKs exist
in Python (`mcp` 2.3.0) and TypeScript. Captures may contain equipment serial numbers and data
from customers' chargers, and some decoders derive from vendor specifications marked as
confidential.

## Decision

The Python core exposes an **MCP server** with read-only tools: list sessions, read decoded
frames and statistics, read logs, draft a report. Rules:

1. **No tool can transmit on a bus, change a capture setting or open hardware.** The agent is
   bound by the same listen-only rule as the box.
2. **Sharing data with a remote model is opt-in per session**, decided by the operator in the UI,
   with serial numbers and charger identifiers masked by default.
3. The server lives in the core, so it works whether the UI is open or not.

An in-app chat panel may come later on top of the same tools; it is not part of this decision.

## Consequences

- Every MCP tool is covered by tests proving it cannot reach a transmit path.
- Masking rules are part of the core's domain and tested like the decoders.
- Reports drafted by the agent are drafts: the operator edits and exports them.
