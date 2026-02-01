# Go Rules (at)

Keep Go changes idiomatic, small, and concurrency-safe.

## Conventions

- Keep packages cohesive; avoid import cycles.
- Prefer context propagation (`context.Context`) in public APIs.
- Avoid global mutable state unless justified.

## Testing

- Default: `go test ./...`
- Prefer table-driven tests for multiple cases.

