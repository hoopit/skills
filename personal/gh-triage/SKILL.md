---
name: gh-triage
description: Triage the backlog with the user — fill missing fields, collapse the false decisions, grill the real ones, until every item is Unattended.
argument-hint: "[grill] [repo#n] — grill: start at the grill; repo#n: grill this issue first"
disable-model-invocation: true
---

# Triage the backlog, attended

Board: **LKs agent project** — <https://github.com/orgs/hoopit/projects/2>.

`Unattended` is the goal state: the one Autonomy an unattended run can pick up, and what
`start-backlog-daemon` consumes. This run's whole output is triage — fields set, holds
lifted, decisions named — written onto the issues themselves, where the agent that
eventually works them will read it.

Triage starts nothing. The daemon picks from **Ready** alone, and what sits in
**Backlog** is a proposal — filed there because its worth was the judgement — so it
moves only on the user's say-so: `hoopit-board ready <repo> <n>`. Step 4 offers the
list.

Three passes, in order: **fields**, **collapse**, **grill**. Each costs more per item than
the one before it, so an item that settles early never reaches a question.

Every pass writes what it learned onto the issues, so the grill starts from the board
alone. Invoked with `grill`, reach the board and go straight to step 5.

## 1. Reach the board

```bash
hoopit-board open >/dev/null && echo up
```

Unreachable ends the run.

## 2. Fields

```bash
hoopit-board next > /tmp/next.json     # read-only
```

`untriaged` is the list, and it comes first: these items are invisible to every ranking
until they have fields, however small they look.

Read each issue and set all three from the rubrics in `create-gh-issue`:

```bash
hoopit-board triage <repo> <n> --priority P2 --effort M --autonomy Unattended
```

Set them from the issue in front of you — the rubric is written down, so this pass asks
the user nothing. State each value and a one-clause reason, then move on.

**Effort is also the model**, so the rubric prices the hunt along with the fix. This is
the one pass that reads the issue closely enough to see the hunt — price it here.

Autonomy is the axis with no default, and the two non-`Unattended` values owe the body a
section:

- `Needs decision` — a `## The decision` heading naming the question and the shapes it
  could take, so clearing it costs a sentence. Write it now where it is missing; an
  unnamed decision costs a re-read before anyone can answer it, and those pile up under
  `hoopit-board decisions --unnamed`.
- `Out of reach` — what it needs that no checkout reaches. Where part of it *is*
  reachable, file that part as its own `Unattended` issue.

Two more things the body owes whoever starts it, both visible only from here:

- **A backticked path that resolves in the checkout.** Footprints come from those, so an
  issue naming none reads as collision-free, and one whose migration the judgement cannot
  place in an app (`MIGRATION-GRAPH:*`) collides with every migration in flight, in both
  directions, and starves. Name the file, or at least the app.
- **A lead** — a file, a symbol, a log line worth starting from. A lead points; the agent
  draws the conclusion.

`needs_judgement` comes next: candidates whose collision judgement landed between
`COLLIDE_LOW` and `COLLIDE_HIGH`. `next` neither dispatches nor rejects them, so they
recur every tick until settled here. Each entry's `judged` map names what it may collide
with — an open PR, or another claimed issue — and the probability. Read the issue against
that PR or issue and settle it one of two ways:

- **It does not touch the same files.** Name the footprint in the body — backticked paths
  that resolve in the checkout — so the path test decides it from then on.
- **It does.** Hold it behind the PR with `Gate: deployed <repo>#<pr>` in the body, so the
  board hands it back once that PR ships. Where the collision is with another in-flight
  issue rather than a PR, name the footprint instead: the paths then collide exactly and
  `next` blocks it until that claim frees.

Say which, and why, in one clause per item.

Three defects strand an item silently. Fix them while you are in here:

- A rollout follow-up in `held` or `blocked` with no `Gate: deployed #<pr>` line. Add it,
  or the item gets started against an unpromoted prod.
