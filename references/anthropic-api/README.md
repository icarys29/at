---
status: stable
last_updated: 2026-02-01
sources:
  - https://docs.anthropic.com/en/api/
  - https://docs.anthropic.com/en/api/messages
---

# Anthropic API (Official Docs Summary)

Condensed, **paraphrased** notes from Anthropic’s official API docs. Keep this as a quick reference for integrations and error handling.

## Authentication

- Use an API key via request headers (see official docs for the exact header names and required version header).
- Never log keys; treat request/response bodies as potentially sensitive.

## Messages API (conceptual)

- Primary operation: create a message with:
  - `model`
  - `max_tokens`
  - `messages` (role-based content)
  - Optional: `system`, tool definitions, and tool-use handling
- Responses include model output content plus metadata (usage, stop reason, etc.).

## Tool use (high-level)

- You define tools (name + JSON schema input) and the model can emit tool calls.
- Your app executes tools and returns tool results back as messages.

## Errors & retries (high-level)

- Handle rate limiting with exponential backoff + jitter.
- Distinguish transient errors (retry) vs permanent request errors (fix request).
- Log: request id, status, and sanitized context needed for debugging.
