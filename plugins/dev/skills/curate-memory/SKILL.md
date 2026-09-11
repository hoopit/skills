---
name: curate-memory
description: Curate agent memory as a short-lived working set.
disable-model-invocation: true
---

# Curate memory

Agent memory is a **working set**: notes for work in flight. A memory earns roughly a
week on that basis. Past it, one of two things is true — the knowledge is durable, and
**graduates** into checked-in context where every developer and their agents will see
it; or it was scaffolding for work that has landed, and **expires**. Nothing stays in
memory because deleting it felt risky.

So curation runs in that order: **measure**, then a **verdict per memory**, then
execute.

## The memory system (what you're working with)

- Memories live as one-fact-per-file markdown under the memory directory, each with
  `name` / `description` / `metadata.type` frontmatter.
- `MEMORY.md` is the index: **one line per memory**, loaded into context every
  session. Keep it in lockstep with the files — every file has exactly one index
  line, and vice-versa.
- **The memory directory is usually NOT git-tracked**, so deleting a memory is
  irreversible. Confirm before bulk deletion (see step 5). Check with
  `git -C <memory-dir> rev-parse --is-inside-work-tree`.
- Memories are **point-in-time observations, not live state**. Never act on a
  memory's claim without re-verifying it (see step 3).

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

## Generic, or it doesn't graduate

Checked-in context is read by every developer on every future task, so what graduates
must **bind them all**. Restate the memory as a rule and drop the particulars that
made it an observation: the ticket key, the PR number, the incident date, the person,
the `file:line` that will move next refactor.

- ✅ `Lock payments in the canonical order: Payment → plans → UserPayment. Never filter a plan pre-lock on is_active — a stale read reorders the lock and deadlocks.`
- ❌ `BAC-7653 (Aug 29) deadlocked because charge_offline pre-locked with is_active=True; fixed in PR #16745, see payments/services.py:412.`

A memory that cannot survive that restatement holds no durable knowledge — the
specifics *were* the content. It **expires**; it does not graduate.

Everything that graduates keeps the destination's voice: rule first, then the
mechanism, then a file pointer if one earns its place. Drop the war story.

## Where knowledge belongs — the routing decision

For each graduating memory, pick the home by the *nature* of the knowledge, not by
topic:

| If the knowledge is… | It belongs in… | Why |
|---|---|---|
| An always-applicable convention for **every file of a type** (every model, migration, view, test) | a **path-scoped rule** `.claude/rules/<x>.md` | Auto-loads whenever a matching file is in context — no reliance on model invocation |
| A gotcha scoped to **one directory's code** (e.g. infra in `cdk/`) | that directory's **`CLAUDE.md`** | Always-on while working in that subtree |
| **Cross-cutting**, always-relevant, touches many files with **no clean path glob** | **root `CLAUDE.md`** | Always-on everywhere; a rule glob can't target it |
| A **decision** worth its alternatives and consequences (why this design, what it costs) | an **ADR** under `docs/adr/` | The genre whose content *is* the reasoning; rules and CLAUDE.md carry verdicts, not deliberation |
| Background a reader needs **occasionally and at length** (a subsystem's shape, an integration's contract) | a **doc** under `docs/`, pointed at from the nearest `CLAUDE.md` | Too long to always-load; the pointer does the triggering |
| An **on-demand procedure** for a specific, *occasional* task (a how-to you invoke when doing X) | **stays / becomes a skill** | Description-gated, model-invoked by semantic trigger — not loaded on every edit |
| Already **enforced by a test/hook or documented next to the code** (a CI-config comment, a `test_*` that fails) | **expire** | The point-of-use copy wins; memory is pure duplication |
| A **one-off finding tied to one ticket** — a bug's cause, a review round, a migration's steps — with no rule left once it lands | **expire** | git log, the PR and the ticket are the record |
| **Personal** (your access/secrets setup), **live-ops** state (incidents, alarms, live AWS), or **in-flight** work | **keep as memory** | Not team-doc material; not derivable from the repo |

Rule-vs-skill: a **rule** binds essentially *every* edit to files of its type; a
**skill** fires only for one particular task. "Every view uses `@http`" is a rule;
"bump an API version" is a skill.

One knowledge item gets **one** home. When the same gotcha spans many sibling
directories, a single path-scoped rule covers them all — reach for that rather than a
copy in each directory's `CLAUDE.md`.

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
ones you will graduate (to write good prose) or whose status you must verify.

