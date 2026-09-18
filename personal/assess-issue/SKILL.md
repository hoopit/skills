---
name: assess-issue
description: Decide whether one issue is worth fixing — price the fix, measure the harm against live data, then close it with the findings or ship it.
argument-hint: "<issue> — a GitHub issue URL, <repo>#<n>, or #<n> in the current repo [--started] [--rounds N]"
disable-model-invocation: true
---

# Assess one issue

One issue in, one of two endings out: **closed**, with the numbers that closed
it, or **shipped** through `hoopit-dev:ship`. Filing on this board is cheap by
design, so some of what sits there asks for a change worth less than it costs.
This is where that gets settled — on measurements, not on how well the issue
reads.

**Ship is the default.** Closing is a claim about the world, and a claim needs
evidence. "Minor" is not evidence; neither is "unlikely", "legacy" or "probably
fine". Most issues here are small, real and cheap, and those ship.

The run ends in one of the two endings or in a question — never in a summary
that leaves the issue exactly as it was found.

Flags:

- `--started` — a caller has already claimed this issue and moved it to **In
  progress** (`start-backlog-daemon` and `gh-triage` both do, before the agent
  they dispatch exists).
  Skips the claim gate in step 1 and the status move in step 6; everything else
  is unchanged. Without it, an issue someone else claimed is not yours.
- `--rounds <N>` — passed through to `ship`.

## 1. Resolve it and gate on it

`#<n>` alone means the repo of the current directory. Read the issue whole,
over REST — `gh issue view` is GraphQL, and the board writes later in this run
have no REST alternative:

```bash
gh api repos/<repo>/issues/<n> --jq '{number, title, state, body, type: .type.name, labels: [.labels[].name]}'
gh api repos/<repo>/issues/<n>/comments --jq '.[] | {user: .user.login, body}'
hoopit-board check <repo> <n>
```

`check` exits non-zero when the issue is closed, blocked, already claimed by
another agent, or already has a PR claiming to close it. A non-zero exit ends
the run: report the reason and change nothing. An issue someone is inside right
now is not yours to close.

Under `--started` the claim is the caller's own, so run `check` for its other
gates and disregard `already started` alone — every other reason still ends the
run, and ending it there means releasing the slot (step 6).

The board's own triage — Priority, Effort, Autonomy — is in `hoopit-board open`.
Read it as the filer's estimate, and expect to correct it: this run is the
first time anyone has measured.

## 2. Test the premise

The cheapest step and the one that most often ends the run. The issue asserts
something about the code; go and read that code. Does the behaviour it
describes exist today, in the branch that runs in production?

A premise written from outside the code is a **guess**, however confident its
wording. Name what would prove it wrong and go look for *that* — an agent that
sets out to confirm a premise confirms it. `git merge-base --is-ancestor <sha>
origin/production` settles "is the fix already out there"; a grep for the
symbol settles "does this path still exist".

Premise false, path gone, already shipped → close (step 5). Otherwise carry on
with what the code actually does, which may be a different issue from the one
filed. Say so if it is.

## 3. Price the fix

Not what it costs to *write* — agent time is not the scarce thing here, and an
hour of it is never the reason to close. What it costs to **land**:

| | |
|---|---|
| **Near zero** | A few lines in code that already has tests. No schema change, no serializer version, no client, no rollout, no coordination. |
| **Expensive** | A migration, a new API version, a client release, a backfill or repair run, a flag with a rollout behind it, a deploy someone has to trigger, a decision someone has to make. |
| **Also expensive** | Standing complexity in a path that is read often, and review attention on a change nobody can verify cheaply. |

**A near-zero fix with a live premise ships unmeasured.** No number can outrun a
cost of nothing, so running them would be spending the expensive thing to save
the cheap one. Skip to step 5. This is the common ending — do not spend an hour
measuring a one-line fix.

## 4. Run the numbers

Only when step 3 found a real cost. Each line below gets a figure and the
source that produced it; a line with an adjective where its figure should be is
not done.

| | |
|---|---|
| **Reach** | How many rows, users, clubs or events does it actually touch? Not how many could in principle. |
| **Rate** | Per day or per week *now*, and which way it is moving. A burst in 2024 and forty a day are different issues. |
| **Consequence** | What one hit costs the person on the other end, said concretely: charged twice, lost the attendance, saw a label read `0 kr`, retried and got through. |
| **Residual** | What happens if nobody ever fixes it — decays, stays flat, or compounds. Whether something already scheduled swallows it. |

Where the figures come from: the `readonly-db` skill for production Postgres
(counts, date ranges, which clubs), the `sentry-cli` skill for event and user
counts with their environment split and first/last seen, `git` for what is
actually promoted. Prefer one counting query over an argument.

**A figure you could not measure is not zero.** Production unreadable, Sentry
silent because nothing logs there, a client-side path with no telemetry — each
is a finding to report, and none of them licenses a close on "no reach". Where
the reach is unmeasurable and the cost is real, that is a question for the
user, not a verdict.

