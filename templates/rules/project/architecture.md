# Architecture Rules (project)

Keep this concise and enforceable.

## Intent

- Define boundaries and dependency direction.
- Make rule violations obvious (and ideally enforce via `.claude/at/enforcement.json`).

## Boundaries

- Domain: TODO
- Application: TODO
- Adapters/Infra: TODO

## Dependency Rules

- TODO: Domain MUST NOT import from Application/Adapters.
- TODO: Application MUST NOT import from Adapters.

