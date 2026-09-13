---
name: curate-memory
description: Curate agent memory as a short-lived working set.
disable-model-invocation: true
---

# Curate memory

Agent memory is a **working set**: notes for work in flight. A memory earns roughly a
week on that basis. Past it, one of two things is true — the knowledge is durable and
**graduates** into checked-in context, or it was scaffolding for work that has landed
and **expires**. Every memory leaves on schedule, by one door or the other.

Curation runs in that order: **measure**, then a **verdict per memory**, then execute.

## The memory system

- `MEMORY.md` is the index — one line per memory, loaded into context every session.
  It stays in lockstep with the files: every file has exactly one index line, and
  every index line has a file.
- **The memory directory is usually NOT git-tracked**, so a curation expires a memory
  by renaming it to `<name>.md.bak`, and the backup lives until the PR merges (steps
  6 and 9).

## Lifetime — a memory earns about a week

| Age | What it takes to keep it |
|---|---|
| **≤ 7 days** | Nothing. It is working-set by default. |
| **8–14 days** | Evidence the work is genuinely still live: an open PR, an open issue, an unmerged branch, a running investigation. Named, not assumed. |
| **> 14 days** | Graduate or expire. There is no third option. |

Two rules cut across the ages:

- **Landing ends a memory's life.** When the PR merges, the ticket closes, the
  incident resolves — the tracker memory expires that day, at any age. What survives
  is whatever graduated out of it.
- **Idle since creation is counter-evidence.** A memory nothing has read since the
  session that wrote it was never load-bearing; hold it to the age table strictly.

## Two bars before anything graduates

### Generic

Checked-in context is read by every developer on every future task, so what graduates
must **bind them all**. Restate the memory as a rule and drop the particulars that
made it an observation: the ticket key, the PR number, the incident date, the person,
the `file:line` that will move next refactor.

- ✅ `Lock payments in the canonical order: Payment → plans → UserPayment. Never filter a plan pre-lock on is_active — a stale read reorders the lock and deadlocks.`
- ❌ `BAC-7653 (Aug 29) deadlocked because charge_offline pre-locked with is_active=True; fixed in PR #16745, see payments/services.py:412.`

A memory that cannot survive that restatement holds no durable knowledge — the
specifics *were* the content. It **expires**.

### Bites again

Generic makes a memory eligible; it doesn't make it worth a line. The bar is **a trap
someone already fell into and someone else would fall into again**: a constraint the
code doesn't show, an ordering that deadlocks, an invariant whose violation surfaces
somewhere far away. Ask what the next person loses without it — "not much" is a
verdict, and the verdict is expire.

**What is gone, goes.** If the integration was removed, the dependency dropped, the
service retired — verify it (step 3), then the memory expires whole, its name with
it. A rule naming something nobody has any more sends the next reader hunting for
code that isn't there.

What graduates keeps the destination's voice: rule first, then the mechanism, then a
file pointer if one earns its place. The war story stays behind.

## Where knowledge belongs — the routing decision

Pick the home by the *nature* of the knowledge, not by topic:

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

**Best fit wins** — the home the knowledge actually belongs in. Only when two homes
fit it equally well does **proximity** break the tie, nearest first:

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

**Extend before you create.** One knowledge item gets one home, and the right home
usually exists already — a fixture the testing rule should mention, a caveat the
existing doc is missing. A new module `AGENTS.md` is cheap where the module has none;
a new rule, doc or root section is a choice to make deliberately.

When a gotcha was **resolved by a mechanism** — a fixture, a helper, a check — the
durable knowledge is the mechanism, not the symptom. Document it where the mechanism
lives, so the workaround stays retired.

## Workflow

### 1. Measure
Run the ledger, then read `MEMORY.md`:

```bash
python3 <skill-dir>/scripts/memory-ledger.py <memory-dir>
```

It prints, per memory: days idle, days old, how many sessions touched it, type,
created and last-touched dates. **Idle days are a floor** — only this project's
transcripts are scanned.

The index one-liners plus the ledger triage most memories. Read full files only for
the ones you will graduate (to write good prose) or whose status you must verify.

### 2. Discover the destinations
- List what already exists: root `AGENTS.md`/`CLAUDE.md`, every module-level one
  (`find . -name 'AGENTS.md' -o -name 'CLAUDE.md'`), `.claude/rules/`,
  `.claude/skills/`, `docs/`, `docs/adr/`. Note the modules with none — those are
  homes you can still create.
- Check whether the memory dir is git-tracked, and clear out any `.md.bak` left by an
  earlier round whose PR has merged (step 9).

### 3. Verify every verdict against ground truth
A memory is a claim; git, the tracker and the code are the record. Each verdict rests
on a fact you checked this session — that is what turns "8–14 days" into a verdict.

- PR/work-tracking memory → `git log --oneline | grep '#<pr>'`, or `gh pr view`.
- Ticket-scoped memory → read the tracker's status.
- "We fixed/retired/deleted X" → confirm X is gone. If it is, nothing about it
  graduates.
