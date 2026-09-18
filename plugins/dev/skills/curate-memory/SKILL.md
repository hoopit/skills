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

## Workflow

### 1. Measure
Run the ledger, then read `MEMORY.md`:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/curate-memory/scripts/memory-ledger.py" <memory-dir>
```

It prints, per memory: days idle, days old, how many sessions touched it, type,
created and last-touched dates. **Idle days are a floor** — only this project's
transcripts are scanned.

The index one-liners plus the ledger triage most memories. Read full files only for
the ones you will graduate (to write good prose) or whose status you must verify.

### 2. Discover the destinations
Read [`destinations.md`](destinations.md) — the homes knowledge can take, the
boundaries between them, and the format each one wants. It settles the destinations
in step 4 and the write-up in step 6.

- List what this repo already has: root `AGENTS.md`/`CLAUDE.md`, every module-level
  one (`find . -name 'AGENTS.md' -o -name 'CLAUDE.md'`), `.claude/rules/`,
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
the plan. `AskUserQuestion` with a question per axis works well. Pure "this shipped,
remove it" is within a "prune my memory" request; borderline calls should be
surfaced, not assumed.

### 6. Execute — back up, graduate, expire
- **Back up first.** `cp MEMORY.md MEMORY.md.bak`, and expire a memory by
  `mv <name>.md <name>.md.bak` — never `rm`. `.bak` sits outside the `*.md` glob, so
  backups stay clear of the index, of recall and of step 7's checks, and every
  expired memory is recoverable verbatim until step 9.
- **Graduate before expiring**, so you always write from the source text. Condense
  into the destination's voice — generic per the bars above, in the format
  `destinations.md` gives it.
- Writing to the global `CLAUDE.md`? Back it up the same way first (`cp CLAUDE.md
  CLAUDE.md.bak`).
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
Graduated knowledge enters shared docs through **review**. Finish the curation by
opening the PR.

- Resolve the repo's default branch: `DEFAULT_BRANCH` from the repo CLAUDE.md
  **Workflow skills config** block if present, else
  `git symbolic-ref refs/remotes/origin/HEAD`.
- Create a branch off it, e.g. `chore/curate-memory-<yyyy-mm-dd>`.
- Check `git status` and `git add` explicit paths — only the files you changed, so
  work in progress from the user, or from another agent sharing the checkout, stays
  out of the commit.
- One focused commit per logical move reads best (e.g. "document the payments lock
  order in the module's AGENTS.md").
- Push and open the PR following the **`create-pull-request`** skill's recipe, without
  `--draft`: no watch follows a curation, so nothing would mark a draft ready.
  There's usually no tracked work item — say so in the body. Structure the body by
  destination: what graduated where, and (for reviewer context) what expired, what
  stayed in memory, and what went to the global `CLAUDE.md` outside this repo.
  Report the PR URL when done.

### 9. After the PR merges — drop the backups
`rm <memory-dir>/*.md.bak`, and the global `CLAUDE.md.bak` if you wrote one. Until
then the backups stay: they are the only copy of every expired memory, and a
graduation that review sends back needs its source text. If the session ends before
the merge, leave them — step 2 of the next curation clears them.
