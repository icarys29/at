# Opportunities: Leveraging Claude Code Specificities

## Currently Underutilized Features

### 1. Frontmatter Capabilities

**Current state:** Basic frontmatter in agents (name, description, model, tools, disallowedTools, permissionMode)

**Missed opportunities:**

#### `skills:` injection
Claude Code can inject full skill content into agent context:
```yaml
---
name: implementor
skills:
  - quality-commands  # Inject quality command reference
  - file-conventions  # Inject naming/structure rules
---
```
This eliminates the need for `build_task_contexts.py` to manually assemble context.

#### `inputs:` declaration (if supported)
Declare expected inputs explicitly:
```yaml
---
name: action-planner
inputs:
  - SESSION_DIR/inputs/request.md
  - SESSION_DIR/inputs/context_pack.md
  - SESSION_DIR/planning/ARCHITECTURE_BRIEF.md?  # ? = optional
---
```

#### `outputs:` declaration
Declare outputs for automatic validation:
```yaml
---
name: action-planner
outputs:
  required:
    - planning/actions.json
    - planning/VERIFICATION_CHECKLIST.md
  optional:
    - planning/REQUIREMENT_TRACEABILITY_MATRIX.md
---
```

### 2. Native Permission Modes

**Current state:** Complex `enforce_file_scope.py` hook (325 lines) that parses transcripts, maintains task maps, and infers scope.

**Better approach:** Use Claude Code's native `permissionMode`:

| Mode | Behavior |
|------|----------|
| `acceptEdits` | Auto-approve file edits (current default) |
| `askEdits` | Prompt user for approval (safer) |
| `bypassPermissions` | Skip all prompts (trusted agents) |

For scope enforcement, combine `permissionMode: askEdits` with clear instructions:
```markdown
## Write Scope
You may ONLY write to these paths:
- src/components/auth/LoginForm.tsx
- src/components/auth/LoginForm.test.tsx

If you need to write elsewhere, STOP and report the scope mismatch.
```

This is simpler, faster, and more transparent than hook-based enforcement.

### 3. `@imports` and Rule Files

**Current state:** `build_context_pack.py` manually assembles context from:
- `.claude/project.yaml`
- `CLAUDE.md`
- `.claude/rules/**/*.md`
- Docs registry
- Language packs

**Better approach:** Use `@imports` in CLAUDE.md or agent files:
```markdown
@import .claude/project.yaml
@import .claude/rules/at/global.md
@import docs/DOCUMENTATION_REGISTRY.json

# Additional context for this session
...
```

Claude Code handles file resolution, caching, and truncation natively.

### 4. Memory and Rules System

**Current state:** Custom learning system with `scripts/learning/*.py` (~6 files, ~400 lines)

**Better approach:** Use Claude Code's native memory:
- `CLAUDE.md` — Project-wide instructions (already used)
- `.claude/rules/**/*.md` — Always-on rules with glob matching
- `~/.claude/CLAUDE.md` — User-wide preferences

The learning system duplicates this with extra complexity:
- `learning/learning_state.py` — State management
- `learning/update_learning_state.py` — State updates
- `learning/install_learning_hooks.py` — Hook setup

Consider:
1. Using Claude Code's native rule files for persistent patterns
2. Outputting ADR stubs directly to `docs/adr/` (already done)
3. Removing the intermediate `learning/` directory abstraction

### 5. Hooks — Focused Usage

**Current state:** Hooks for scope enforcement, audit logging, session lifecycle, subagent validation, docs drift detection, UX nudges.

**Recommended refinement:**

| Hook | Keep/Remove | Reason |
|------|-------------|--------|
| `SubagentStop` → `on_subagent_stop.py` | **Simplify** | Validates reply format; could be agent instruction |
| `PreToolUse` → `validate_task_invocation.py` | **Remove** | Orchestrator controls Task calls |
| `PreToolUse` → `enforce_file_scope.py` | **Replace** | Use `permissionMode` + instructions |
| `PostToolUse` → `validate_actions_write.py` | **Remove** | Duplicates validate_actions.py |
| Audit hooks | **Keep** | External logging is legitimately hook territory |
| Policy hooks | **Keep** | Secrets protection is a valid guardrail |

### 6. Plugin Manifest Features

**Current state:** Minimal `plugin.json`:
```json
{
  "name": "at",
  "version": "0.3.1",
  "description": "...",
  "lspServers": "./.lsp.json"
}
```

**Expansion opportunities:**

```json
{
  "name": "at",
  "version": "0.3.1",
  "description": "...",
  "lspServers": "./.lsp.json",
  "commands": {
    "run": "skills/run/SKILL.md",
    "init": "skills/init-project/SKILL.md",
    "doctor": "skills/doctor/SKILL.md"
  },
  "agents": {
    "implementor": "agents/implementor.md",
    "tests-builder": "agents/tests-builder.md"
  },
  "hooks": "hooks/hooks.json",
  "config": {
    "schema": "schemas/project.schema.json",
    "default": "templates/project.yaml"
  }
}
```

### 7. Model Selection in Frontmatter

**Current state:** All agents use `model: sonnet`

**Opportunity:** 3-tier strategic model selection:

| Agent | Recommended Model | Reason |
|-------|-------------------|--------|
| `solution-architect` | `opus` | Strategic architectural decisions |
| `action-planner` | `opus` | Complex planning, parallel execution |
| `root-cause-analyzer` | `opus` | Deep investigation, pattern recognition |
| `brainstormer` | `opus` | Strategic ideation, tradeoff analysis |
| `implementor` | `sonnet` | Code generation (execution-focused) |
| `tests-builder` | `sonnet` | Test generation (execution-focused) |
| `reviewer` | `haiku` | Report generation, lower complexity |
| `docs-keeper` | `haiku` | Minimal edits, registry updates |
| `compliance-checker` | `haiku` | Simple yes/no decisions |
| `story-writer` | `haiku` | Template-driven output |

**3-Tier Strategy:**
- **Opus**: Strategic thinking, architectural decisions, complex reasoning
- **Sonnet**: Code generation, execution-focused tasks
- **Haiku**: Simple reports, minimal edits, template-driven work

### 8. Structured Output Contracts

**Current state:** Agents must reply with:
```
STATUS: DONE
SUMMARY: <bullets>
REPO_DIFF:
- <files>
SESSION_ARTIFACTS:
<paths>
```

This is validated by `on_subagent_stop.py` hook.

**Better approach:** Use frontmatter `outputs:` and trust the model:
```yaml
---
outputs:
  format: structured
  fields:
    - status: enum(DONE, PARTIAL, BLOCKED)
    - summary: string[]
    - changed_files: string[]
    - session_artifacts: string[]
---
```

Claude Code may support structured output validation natively (check latest docs).

## Implementation Priority

1. **High Impact, Low Effort**
   - Switch to `permissionMode` for scope control
   - Use `@imports` in context assembly
   - Add model selection to agents

2. **High Impact, Medium Effort**
   - Replace `build_context_pack.py` with prompt templates
   - Simplify hooks to essential-only

3. **Medium Impact, High Effort**
   - Migrate learning system to native rules
   - Implement frontmatter `skills:` injection
   - Restructure plugin manifest

## Claude Code Feature Requests

Features that would help this plugin if Claude Code supported them:

1. **Declarative agent outputs** — Validate output structure in frontmatter
2. **Agent-to-agent context passing** — Native way to pass artifacts between subagents
3. **Scoped file permissions per agent** — Declare allowed write paths in frontmatter
4. **Session persistence** — Native session concept (not just transcript)
5. **Batch tool calls** — Run multiple scripts in one subprocess for latency reduction
