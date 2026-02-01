# at (global rules)

- Use `.claude/project.yaml` as the source of truth for format/lint/type/test/build commands.
- Keep plugin baseline rules under `.claude/rules/at/`; keep repo-specific rules under `.claude/rules/project/`.
- Prefer small, verifiable changes over large refactors unless requested.
- Do not commit secrets; avoid reading/writing `.env` and `secrets/**` unless explicitly required.
- Finish non-trivial workflows with a compliance decision backed by evidence.