### 2. Discover the destinations and verify reversibility
- Find the surfaces that already exist: root `CLAUDE.md`, any directory `CLAUDE.md`
  (`find . -name CLAUDE.md`), `.claude/rules/`, `docs/`, `docs/adr/`. Match the
  style already there — extend a section, don't reinvent.
- Confirm whether the memory dir is git-tracked (deletions reversible or not).

### 3. Verify each candidate against ground truth — NEVER trust the memory blindly
This is what turns "8–14 days" from a guess into a verdict.

- PR/work-tracking memory → `git log --oneline | grep '#<pr>'`, or `gh pr view`.
  Merged ⇒ the work landed ⇒ the tracker expires today.
- Ticket-scoped memory → check the tracker's status before assuming it is live.
- "We fixed/retired/deleted X" → confirm X is actually gone before expiring on that
  basis.
- A memory citing `file:line`, a flag, or a construct → confirm it still exists.

### 4. Emit the verdict table
Before touching anything, output **one row per memory** — the whole set, not just the
ones you plan to act on:

| memory | type | age | idle | now | later | when |
|---|---|---|---|---|---|---|
| payments-lock-order-class | project | 12d | 3d | graduate → `.claude/rules/payments.md` | — | now |
| bac-7655-event-fanout-lock | project | 11d | 10d | keep | expire | PR #16781 merges (~2026-09-15) |
| prod-rest-api-morning-floor-16539 | project | 15d | 15d | expire | — | now |

- **now** — `expire`, `graduate → <destination>`, or `keep`.
- **later** and **when** — filled only for `keep`. `when` names **the event that ends
  the work**, with a date estimate in parentheses; a bare date is a guess dressed up.
  A keep with no nameable ending event is not a keep — re-read the age table.

### 5. Confirm before outward/irreversible actions
The table *is* the plan — present it and get a green light on (a) which memories
graduate and where, and (b) expiry scope. Graduation is outward-facing (it ships as a
PR in step 8) and expiry is irreversible. `AskUserQuestion` with a question per axis
works well. Pure "this shipped, remove it" is within a "prune my memory" request;
borderline calls should be surfaced, not assumed.

### 6. Execute — graduate first, then expire the source
- **Graduate before deleting** so you never lose the source text. Condense into the
  destination's voice, generic per the rule above.
- When a rule's glob depends on layout, **verify the layout** first
  (`find -type d -name tests`). Per-app dirs need `**/<name>/**`, not `<name>/**`.
- Keep `MEMORY.md` in sync: remove the expired lines. Maintain a **top pointer note**
  recording where graduated knowledge went, so it isn't re-added to memory later
  (e.g. "CDK gotchas → cdk/CLAUDE.md; test gotchas → the `testing` rule").

### 7. Verify consistency
```bash
# counts match, no dangling refs, no orphan files
ls *.md | grep -vx MEMORY.md | wc -l           # files
grep -c '^- \[' MEMORY.md                       # index entries
grep -oP '\]\(\K[^)]+\.md' MEMORY.md | while read f; do [ -f "$f" ] || echo "MISSING $f"; done
for f in $(ls *.md|grep -vx MEMORY.md); do grep -q "($f)" MEMORY.md || echo "ORPHAN $f"; done
```

### 8. Open a PR with the graduated knowledge
Graduated knowledge enters shared docs through **review**, not a direct push. Finish
the curation by opening the PR; don't wait to be asked.

- Resolve the repo's default branch: `DEFAULT_BRANCH` from the repo CLAUDE.md
  **Workflow skills config** block if present, else
  `git symbolic-ref refs/remotes/origin/HEAD`.
- Create a branch off it, e.g. `chore/curate-memory-<yyyy-mm-dd>`.
- Stage **only the files you changed** — never sweep up the user's unrelated
  in-progress work. Check `git status` and `git add` explicit paths.
- One focused commit per logical move reads best (e.g. "promote payments lock order
  to a path-scoped rule").
- Push and open the PR following the **`create-pull-request`** skill's recipe.
  There's usually no tracked work item — say so in the body. Structure the body by
  destination: what graduated where, and (for reviewer context) what expired or
  stayed private. Report the PR URL when done.

## Path-scoped rules — the format

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

The three loading mechanisms, side by side: a nested `CLAUDE.md` loads by *directory
proximity*, a rule by *path glob match*, a skill by *model invocation* (description-
gated, and narrowable with the same `paths:` field).
