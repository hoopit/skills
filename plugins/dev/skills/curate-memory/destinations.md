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
well does **price** break the tie, cheapest first — the ladder below. The closer a
fact lives to the code it governs, the more certainly the reader who needs it sees
it, and the fewer unrelated sessions pay to carry it.

## The price ladder — a dearer home sets a higher bar

A line's **price** is who loads it times how often it is no use to them. The three
bars are the same in every home; what rises with the price is how plainly a rule has
to clear them. Cheapest first:

| Home | Who pays | What it takes | How a stale line gets caught |
|---|---|---|---|
| A **test, hook or assertion** that fails without it | Nobody | Any trap that can be pinned. Prefer it to prose in every home below | It goes red. The one home that cannot rot |
| A **comment or docstring** at the point of use | Only a reader already standing at that code, who always needs it | True, news, and not said by the code itself. One incident is enough, and loud-but-unsolvable is enough | Only by a diff that touches its lines — nobody re-reads it otherwise |
| A **doc** behind a pointer | Whoever follows the pointer | The same, at a length the point of use could not hold | Almost never: no diff touches it and few read it |
| An **ADR** | Whoever follows the pointer | A decision worth its alternatives | It cannot go stale — it is dated by genre, and superseded rather than edited |
| A **skill's body** | Every run of that one task | It would bite most runs of the task | By the agent that follows it and finds it wrong |
| A **module `AGENTS.md`** | Every session working in that subtree | **Silent**, and binding more than one place in the module — bound to one place, it is a comment | Read constantly, one file, fixed in a line |
| A **path-scoped rule** | Every edit to a file of that type, in every module | **Silent**, and met or plainly reachable in more than one module | As above |
| **Root `AGENTS.md`** | Every session in the repo | **Silent**, costly when missed, and no module or glob holds it | As above |
| The **global `CLAUDE.md`** | Every session in every repo | A standing instruction the user gave, or a fact about their machine that bites most weeks | As above |

**A cheap home asks less of the rule and more of its form.** The rungs nobody
re-reads are the rungs where a stale line lives for years, so a line placed there
has to **die with its code**:

- It has an **anchor**: lines beside it that exist because of the fact, so whoever
  changes them meets the comment in the same diff. The fact may be local (the
  invariant these lines hold) or remote (the vendor behaviour they work around) —
  when a remote fact changes, its anchor has to change with it.
- It carries nothing that drifts on its own: no counts, versions, ids, dates, no
  name of a function that lives elsewhere.

A fact with **no anchor** — true and useful, with no code resting on it — has nothing
to bring it back into anyone's view: a cloud API's 90-day lookup window, a library
version's quirk. Pin it with a test (`event_scrubber is not None` outlives "sdk 2.68
drops the scrubber"), or place it in a home that is read, at that home's bar. A doc
takes only what stays true while the code moves: a subsystem's shape, an
integration's contract — never its state.

A read home rots less often and costs more when it does: a stale comment misleads
one reader, a stale `AGENTS.md` line misleads every session, and is believed. The
drift rule binds every rung.

**Step down before expiring.** A rule that misses the bar of the home it asked for is
tried one rung cheaper, as long as that rung still fits what the rule is and the
rule can take that rung's form: the
migration trap too rare for the rule file is a comment on the one migration that
shows it. A rule that misses at the comment rung expires.

**Step up only on evidence.** A rule climbs to an always-loaded home because it was
met in a second place, never because it felt important.

Three boundaries price doesn't settle:

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
