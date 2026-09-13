# Destinations

Where knowledge lives once it graduates out of memory: the homes it can take, the
boundaries between them, and the format each one wants. Reached from step 2 of
[`SKILL.md`](SKILL.md); keep it open through the verdict table and the write-up.

## Pick the home by the nature of the knowledge, not by topic

| If the knowledge is… | It belongs in… | Why |
|---|---|---|
| A constraint a reader must honour **at one specific place in the code** | a **comment or docstring right there** — better still, a test or hook that fails without it | Unmissable, and it travels with the code it binds |
| A gotcha or convention scoped to **one module/app directory** | that module's **`AGENTS.md`** — create one if there is none | Always-on in that subtree, invisible everywhere else |
| An always-applicable convention for **every file of a type, across modules** (every model, migration, view, test, admin) | a **path-scoped rule** `.claude/rules/<x>.md` | Auto-loads whenever a matching file is in context — no reliance on model invocation |
| A **decision** worth its alternatives and consequences (why this design, what it costs) | an **ADR**, in the nearest `docs/adr/` that covers the subject | The genre whose content *is* the reasoning; rules and `AGENTS.md` carry verdicts, not deliberation |
| Background a reader needs **occasionally and at length** (a subsystem's shape, an integration's contract) | a **doc** beside the code it describes, pointed at from the nearest `AGENTS.md` | Too long to always-load; the pointer does the triggering |
| An **on-demand procedure** for a specific, *occasional* task (a how-to you invoke when doing X) | **stays / becomes a skill** | Description-gated, model-invoked by semantic trigger — not loaded on every edit |
| Genuinely **repo-wide**, touching many modules with **no path glob that targets them** | **root `AGENTS.md`** (or root `docs/`) | Always-on everywhere — the highest bar in the repo |
| Already **enforced by a test/hook or documented next to the code** (a CI-config comment, a `test_*` that fails) | **expire** | The point-of-use copy wins; memory is pure duplication |
| A **one-off finding tied to one ticket** — a bug's cause, a review round, a migration's steps — with no rule left once it lands | **expire** | git log, the PR and the ticket are the record |
| Durable but **yours alone** — this machine's quirks, your tooling and access setup, how you want work handled — and true in every repo you touch | the **user's global `CLAUDE.md`** (`~/.claude/CLAUDE.md`) | The one home outside the repo, for what a teammate would find wrong or irrelevant |
| **Live-ops** state (incidents, alarms, live infrastructure) or **in-flight** work | **keep as memory** | Still moving; nothing to write down yet |

## Best fit wins

Take the home the knowledge actually belongs in. Only when two homes fit it equally
well does **proximity** break the tie, nearest first:

> local comment/doc → module `AGENTS.md` / local ADR / local doc → path-scoped rule →
> skill → root `AGENTS.md` / root docs / root ADR

The closer a fact lives to the code it governs, the more certainly the reader who
needs it sees it, and the fewer unrelated sessions pay to carry it.

Three boundaries proximity doesn't settle:

- **Repo or you?** Scope decides, before anything else. What a teammate would need
  goes in the repo, even when you are the only one who has hit it; what binds your
  machine, your shell or your access goes in the global `CLAUDE.md`, where it is out
  of everyone else's way. Global loads in every session of every project, so the
  *bites again* bar applies hardest of all there.
- **Rule or module?** A rule earns its glob when the same gotcha binds files in
  *many* modules; one module's quirk goes in that module's `AGENTS.md`, however
  tempting a tidy new rule file looks. "Every migration is reversible" is a rule;
  "this module's amounts are minor units" is that module's `AGENTS.md`.
- **Rule or skill?** A rule binds essentially *every* edit to files of its type; a
  skill fires for one particular task. "Every view uses `@http`" is a rule; "bump an
  API version" is a skill.

## Extend before you create

One knowledge item gets one home, and the right home usually exists already — a
fixture the testing rule should mention, a caveat the existing doc is missing, the
section of the global `CLAUDE.md` that already covers your shell. A new module
`AGENTS.md` is cheap where the module has none; a new rule, doc or root section is a
choice to make deliberately.

When a gotcha was **resolved by a mechanism** — a fixture, a helper, a check — the
durable knowledge is the mechanism, not the symptom. Document it where the mechanism
lives, so the workaround stays retired.

## Formats

### Path-scoped rule

`.claude/rules/<name>.md`, whose body loads into context only when a file matching its
`paths:` glob is in context. Globs support `**`, `*`, and brace expansion
(`{ts,tsx}`).

```markdown
---
paths:
  - "**/tests/**"
  - "**/test_*.py"
  - "**/conftest.py"
---

# Testing
...rule body...
```

The glob depends on layout, so check the layout before writing it (`find -type d
-name tests`). Directories that repeat per module need `**/<name>/**`; `<name>/**`
matches only at the root.

### Module `AGENTS.md`

Mirror the repo root: where the root keeps `AGENTS.md` with a `CLAUDE.md` symlink
beside it, create both (`ln -s AGENTS.md CLAUDE.md`) and commit both; where the root
is a plain `CLAUDE.md`, write that.
