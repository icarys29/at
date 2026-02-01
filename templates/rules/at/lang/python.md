# Python Rules (at)

Keep Python changes predictable, typed, and testable.

## Conventions

- Prefer explicit types for public functions/methods.
- Prefer small modules; avoid circular imports.
- Prefer structured logging over `print()`.

## Testing

- Default: `pytest` style unit tests.
- Prefer behavior-focused tests over implementation details.

## Safety

- Never read/write secrets files (respect `policies.forbid_secrets_globs`).

