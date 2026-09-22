---
name: create-gh-issue
description: File a triaged GitHub issue. Use when filing an issue, TODO, follow-up or finding for Hoopit agent work.
---

# Create a GitHub issue

An issue is filed only once it is **triaged**: assigned, typed, prioritised,
costed, and judged startable alone or not. Type says what kind of work it is;
Priority and Effort are what the board sorts on, and Autonomy is what
the backlog daemon filters on — so a blank one hands the triage
straight back to a human. Untriaged is unfinished.

Board: **LKs agent project** — <https://github.com/orgs/hoopit/projects/2>.
**Ready** is the pool `start-backlog-daemon` dispatches from; **Backlog** is where an
item waits for the user to promote it. Whether to file and which status to file into
are two questions, and the two gates below answer them separately; the user's word
beats either.

Priority, Effort, Autonomy and `Start date` are org-wide **issue** fields on
`hoopit`, shared by every repo and every board — the value rides on the issue itself,
so it survives being taken off a board and is there to read from any other one. A pull
request cannot carry them.

## File it, or ask first

Filing to this board is cheap, so the gate is low — a gate for this board and no
other tracker. File what you are **sure** of, and ask about the rest.

- **Sure**: the work follows from something you established — the item the task itself
  needs, a follow-up the shipped change leaves behind, a verification still to run, a
  confirmed bug, a wrong premise measured against prod, a finding that would otherwise
  be lost. "This is broken and nobody has recorded it" files itself.
- **Unsure**: its worth is the judgement rather than its subject — a refactor, a
  cleanup, a nice-to-have, a decision dressed as a task, anything whose scope could be
  a line or a month. "I think this would be good" asks, and torn asks.

Asking is its own question — title and one line per proposed issue, never a bullet
inside a larger summary being confirmed. With nobody there to ask, file it anyway with
Autonomy `Needs decision` and the decision named in the body: dropping it loses the
finding, deciding it invents a requirement.

Report what you filed with its number, so a wrong call is one click from closed.

## Ready, or Backlog

Clearing the filing gate says nothing about status. Ready is not importance and not
confidence in the finding — **Ready means the decision to do this has already been
taken, and only the doing is left**. Where filing the issue *is* the decision, it
belongs in Backlog until the user makes it.

One test: *if I did not file this, would something already agreed-to be left undone?*
No — then Backlog.

- **Ready**: the item the current task needs; work a shipped change is incomplete
  without; a verification that change owes; a defect at `P0` or `P1`; anything the
  user asked for.
- **Backlog**: everything else, a confirmed `P2`/`P3` bug and a finding worth keeping
  included. That a finding would otherwise be lost is a reason to **file** it, never a
  reason to make it Ready — Backlog loses nothing.

A finding a run turns up is almost always Backlog: the run was dispatched to do
something else, and what it noticed on the way is a proposal however certain it is.
`hoopit-board triage` backstops only the floor a machine can read — a `P3` never goes
Ready, and `--ready` on one lands in Backlog with a line saying so. Everything above
`P3` it takes on trust, so the test above is what decides those; `hoopit-board ready`
is the override for when the user has said so.

## 1. Resolve the repo

```bash
gh repo view --json nameWithOwner -q .nameWithOwner
```

The current repo, unless the request names another. With no repo either way,
ask whether it belongs in `hoopit/api`, `hoopit/web-admin` or
`hoopit/flutter-app`.

## 2. Search the board first

An open issue may already cover this, or the finding may belong on a related
issue — as a comment, or folded into its scope.

```bash
hoopit-board open
```

Every open item on the board, one line each — `hoopit-board` is the board's
mechanical half. It lives in this skill, at `scripts/hoopit-board`, symlinked
onto `PATH` from `~/.local/bin`; `gh-triage` and `curate-backlog` call it
too, so edit it here and mind them. The rubrics below are its `PRIORITIES`,
`EFFORTS` and `AUTONOMY` lists — a value added to one belongs in the other, and
a value added to either belongs in the org field as well
(`updateIssueField`, listed by `organization.issueFields`).