- A memory citing `file:line`, a flag, or a construct → confirm it still exists.

### 4. Emit the verdict table
Before touching anything, output **one row per memory** — the whole set, not just the
ones you plan to act on:

| memory | type | age | idle | now | later | when |
|---|---|---|---|---|---|---|
| payments-lock-order-class | project | 12d | 3d | graduate → `payments/AGENTS.md` | — | now |
| bac-7655-event-fanout-lock | project | 11d | 10d | keep | expire | PR #16781 merges (~2026-09-15) |
| prod-rest-api-morning-floor-16539 | project | 15d | 15d | expire | — | now |

- **now** — `expire`, `graduate → <destination>`, or `keep`.
- **later** and **when** — filled only for `keep`. `when` names **the event that ends
  the work**, with a date estimate in parentheses; a bare date is a guess dressed up.
  A keep with no nameable ending event is not a keep — re-read the age table.

### 5. Confirm the plan
The table *is* the plan — present it and get a green light on (a) which memories
graduate and where, and (b) expiry scope. Graduation is outward-facing (it ships as a
PR in step 8); expiry is undoable only for as long as the `.bak` backups survive; and
an edit to the global `CLAUDE.md` reaches no reviewer, so quote its exact lines in
the plan. `AskUserQuestion` with a question per axis works well. Pure "this shipped, remove it"
is within a "prune my memory" request; borderline calls should be surfaced, not
assumed.

### 6. Execute — back up, graduate, expire
- **Back up first.** `cp MEMORY.md MEMORY.md.bak`, and expire a memory by
  `mv <name>.md <name>.md.bak` — never `rm`. `.bak` sits outside the `*.md` glob, so
  backups stay clear of the index, of recall and of step 7's checks, and every
  expired memory is recoverable verbatim until step 9.
- **Graduate before expiring**, so you always write from the source text. Condense
  into the destination's voice, generic per the bars above.
- A rule's glob depends on layout — verify the layout first (`find -type d -name
  tests`). Per-module dirs need `**/<name>/**`, not `<name>/**`.
- A new module `AGENTS.md` mirrors the repo root: where the root keeps `AGENTS.md`
  with a `CLAUDE.md` symlink beside it, create both (`ln -s AGENTS.md CLAUDE.md`) and
  commit both; where the root is a plain `CLAUDE.md`, write that.
- Writing to the global `CLAUDE.md`? Back it up the same way (`cp CLAUDE.md
  CLAUDE.md.bak`), then extend the section that already covers the subject rather
  than opening a new one.
- Keep `MEMORY.md` in sync: remove the expired lines. Maintain a **top pointer note**
  recording where graduated knowledge went, so it isn't re-added to memory later
  (e.g. "billing gotchas → `billing/AGENTS.md`; test gotchas → the `testing` rule").

### 7. Verify consistency
```bash
# counts match, no dangling refs, no orphan files
ls *.md | grep -vx MEMORY.md | wc -l           # files
grep -c '^- \[' MEMORY.md                       # index entries
grep -oP '\]\(\K[^)]+\.md' MEMORY.md | while read f; do [ -f "$f" ] || echo "MISSING $f"; done
for f in $(ls *.md|grep -vx MEMORY.md); do grep -q "($f)" MEMORY.md || echo "ORPHAN $f"; done
ls *.md.bak                                     # one per expired memory, plus MEMORY.md.bak
```

### 8. Open a PR with the graduated knowledge
Graduated knowledge enters shared docs through **review**, not a direct push. Opening
the PR is part of the curation, not a follow-up to offer.

- Resolve the repo's default branch: `DEFAULT_BRANCH` from the repo CLAUDE.md
  **Workflow skills config** block if present, else
  `git symbolic-ref refs/remotes/origin/HEAD`.
- Create a branch off it, e.g. `chore/curate-memory-<yyyy-mm-dd>`.
- Check `git status` and `git add` explicit paths — only the files you changed, so
  the user's unrelated work in progress stays out of the commit.
- One focused commit per logical move reads best (e.g. "document the payments lock
  order in the module's AGENTS.md").
- Push and open the PR following the **`create-pull-request`** skill's recipe.
  There's usually no tracked work item — say so in the body. Structure the body by
  destination: what graduated where, and (for reviewer context) what expired, what
  stayed in memory, and what went to the global `CLAUDE.md` outside this repo.
  Report the PR URL when done.

### 9. After the PR merges — drop the backups
`rm <memory-dir>/*.md.bak`, and the global `CLAUDE.md.bak` if you wrote one. Until
then the backups stay: they are the only copy of
every expired memory, and a graduation that review sends back needs its source text.
If the session ends before the merge, leave them — a stale `.bak` costs nothing, and
the next curation clears it in step 2.

## Rule format

A rule is `.claude/rules/<name>.md` whose body loads into context only when a file
matching its `paths:` glob is in context. Globs support `**`, `*`, and brace
expansion (`{ts,tsx}`).

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