- A gate line naming an unreadable PR — a typo. Fix it against the real PR.
- A `P0` behind a full board. The daemon respects its target, so surface it in the
  report: interrupting flight is the user's call and the only thing here worth it.

`scheduled` and `awaiting_deploy` clear themselves. A `Start date` genuinely ahead is a
gate that still binds; `--not-before none` is for one that has stopped binding.

**Done when** every item that was in `untriaged` carries all three fields, each
`Needs decision` names its decision and each `Out of reach` names what it needs, and every
`needs_judgement` entry has a footprint or a gate in its body.

## 3. Collapse

```bash
hoopit-board decisions 40 --lines 1
hoopit-board decisions --unnamed
```

Walk the whole `Needs decision` pile, highest priority first, and find the ones that need
no decision at all. This is the pass with the most leverage in the run: it takes items off
the user's queue without spending a question, and more of them go than the pile suggests.

Four things retire an item:

- **The premise is answerable and nobody looked.** An issue claiming something "is not
  answerable from the repo" is often wrong about that. Read the code path end to end.
  Production is readable through `readonly-db`, Sentry through `sentry-cli`, the ALB logs
  through `detect-slow-requests` — a decision resting on a measurement is yours to
  measure.
- **The blocker shipped.** An issue written against another issue's *proposed* mechanism
  goes stale when that issue merges something else. Read what landed — `git show <sha>
  --stat`, the PR body — rather than what was proposed.
- **The issue already picks a shape** and only hedges about it: "either would do", "or
  another agreed choice", a `**Fix:**` line that its own acceptance criterion contradicts.
  Decide whether the hedge is a question or an author being polite.
