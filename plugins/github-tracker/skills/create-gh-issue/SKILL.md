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

Board: the board in your `hoopit-board` config — `hoopit-board config` prints it.
Whether to file is the gate below; which status to file into is step 5, and the two
are separate questions.

Priority, Effort, Autonomy and `Start date` are org-wide **issue** fields on
`hoopit`, shared by every repo and every board — the value rides on the issue itself,
so it survives being taken off a board and is there to read from any other one. A pull
request cannot carry them.

## File it, drop it, or ask

Filing to this board is cheap, so the gate is low — a gate for this board and no
other tracker. Decide each candidate yourself, and ask only the coin-flips.

- **File** what you are fairly sure is worth recording: the work follows from something
  you established — the item the task itself needs, a follow-up the shipped change leaves
  behind, a verification still to run, a confirmed bug, a wrong premise measured against
  prod, a finding that would otherwise be lost. "This is broken and nobody has recorded
  it" files itself. A refactor, a cleanup or a nice-to-have you would argue for files too,
  as a proposal in `Backlog`.
- **Drop** what you are fairly sure is not: the merge or the change already settled it, or
  you would argue against it yourself. Name each drop and its reason in your report.
- **Ask** only a 50/50 — its worth is the judgement itself, and you can argue it either
  way. Asking is its own question — title and one line per proposed issue, never a bullet
  inside a larger summary being confirmed. With nobody there to ask, file it anyway with
  Autonomy `Needs decision` and the decision named in the body.

## 1. Resolve the repo

```bash
gh repo view --json nameWithOwner -q .nameWithOwner
```

The current repo, unless the request names another. With no repo either way,
ask which of the repos in your `hoopit-board` config it belongs to.

## 2. Search the board first

An open issue may already cover this, or the finding may belong on a related
issue — as a comment, or folded into its scope.

```bash
hoopit-board open
```

Every open item on the board, one line each — `hoopit-board` is the board's
mechanical half.

Read every plausible match before creating anything — `gh api
repos/<repo>/issues/<n> --jq '{number, title, state, body}'`, which is REST where
`gh issue view` would be GraphQL. The step ends with a covering issue named, or
with none found — and, where the new issue is a piece of a larger one, with that
parent named too (step 4).

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
  - An acceptance line whose last step needs the code **deployed** — logs read once it
    ships, a promotion confirmed, a script only the deployed app can run, a repair of
    rows a bug fixed in the same PR keeps writing until it ships — makes this
    two issues, not one longer one. The two phases have different gates and different
    actors, and the board cannot represent "merged but not yet done": the PR closes what
    it delivers, so an item held open past its merge freezes at `In progress` with nobody
    on it. File the operational half separately, as a `Follow-up` carrying `Gate:
    deployed` (step 5), and let the first close at its merge.
  - An acceptance line that only needs the Sentry issue to go **quiet** resolves it
    directly, no follow-up: `sentry issue resolve <ID>` once the fix reaches the branch
    the event comes from. A resolved issue reopens itself on the next matching event —
    that regression is the verification a follow-up would otherwise spend a day's
    traffic window to re-derive.
  - A run that only needs the code **reviewed** stays in one issue. Where the repo has
    a script that runs the local checkout against prod (see its `AGENTS.md`), a repair
    command runs from its own branch once the PR is green and ready (`monitor-pr` asks
    for it), and its run log lands in the same PR before merge.
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
| `Follow-up` | **Operational** work an **earlier issue** leaves behind: a verification, logs to read once it is live, a measurement, an existing script or repair command to run. |

Type on the **deliverable**. A diff is a `Bug`, `Feature` or `Task`, whatever it waits
on — a shim to drop, a flag to remove, a migration once the earlier issue merges, a repair
command still to write. An answer or an operational action is a `Follow-up`. The wait
itself rides on a `blockedBy` link to the earlier issue or a `Gate: deployed` line
(step 5), which leaves the type free to say what the work is. An epic is being
decomposed rather than shipped, so its rows are typed on their own merits too. Name the
issue it follows in the body either way (`follows hoopit/api#412`): a cross-reference is
not a type.

