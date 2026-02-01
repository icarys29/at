# Architecture (at) — Project Overview

- Last updated: 2026-02-01

## 1) Architecture summary (concise)

- Style: (fill in, e.g., layered / hexagonal / modular monolith / microservices)
- Primary runtime(s): (fill in)
- Data stores: (fill in)
- Communication: (fill in)

## 2) Architecture patterns in use

Keep this section short and factual. Prefer bullets over prose.

- (Pattern) — where it is used and why.
- (Pattern) — where it is used and why.

## 3) Boundaries & dependencies (corporate-grade)

Document constraints that help prevent “big ball of mud”.

- Boundary: `<module/package>` owns `<capability>`; do not call into `<other module>` directly.
- Allowed dependency directions: (fill in)
- Forbidden dependencies: (fill in)

## 4) Key decisions (ADR index)

- ADRs live under `docs/adr/`.
- Keep ADRs short; record decisions only when they materially affect future work.