- **The remaining choice is engineering.** `Needs decision` is for product behaviour,
  naming, UX and scope. A choice between two implementations belongs to whoever has the
  code in front of them — it is the work, not a question about the work.

  Retire it by naming a **default and its departure condition**: which shape you would
  take, why, and the finding that should make the agent take the other one instead
  ("dispatch from the bulk path; take the signal-scoped variant only if a caller deletes
  these rows outside it — say which"). A bare pick over-constrains an agent who can see
  more than you can from here; a bare "the agent decides" hands over an item whose first
  act is an unresolved fork. The default plus the condition removes the hold and leaves
  the judgement where it can be exercised.

**Fan the reading out.** Testing the four retirements is code paths, prod and Sentry per
item, and the context that later grills has no use for any of it. Batch the pile by
domain and dispatch one subagent per batch, in parallel, read-only on GitHub and the
repos. Each gets this section as its contract, its issues, and the clues you already hold
— the merged PR an issue follows, the ADR that bears on it. For each issue it writes one
file under a fresh scratchpad directory:

- the verdict, the retirement it rests on, and a one-line reason;
- the exact comment to post — the evidence for a retirement; for a survivor, each
  retirement tested and what ruled it out;
- for a survivor whose body lacks one, the `## The decision` section to add.

It returns one line per issue: `<repo>#<n> RETIRE|SURVIVE <retirement> — <reason>`. The
verdict and the writes stay yours. Post each comment from its file, and open a file only
where the one line leaves you doubting the verdict.

Write the evidence as a comment on the issue, then move the field:

```bash
gh api -X POST repos/<repo>/issues/<n>/comments -F body=@<file>
hoopit-board triage <repo> <n> --autonomy Unattended
```

The comment is the durable half — it stops the next pass re-deriving the same thing, and
it is what lets the user overturn a wrong call in one click.

Retire an item on evidence alone. Descoping, abandoning and closing are *answers* to a
decision, so they belong to the user in the grill.

**A wrong `Unattended` is cheap, and that is why this pass rewards being decisive.** The
daemon's opening prompt tells the agent that on a decision it cannot make it writes the
question onto the issue and calls `hoopit-board release`; `check` reads that **handback**,
so an item that turns out to be undecided returns here with a sharper question than it
left with. The opposite error has no such loop: an item parked on `Needs decision` that
never needed one waits for a human forever. Bias accordingly.

An item that survives all four is a real decision, and it leaves this pass with a
`## The decision` section in its body — the same one the fields pass writes, for the same
reason. Naming it is the precondition for grilling it: the question has to be readable
before it can be asked, and the naming is what survives a round nobody answers. Its
comment carries each retirement tested and what ruled it out, so the grill and the next
run start past them.

A finding of your own that falls out of this pass gets its own issue through
`create-gh-issue`, naming the decision that turned it up.

**Done when** every item in both listings has been tested against all four retirements
with each verdict stated, and every survivor names its decision.

## 4. Report the triage

- Fields filled, with the values.
- Items retired in the collapse — each with the evidence that retired it. This is
  the number that matters: a retired item is a slot an unattended run fills from then on
  with nobody present.
- Defects fixed: gate lines added or corrected, decisions named, paths supplied.
- What is now `Unattended` in Backlog and could be promoted, ranked as `hoopit-board
  slots --unattended` lists Backlog — the user picks which move to Ready; move none on
  your own.
- The `Out of reach` count alone, and that `gh-followup` is what works that bucket.
- Whether anything is draining the queue: `systemctl --user is-active
  start-backlog.service` plus a `start-backlog-daemon` process check. A queue of
  `Unattended` items with nothing consuming it is the one way a clean triage run still
  leaves the backlog stopped. Report the fact; enabling it is the user's call. An active
  daemon can still be dispatching nothing — `journalctl --user -u start-backlog -n 20`
  names the hold, and `aws login session is dead` clears with `aws login --profile
  login-raw`.

Flight counts move while the report is being read, so leave them to the daemon.

This report is the boundary. A collapse that fanned out leaves this context heavy with
reads the grill never uses, and every round would carry them. Ask the user: clear and run
`/gh-triage grill` (recommended), or continue here. A collapse small enough to need no
fan-out continues straight into the grill.

## 5. Grill

What survives is the user's: product behaviour, domain modelling, UX, scope, a trade with
no measurable answer. Work it **one issue at a time**, highest priority first —
`hoopit-board decisions` is already in that order, a `repo#n` argument ahead of it — in
the format
`mattpocock-skills:grilling` defines. Read that skill for the round structure and the
question format; three things are particular to this use:

- **The tree is one issue's.** A round covers that issue's frontier and nothing else, so
  the user answers in the order the questions were asked.
- **Every recommendation carries its argument against.** A recommendation with no
  downside stated is a nudge, and nudging is how a triage run invents a requirement.
- **Fire the `AskUserQuestion` ping** at the end of each round, as the bare ping the
  global `CLAUDE.md` describes. The round lives in the chat text; the ping is what reaches
  a tab nobody is watching.

Facts are yours, decisions are theirs. A frontier question needing a fact from the code,
prod or Sentry is a fact to go and get — dispatch a subagent for a wide read, and let the
rest of the frontier proceed while it runs. A fact that settles the question outright
means the item belonged in the collapse: say so, and retire it there.

An issue's frontier empties, and then:

1. Comment the answers onto the issue — every question, its answer, and the reasoning the
   answer alone does not carry. This is what the eventual agent reads.
2. Fold what changed the issue's shape into the body — a new constraint, a ruled-out
   option — so the body still describes the work.
3. `hoopit-board triage <repo> <n> --autonomy Unattended`.
4. Open the next issue.

**With nobody there to answer**, the ping still goes out and the issue keeps its
`Needs decision` with the round written onto it as a comment. That comment is what
survives the run: the next pass answers it instead of re-deriving it.

## 6. Report the grill

- Decisions the user answered, and which issues reached `Unattended`.
- Issues mid-grill, with the round they wait on.
- The `hoopit-board decisions --unnamed` count: the grill skips those, and the next full
  run names them.
