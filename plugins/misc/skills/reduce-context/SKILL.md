---
name: reduce-context
description: Walk through turning off the skills, plugins, tools and MCP servers you never use.
disable-model-invocation: true
---

# Trim Claude Code's context

Every skill description, plugin skill, MCP tool schema and built-in tool definition is
sent on **every turn**, used or not. This runs an interactive wizard over what's actually
installed on this machine and turns off what the person doesn't want.

Run it, and stay out of its way — it is the human's wizard, not yours:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/skills/reduce-context/scripts/reduce-context.sh"
```

It needs `jq`. It stages every change and writes nothing until the final confirmation,
backing up `~/.claude/settings.json` (and `~/.claude.json`, if MCP servers are disabled)
first.

## What it walks, in order

1. **Built-in skills** shipped inside the `claude` binary — a curated list, since they
   aren't on disk. An override for a name a build doesn't have is a harmless no-op.
2. **Account-synced skills** (`anthropic-skills:*`), read from `~/.claude/skills/synced/`.
3. **Whole plugins** — the biggest single win when a plugin ships an MCP server nobody calls.
4. **Individual skills** from each kept plugin, plus `~/.claude/skills` and `.claude/skills`,
   one source per screen.
5. **Built-in tools** whose schemas ride along every turn: Artifact, Workflows, agent view,
   auto-memory — and `disableBundledSkills`, which drops every shipped skill at once.
6. **MCP servers**, disabled for the current project only (the same edit `/mcp disable` makes).
7. **Custom subagents**, whose descriptions are listed every turn. There is no off switch,
   so their definition files move into a `disabled/` folder beside them.

Each skill gets two dials: `off` (gone from the model *and* from `/slash`) and
`user-invocable-only` (hidden from the model, still typable as `/name` — no per-turn cost).

## Afterwards

Changes land in `settings.json` and take effect on the next session. `/context` shows the
new baseline, `/skills` and `/mcp` reverse anything by hand, and the timestamped backup
restores the lot.
