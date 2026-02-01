# Gaps & Remediation Plans (at)

This folder contains **gap analyses** between the former `at` plugin implementation and the current rebuild, plus **actionable remediation plans** aligned with the current architecture (session-backed, deterministic, `uv run` scripts, docs registry v2).

## Files

- `plan/gaps/2026-02-01-gap-analysis.md` — capability-by-capability comparison (former vs current), with pros/cons and missing functionality.
- `plan/gaps/2026-02-01-remediation-action-plan.md` — prioritized remediation roadmap and design guidance to close the gaps without blindly copying the former plugin.
- `plan/gaps/2026-02-01-remediation-backlog.json` — structured backlog derived from the remediation plan (workstreams, items, deliverables, verification).