Read every plausible match before creating anything — `gh api
repos/<repo>/issues/<n> --jq '{number, title, state, body}'`, which is REST where
`gh issue view` would be GraphQL. The step ends with a covering issue named, or
with none found.

## 3. Write it

- **Title** — imperative, prefixed with the area where the repo uses one:
  `ci: cache CocoaPods between deploys`.
- **Body** — the symptom or the want, why it matters, and one concrete
  acceptance line. Point at the code (`path/to/file.py:120`), the failing run,
  the Sentry issue.
  - An acceptance line that asks for an **absence** — no errors since the rollout,
    no rows left, the alert quiet — has to say what the window must *contain* to
    count, because a zero over a window nothing exercised proves nothing. Name the
    traffic ("at least a day's SMS sends, ~750/day") or name a positive check that
    does not depend on traffic at all (`convalidated = true`, a count over existing
    rows). Otherwise whoever runs it can satisfy the line in ten minutes and learn
    nothing, and the issue closes on an empty window.
  - An acceptance line whose last step happens **after merge** — a script run against
    production, logs read once it ships, a promotion confirmed — makes this two issues,
    not one longer one. The two phases have different gates and different actors, and
    the board cannot represent "merged but not yet done": the PR closes what it
    delivers, so an item held open past its merge freezes at `In progress` with nobody
    on it. File the operational half separately, as a `Follow-up` carrying `Gate:
    deployed` (step 5), and let the first close at its merge.
- **The decision**, where the issue turns on a question only the author can answer —
  product behaviour, naming, UX, scope. Give it a `## The decision` heading of its own
  and state the question and the shapes it could take, so clearing it costs a sentence
  rather than a re-read of the whole issue. Writing it here is what makes step 5's
  Autonomy `Needs decision`; naming it after the issue is filed costs an edit, and the
  edit is what gets skipped.

## 4. File it, assigned and typed

Write the body to a scratchpad file, then:

```bash
gh issue create --repo <repo> --assignee @me --type <Type> \
  --title '<title>' --body-file <path>
```

**Type**

| | |
|---|---|
| `Bug` | An unexpected problem or behaviour. Something is broken. |
| `Feature` | A request, an idea, new functionality. |
| `Task` | Default. A specific piece of work that is neither of the above — a refactor, a chore, a cleanup, a spike. |
| `Follow-up` | Work a **parent** issue is not complete without: logs to read once it ships, a script to run, errors to check, something to monitor. |

A parent to name makes it a `Follow-up` — name it in the body (`follows
hoopit/api#412`). No parent makes it a `Task`.

## 5. Set Priority, Effort and Autonomy

Read all three off the issue's own content and set them — state each value and a
one-clause reason in your reply, then keep going.

```bash
hoopit-board triage <repo> <n> --priority P2 --effort M --autonomy Unattended --ready
```

One call sets every field, and adds the issue to the board first when it is not there.
`--ready` is the Status: on only where the Ready gate above says the decision is
already taken, off otherwise — and a `P3` is refused it whatever is passed. `--not-before YYYY-MM-DD` on the same call sets the fourth field, which most
issues leave empty.

**Priority**

| | |
|---|---|
| `P0` | Broken in production, or blocking work happening right now. Data loss, a failing deploy, users hitting it. |
| `P1` | Real bug with a workaround, or work that unblocks something scheduled. |
| `P2` | Default. Worth doing, no deadline attached. |
| `P3` | Fine if it sits. Polish, speculative cleanup. |

Torn between two levels, take the lower — except a production symptom, which
floors at `P1`.

**Effort**

| | |
|---|---|
| `XS` | Minutes. One line, one config value, a typo. |
| `S` | An hour or two. One file, no design decisions. |
| `M` | Default for a real change. A few files, a test, some thinking. |
| `L` | Multi-day, or cross-cutting enough that the approach needs deciding first. |
| `XL` | Too big for one PR — say so, and offer to split it. |

