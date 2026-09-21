---
name: reduce-context
description: Propose and apply a set of skills, plugins, tools and MCP servers to turn off.
disable-model-invocation: true
---

# Trim Claude Code's context

Every skill description, plugin skill, MCP tool schema and built-in tool definition is sent
on **every turn**, used or not. Your job is to turn that into a specific proposal — "these
nine, because you have never once invoked them" — and apply what the person agrees to.

Three scripts do the mechanical half. Everything else is judgement.

| Script | What it does |
|---|---|
| `inventory.sh` | Emits the whole installed inventory as JSON |
| `usage.sh [days]` | Counts what has actually been invoked, from the transcripts |
| `reduce-context.sh --apply <plan.json> [--yes]` | Applies a plan, with a diff and a backup |

## 1. Gather the evidence

```bash
bash "${CLAUDE_PLUGIN_ROOT}/skills/reduce-context/scripts/inventory.sh" > /tmp/inv.json
bash "${CLAUDE_PLUGIN_ROOT}/skills/reduce-context/scripts/usage.sh" 60 > /tmp/usage.json
```

`inventory.sh` runs `claude` headless twice (~15s, two throwaway calls) to read the live
skill list out of the session's init event — once normally, once with `--setting-sources ''`
so skills the person has *already* disabled still show up. Pass `--no-probe` to skip that and
read only what's on disk. Its `bundled[].seen` says whether a name came from the probe or
from the fallback list; a probe under-reports some skills, so both are included.

Read the summary counts, not the whole file — 100+ plugin skills will bury the conversation.
`jq` out what you need.

Ask for `/context` too. It's a slash command, so only the person can run it; its breakdown
tells you whether skills, MCP tools or something else is actually eating their window. Don't
guess at proportions you haven't seen.

## 2. Propose, don't interrogate

Cross the inventory against the usage counts and come back with a concrete set, grouped, with
the reason attached. Never invoked in 60 days is the strongest signal you have. Say what each
group costs and what turning it off gives up.

Two dials per skill, and the difference matters:

- `off` — gone from the model *and* from `/slash`.
- `user-invocable-only` — hidden from the model, still typable as `/name`. No per-turn cost,
  nothing lost. **Default to this** for anything invoked rarely but deliberately.

Beyond skills: whole plugins (`enabledPlugins`), the big tool schemas (`enableArtifact`,
`enableWorkflows`, `disableAgentView`), MCP servers — usually the heaviest single line in
`/context` — and custom subagents, whose descriptions are listed every turn.

Flag anything load-bearing before they agree to it: `disableBundledSkills` drops every shipped
skill at once, `autoMemoryEnabled: false` stops memory being read *and* written, and
`disableAgentView` takes `claude agents`, `--bg` and `/background` with it.

## 3. Apply what they agreed to

Write the plan and hand it to the script:

```json
{
  "skillOverrides": {"dataviz": "off", "code-review": "user-invocable-only"},
  "settings": {"enableArtifact": false},
  "plugins": {"figma@claude-plugins-official": false},
  "mcpDisable": ["some-server"],
  "agentsAside": ["/home/you/.claude/agents/unused.md"]
}
```

```bash
bash "${CLAUDE_PLUGIN_ROOT}/skills/reduce-context/scripts/reduce-context.sh" --apply /tmp/plan.json
```

That prints the diff and writes nothing. Show it, then re-run with `--yes` to apply. It backs
up `settings.json` (and `~/.claude.json` if MCP servers are involved) first.

`mcpDisable` is project-scoped — the same edit `/mcp disable` makes, in the current directory
only. `agentsAside` moves an agent's file into a `disabled/` folder beside it, because agents
have no off switch.

## 4. Close the loop

Changes take effect in the next session. Tell them to restart and run `/context` again — the
before-and-after is the only real proof this worked.

## The human-driven path

If they'd rather click through it themselves, the same thing exists as a nine-stage wizard
with no model in the loop:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/skills/reduce-context/scripts/reduce-context.sh"
```

It walks the same inventory one source per screen, stages everything, and writes nothing until
a final confirmation. Use it when the person wants to see every name themselves, or when
there's no usage history worth mining.
