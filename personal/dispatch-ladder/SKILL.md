---
name: dispatch-ladder
description: The backlog daemon's Effort-to-model/effort ladder.
user-invocable: false
---

# The dispatch ladder

Every unattended start is priced off one table: the board's **Effort** (XS..XL) picks the
model and the reasoning effort the agent is started on. The table lives in
[`ladder.json`](ladder.json) beside this file — read it for the current rungs rather than
copying them. `hoopit-board next` reads it at every tick, `start-backlog-daemon` passes each
rung to `claude --model <model> --effort <effort>`, and `review-dispatch` is the only
procedure that moves a rung.

- `models` and `efforts` list the axes cheapest first; that order is what "under" means.
- `rungs` maps each Effort to a `{model, effort}` pair.

## The rule

**No rung is priced under a smaller one.** Rungs compare by model first, then effort, both
in the order the axes list them; `hoopit-board` refuses to load a ladder that breaks this.
It is a ladder over model *and* effort together — checking effort alone is the wrong test,
since XS and S differ by model, not effort.

Two adjacent rungs may be equal. That costs two things: the Effort between them no longer
changes what an agent is given, and `hoopit-board dispatches` groups by `model/effort`, so
the two tiers' work pools into one row that `review-dispatch` can no longer read apart.

Every rung names its effort. An unset one would inherit `~/.claude/settings.json`
(`effortLevel`, and `modelSettings` per model), which a dispatch must never depend on.

## Model names are aliases

`model` is a Claude Code alias (`sonnet`, `opus`, `fable`), resolved by the installed CLI
at start. A CLI update can move an alias to a newer model with no change here — confirm
what one resolves to with
`claude -p --model <alias> --output-format json ok`, whose `modelUsage` names the model.
The claim comment records the alias, so the dispatch record cannot tell two versions behind
one alias apart; say so when reading a window that spans an alias moving.