Price the hunt along with the fix: `DISPATCH_MODEL` in `hoopit-board` maps Effort to the
model and reasoning effort an unattended start gets, so Effort is all that prices the
hunt. A cause nobody has found, an approach still to decide, or a change across
modules, migrations, concurrency or money is `L` even where the eventual diff is small.
Say when you are pricing the hunt, so a cheap-looking `L` reads as deliberate.

**Autonomy** — can an agent take this to a PR ready for review without asking
its author anything? You are the author, and you are answering now, while the
reason is in front of you.

| | |
|---|---|
| `Unattended` | **Decided** and **reachable**: the issue says what to do, and everything it needs is in a repo the agent checks out. |
| `Needs decision` | A question of product behaviour, naming, UX or scope is the author's. An issue too vague to judge lands here. |
| `Out of reach` | It needs something no checkout reaches — a third-party dashboard, a credential the author keeps, an app-store step, a deploy someone triggers, a manual action with no PR behind it. |

**Production is readable**, through the `readonly-db` skill, so an issue that needs
live data to settle is reachable and the measuring is the agent's work. An agent
that finds production unreadable reports that, in place of the answer.

This is the one axis with no default. Torn goes to `Needs decision`: an agent
that answers a product question invents a requirement, and an unattended run
has nobody there to catch it. Fail both tests and either value is right — pick
the one that would have to be cleared first.

`Needs decision` is the value for an issue whose body carries the `## The decision`
section from step 3. One filed without it is a re-read for whoever clears it; they pile
up under `hoopit-board decisions --unnamed`.

**Not before** — a date, and only where the work genuinely cannot begin before one:

```bash
hoopit-board triage <repo> <n> --not-before 2026-10-26   # `none` clears it
```

Set it when a **calendar** event is what the work waits for — a date the code has to
live through (a DST end, a month or year boundary, a scheduled run), a deadline
someone else owns, a window that opens. Say the date in the body with what happens on
it, because the field carries no reason.

Waiting on a person is not a date: that is `Needs decision`. Waiting on a **deploy**
is not a date either — it has a gate of its own.

**Gate: deployed** — one line in the body, for work that cannot start until the code
is live in production:

```
Gate: deployed hoopit/api#17271
```

The number is the **pull request** that ships it (`#17271` alone means this repo; a
squash-commit sha also works). `hoopit-board` resolves it the way `AGENTS.md` says to:
the PR's `merge_commit_sha` — the squash commit on `master`, not the head sha squashing
throws away — then `git merge-base --is-ancestor <sha> origin/production`. Unmerged, or
merged but unpromoted, and the issue stays out of `startable` and out of `check` until
promotion lands. Nothing has to remember it and no date is guessed.

Write the line while filing, off the PR you just merged. The PR number exists before
the sha does, so a follow-up filed mid-review can carry the gate already.

Ancestry flips when the workflow pushes `production`, ahead of the ECS rollout and the
schema it carries — so the agent it releases still confirms the rollout finished, by
polling for the thing itself rather than re-reading ancestry. In `hoopit/api` the
`deploy-status` skill gives the gap and what to poll; a gated issue's acceptance is the
right place to name it. And a repo with no `production` branch
(`hoopit/flutter-app`) has no such test at all: that work is Autonomy `Out of reach`,
not a gate.

`blockedBy` is worth setting only where the blocker is an issue someone will close —
`check` holds on an open one and ignores a closed one.

An item with a future date is held out of `startable` and out of `check`, and ranks
again by itself on the day — nothing has to remember it. A date in the past is
invisible, so a gate that has fallen due costs nothing to leave behind.

## 6. Report

The issue URL, the Type, the Priority, the Effort and the Autonomy — and the date,
where you set one, with what happens on it — so a wrong call is one glance from being
corrected.