**A zero over a window nothing exercised is not a zero either.** Before believing
"no errors since the rollout" or "quiet for a week", count what the window
*contained*: writes to the table, requests through the route, runs of the task. A
constraint that has enforced for ten minutes against zero writes has not been
tested by them, and neither has a nightly job between two firings. Say the traffic
figure next to the zero, or the reader cannot tell a clean window from an empty one.

Where the window comes back empty, the substitute is not a longer wait — it is
evidence of a different kind: the scan that already ran (`convalidated = true` over
every row), or the write path enumerated down to its callers. Reach for that, and
say which one carried the verdict.

## 5. Decide

Close only on something you can print:

| Bucket | What has to be shown |
|---|---|
| **Premise false** | The code does not do what the issue says it does. |
| **Already handled** | A merged PR covers it, or an open issue does — close `--duplicate-of` that one. |
| **No reach** | The path has not executed in 90 days and nothing schedules it. Measured, not assumed. |
| **Cost outruns the harm** | The fix carries one of step 3's expensive items and the measured harm is cosmetic, or a handful of rows a year, with a residual that does not compound. |

Everything else ships, small and dull included.

Two outcomes are neither, and both end in a question rather than an action:

- **Bigger than one PR.** Set `--effort XL` and say what the split would be. One
  `/ship` run is one PR; forcing this one through produces a branch nobody can
  review.
- **A product, naming or scope question.** Set `--autonomy 'Needs decision'`,
  name the decision in a comment, and ask. Answering it yourself invents a
  requirement.
- **Nothing to measure until a date passes.** Set `--not-before <YYYY-MM-DD>` and
  say in a comment what happens on it, then release the slot.
- **The code is not in production yet.** `git merge-base --is-ancestor <sha>
  origin/production` is the test, and it is the first thing a rollout follow-up runs.
  Unpromoted: add `Gate: deployed <repo>#<pr>` to the body naming the PR that ships it,
  say so in a comment, and release. The board then holds the issue until promotion
  lands and hands it back by itself — no date to guess and no reminder to keep.

  **Promoted is not yet deployed**, and a check run in that gap reads like a failed
  rollout rather than an early one. Ancestry flips when the workflow pushes
  `production`; the schema and the running code follow, and they do not arrive
  together. So poll for the thing itself instead of concluding from ancestry, and
  know what the thing you polled actually proves — a migration applied before the
  service rollout says the schema moved while the old code still serves. In
  `hoopit/api` the **`deploy-status`** skill has the ordering and the figures. Wait it
  out rather than releasing the slot; a pipeline can be slow for an hour without being
  broken, so release on a blocked pipeline, not a clock.

Both write the field and the comment **first**, then ask — under `--started`
the asking may reach nobody, and the board is what survives that.

Where the numbers change the triage without changing the verdict — a P2 that
measures as a P0, an `S` that prices as an `L` — fix the fields with
`hoopit-board triage` on the way past, and say what you moved and why.

## 6. Act

### Closing

The comment is the artifact; the close is the easy half. Write the findings to
a scratchpad file — what was measured, the figure, the source that produced it,
and the one sentence that would reopen this — then:

```bash
gh issue comment <n> --repo <repo> --body-file <path>
gh issue close <n> --repo <repo> --reason 'not planned'
```

`--duplicate-of <m>` instead of `--reason` when another issue covers it.
Closing carries the board item to Done on its own. Reopening costs one click,
and a close written so that reopening is *informed* is the whole point — never
close with a verdict alone.

### Handing the slot back

Either question in step 5, or a `check` gate that stopped a `--started` run,
leaves the issue open and unworked while the board still reads **In progress**
— a slot wedged against every later dispatch, and an item
`curate-backlog` has to guess about. Give it back:

```bash
hoopit-board release <repo> <n> --reason '<the question, in a clause>'
```

The release outranks the claim, so the issue is startable again once its
question is answered. Only reach for this under `--started`; a run you invoked
yourself has you to answer it.

### Shipping

```bash
hoopit-board start <repo> <n>     # not under --started: the caller did it
```

The board is how the user sees what is being worked right now; an issue mid-fix
still reading `Ready` invites a second agent onto it, so this moves first, not
after the fact. Then invoke the **`hoopit-dev:ship`** skill with:

- `TARGET_REPO` — the issue's repo, at `~/Dev/Hoopit/<name>`;
- `WORK_ITEM` — the issue, its URL, tracker GitHub;
- `BRIEF` — what to change and why, carrying **what you found**, not what the
  issue claimed: the true premise from step 2, and any figure from step 4 that
  bounds the fix (a migration's row count, the clubs affected). Where the filed
  premise turned out wrong, the brief says so and the PR body says so.
- any `--rounds` this run was given.

The PR description carries `closes #<n>`, one line per issue. `ship` owns
everything from the branch to the monitored PR — do not duplicate its steps
here.

## 7. Report

The verdict in one line with the figure that decided it, then the measurements
as a table — quantity, value, source — then the link: the closing comment, or
the PR and its watch. A verdict without its numbers underneath is the thing
this skill exists to replace.
