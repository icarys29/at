# Pattern: Public API Standards

## Intent

- Provide predictable, stable public interfaces (endpoints, CLI commands, SDK public APIs).

## When to Use

- Use when introducing or changing any public API surface.
- Treat changes here as part of the external contract.

## Example

- Versioning:
  - Additive changes are preferred; breaking changes require an explicit version bump.
- Naming:
  - Use consistent nouns/verbs; avoid abbreviations unless standard in the domain.
- Errors:
  - Standardize error shape and codes; avoid leaking internal stack traces.
- Deprecation:
  - Announce deprecation with a timeline; keep backward compatibility until the removal date.

## Constraints

- Keep this doc short; link to an ADR only when a decision will matter in 3+ months.
- Do not document obvious folder structure; document the contract and its stability rules.

