# Rust Rules (at)

Keep Rust changes safe, idiomatic, and explicit about ownership.

## Conventions

- Prefer clear ownership/lifetime boundaries over cleverness.
- Avoid `unsafe` unless absolutely required; justify it.
- Keep modules small; prefer composition.

## Testing

- Default: `cargo test`
- Prefer unit tests close to the module under test.