**Parent** — attach the issue as a GitHub sub-issue only where the other issue is the
**whole** and this one a **piece** of it: the parent is not done until this is, and
closing every sub-issue finishes it. That fits an `XL` split into PR-sized issues, an epic's
rows, and one change carried across repos (the api, web-admin and app halves under one
umbrella — a sub-issue may live in another repo of the org).

Everything else stays a link, because a parent claims scope:

| Relation | Link |
|---|---|
| Must wait for another to close | `blockedBy` (step 5) |
| Must wait for a deploy | `Gate: deployed` (step 5) |
| Left behind by an issue that closes at its merge | `follows <repo>#<n>` in the body — that issue's scope ended at its merge |
| Turned up by a run dispatched for something else | `found while working on <repo>#<n>` in the body — a finding is outside the run's scope |
| Same area, similar symptom | a cross-reference in the body |

A follow-up and its origin can still share a parent, where both are pieces of one larger
whole. An issue has at most one parent; read it first, and leave one already set unless it
is plainly wrong:

```bash
gh api repos/<repo>/issues/<n> --jq '.parent_issue_url'
gh api -X POST repos/<parent-repo>/issues/<parent>/sub_issues \
  -F sub_issue_id="$(gh api repos/<repo>/issues/<n> --jq .id)"
```

`sub_issue_id` is the issue's REST `id`, not its number. GitHub shows the parent on the
issue, so the body does not repeat it. The PR that delivers a piece says `closes` the
piece, never the parent, and the parent closes with its last piece.

## 5. Set Priority, Effort and Autonomy

Read all three off the issue's own content and set them — state each value and a
one-clause reason in your reply, then keep going.

```bash
hoopit-board triage <repo> <n> --priority P2 --effort M --autonomy Unattended --ready
```

One call sets every field, and adds the issue to the board first when it is not there.
`--not-before YYYY-MM-DD` on the same call sets the fourth field, which most issues
leave empty.

**Priority**

| | |
|---|---|
| `P0` | Broken in production, or blocking work happening right now. Data loss, a failing deploy, users hitting it. |
| `P1` | Real bug with a workaround, or work that unblocks something scheduled. |
| `P2` | Default. Worth doing, no deadline attached. |
| `P3` | Fine if it sits. Polish, speculative cleanup. |

Torn between two levels, take the lower — except a production symptom, which
floors at `P1`.

**Status** — `--ready` puts the issue in the pool the backlog daemon, where one runs,
dispatches from, and that pool is for work already **committed** to: the decision is
taken and only the doing is left. Where filing the issue *is* the decision, it is a
**proposal**, and it waits in Backlog for the user to promote it.

The test: *if I did not file this, would something already agreed-to be left undone?*
No — then Backlog.

| | |
|---|---|
| `Ready` | Committed: the item this task needs, work a shipped change is incomplete without, a verification it owes, a `P0` or `P1` defect, anything the user asked for. |
| `Backlog` | Default. Everything else — a `P2` or `P3` bug, a cleanup, a finding worth keeping. |

A finding a run turns up is a proposal however certain you are of it: the run was
dispatched to do something else. That it would otherwise be lost is what makes it worth
**filing**, never what makes it Ready — Backlog loses nothing. A `P3` is refused
`--ready` outright; `hoopit-board ready` is the override.

**Effort**

| | |
|---|---|
| `XS` | Minutes. One line, one config value, a typo. |
| `S` | An hour or two. One file, no design decisions. |
| `M` | Default for a real change. A few files, a test, some thinking. |
| `L` | Multi-day, or cross-cutting enough that the approach needs deciding first. |
| `XL` | Too big for one PR — say so, and offer to split it into sub-issues (step 4). |

Price the hunt along with the fix: where a backlog daemon runs with a dispatch ladder
configured, the `dispatch-ladder` skill maps Effort to the model and reasoning effort
an unattended start gets, so Effort also picks the model there — but the rubric prices
the hunt along with the fix either way, and this is the one pass that reads the issue
closely enough to see it. A cause nobody has found, an approach still to decide, or a
change across modules, migrations, concurrency or money is `L` even where the eventual
diff is small. Say when you are pricing the hunt, so a cheap-looking `L` reads as
deliberate.

**Autonomy** — can an agent take this to a PR ready for review without asking
its author anything? You are the author, and you are answering now, while the
reason is in front of you.

| | |
|---|---|
| `Unattended` | **Decided** and **reachable**: the issue says what to do, and everything it needs is in a repo the agent checks out. |
| `Needs decision` | A question of product behaviour, naming, UX or scope is the author's. An issue too vague to judge lands here. |
| `Out of reach` | It needs something no checkout reaches — a third-party dashboard, a credential the author keeps, an app-store step, a deploy someone triggers, a manual action with no PR behind it. |

A command to write and run is judged on the writing: its PR asks for the run before it
merges (step 3), so the run has a PR behind it and the issue can be `Unattended`.

**Production is readable**, through the repo's production-read skill where it has one
(see its `AGENTS.md`), so an issue that needs live data to settle is reachable and the
measuring is the agent's work. An agent that finds production unreadable reports that,
in place of the answer.

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
Gate: deployed <repo>#<pr>
```

The number is the **pull request** that ships it (`#<pr>` alone means this repo; a
squash-commit sha also works). `hoopit-board` resolves it against the repo's configured
production branch (`hoopit-board config` names it): the PR's `merge_commit_sha` — the
squash commit on the default branch, not the head sha squashing throws away — then
`git merge-base --is-ancestor <sha> origin/<production-branch>` after a fetch. Unmerged, or merged but
unpromoted, and the issue stays out of `startable` and out of `check` until promotion
lands. Nothing has to remember it and no date is guessed.

A gate is read wherever it stands on a line, and every one in the body must be live. One
that names no pull request or sha, such as a placeholder, holds the issue. To mention a
gate in prose without setting one, put it in backticks: `hoopit-board` does not read those.

Write the line while filing, off the PR you just merged. The PR number exists before
the sha does, so a follow-up filed mid-review can carry the gate already.

Ancestry flips when the workflow pushes the production branch, ahead of any rollout and
the schema it carries — so the agent it releases still confirms the rollout finished, by
polling for the thing itself rather than re-reading ancestry. Where the repo has a skill
for the rollout's ordering and figures (see its `AGENTS.md`), that's the one to poll
with; a gated issue's acceptance is the right place to name it. And a repo configured
with no production branch has no such test at all: that work is Autonomy `Out of reach`,
not a gate.

`blockedBy` is worth setting only where the blocker is an issue someone will close —
`check` holds on an open one and ignores a closed one.

An item with a future date is held out of `startable` and out of `check`, and ranks
again by itself on the day — nothing has to remember it. A date in the past is
invisible, so a gate that has fallen due costs nothing to leave behind.

## 6. Report

The issue URL, the Type, the Priority, the Effort, the Autonomy and the Status — the
parent, where you attached one, and the date, where you set one, with what happens on it — so a wrong call is one glance
from being corrected.

## Maintaining `hoopit-board`

The script is the plugin's `bin/hoopit-board`, on `PATH` as a bare command, with its
tests in the plugin's `tests/`; every skill in the plugin calls it, so edit it there and
mind them. The rubrics above are
its `PRIORITIES`, `EFFORTS` and `AUTONOMY` lists — a value added to one belongs in the
other, and a value added to either belongs in the org field as well (`updateIssueField`,
listed by `organization.issueFields`).
