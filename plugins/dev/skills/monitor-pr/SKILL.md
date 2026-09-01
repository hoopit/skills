---
name: monitor-pr
description: Watch a single pull request and work each review round — merge conflicts, unresolved review threads, failing checks — one push per round, until it is merged. Use only when explicitly asked to monitor a PR.
argument-hint: "<PR url or number> [--single] [--subagent[=<model>]]"
---

# Monitor PR

A **round** is one batch of work on a PR: it opens once `CodeRabbit` and `codex-review`
have both reported on the current head, and covers every unresolved thread, failing
check and merge conflict the PR has at that point, ending in exactly one push.

Flags:

- default — keep working rounds until the PR is merged or closed. A decision only a
  human can settle becomes a question (Step 5); the watch keeps running while it waits.
- `--single` — wait for one round, work it, report, done.
- `--subagent[=<model>]` — run rounds in a `hoopit-dev:monitor-pr-worker` instead of yourself,
  reusing it across rounds until it nears its context limit, then rotating to a fresh
  one. The model defaults to `opus`; `--subagent=fable` (or `sonnet`, `haiku`) overrides
  it. A Sonnet session driving the workers is a cheap long-lived watch.

## Step 1 — Resolve the target

Take the PR from the arguments. With none there, read this session's name — `ListAgents`
prints `This session is <name>`, and a name like `pr16619` carries the number. Ask only
when neither yields one.

Set `OWNER_REPO` (from the URL, else `gh repo view --json nameWithOwner --jq
.nameWithOwner`) and `PR`; set `REPO_ROOT=$(git rev-parse --show-toplevel)` and
`SKILL_DIR` to this skill's base directory. Echo the URL once so the footer PR badge
renders and the user sees which PR you resolved:

```bash
gh pr view <PR> --repo <OWNER_REPO> --json url --jq .url
```

Rounds run only in an existing worktree for the PR branch. Confirm one exists; if it
does not, the watch cannot arm — say so through `AskUserQuestion` (Step 5) rather than
just printing it:

```bash
BRANCH=$(gh pr view <PR> --repo <OWNER_REPO> --json headRefName --jq .headRefName)
git worktree list --porcelain | grep -B2 "refs/heads/$BRANCH"
```

## Step 2 — Arm the watch

Label the PR `monitored`, so a glance at GitHub shows which PRs have a watch running.
The label exists in `hoopit/api`, `hoopit/web-admin` and `hoopit/flutter-app`; in any
other repo create it first with `gh label create monitored --repo <OWNER_REPO> --color
1D76DB --description "Claude's monitor-pr skill is watching this PR"`. A failure here is
never fatal — note it and arm the watch anyway.

```bash
gh pr edit <PR> --repo <OWNER_REPO> --add-label monitored
```

```
Monitor(
  command: "ONCE=<1 with --single, else 0> bash <SKILL_DIR>/scripts/watch-pr.sh <OWNER_REPO> <PR> 60",
  description: "monitor-pr #<PR>",
  persistent: true,
)
```

The script polls every 60 s and prints only:

- `ROUND head=… unresolved=N new_threads=K failing=<names> conflicting=0|1` — both
  reviewer statuses are present and non-pending on the current head, and there is work
  the previous round did not see: a new or newly-replied-to unresolved thread, a red
  check, or a conflict. Other CI may still be running; the round re-queries checks.
  With `ONCE=1` the script exits after this line.
- `PR_CLOSED state=MERGED|CLOSED` — the script exits.
- `WATCH_ERROR fetch_failures=N last=…` — GitHub could not be reached five polls in a
  row (expired auth, network, deleted PR); the script exits non-zero. The watch is dead:
  go to Step 5.

For a repo whose reviewer statuses have other names, prefix `GATE_CHECKS=<a>,<b>`.

Tell the user in one line that the watch is armed and what opens a round.

## Step 3 — Work each `ROUND`

The round briefing is the `hoopit-dev:monitor-pr-worker` agent definition, which ships
in this plugin at `<SKILL_DIR>/../../agents/monitor-pr-worker.md`.

Default: read it and follow its body yourself, with the inputs below, ending with its
report.

`--subagent`: rounds go to a named worker that is reused while it stays under 100k
tokens. First round (and first round after each rotation):

```
Agent(
  subagent_type: "hoopit-dev:monitor-pr-worker",
  model: "<--subagent's model, else opus>",
  name: "pr-<PR>-worker",
  description: "round PR #<PR>",
  prompt: "PR_URL=<PR_URL> OWNER_REPO=<OWNER_REPO> PR=<PR> REPO_ROOT=<REPO_ROOT>\nROUND: <the ROUND line verbatim>",
)
```

Each completion notification reports `subagent_tokens`; keep a running total per worker.
Next round while the total is under 100k:

```
SendMessage(to: "pr-<PR>-worker", message: "ROUND: <the ROUND line verbatim>")
```

At 100k or above, rotate: spawn a fresh worker with the full prompt (use a new name,
e.g. `pr-<PR>-worker-2`) and start its total at zero.

One round at a time: a `ROUND` that lands mid-round is worked after the current one.

## Step 4 — Report

Print the round's report under a `Round N — <trigger>` heading. With `--single`, that is
the end.

A `QUESTIONS` section is a fork, not an ending: the watch stays armed and the questions
go to the user in Step 5. One outcome ends the watch on its own — the same check "still
failing" in two consecutive rounds; `TaskStop` the monitor, then ask.

Failing that, idle until the next `ROUND`.

On `PR_CLOSED state=MERGED`, print a tally — rounds, threads resolved, checks fixed,
conflicts merged — and stop. Two things outlive the PR and are carried into that tally:
commits the worktree holds and the remote does not (push them, saying plainly that this
opens a follow-up PR against the default branch), and any question still unanswered
(restate it as an open item).

Whenever the watch ends — `--single` done, an early stop, or `PR_CLOSED` — drop the label
again, so it only ever marks PRs under an active watch:

```bash
gh pr edit <PR> --repo <OWNER_REPO> --remove-label monitored
```

## Step 5 — Ask in rounds

Every question this skill puts to the user goes through here, in the format
`mattpocock-skills:grilling` defines — invoke that skill when it is installed. Number
each question and give each one your recommended answer:

```
❓ **Q1** - **<title>**: <body; name each alternative>

➡️ <your recommended answer>
```

Facts are yours to find, decisions are the user's: anything answerable from the PR, the
logs, the diff or the code you look up yourself, so what reaches the user is only what
they alone can settle.

Two paths reach the user, and they differ in timing and in what they offer.

**A fork** — a decision the round turned up. Collect every fork the round produced, let
the round finish its push (settled work ships while the question waits), then ask them
as one round of questions. The watch stays armed meanwhile and the answer ships in the
next round's push. A question left unanswered rejoins the next round's question set, so
it stays in front of the user.

**A stop** — the watch itself has ended. Ask immediately, on its own, once the label is
dropped. A stop covers: no worktree for the branch (Step 1), `WATCH_ERROR`, `PR_CLOSED
state=CLOSED`, the same check failing two rounds running, the `Monitor` task exiting or
being killed, and any round that errors out beyond working around (auth expired,
worktree gone, push rejected, the worker dying twice). A watch always ends in front of
the user: the question is the last thing the turn does, and it names the real reason.

The chat round carries the substance; `AskUserQuestion` carries the attention. Fire it
once per round of questions, headed `Monitoring`, its text naming the PR and how many
questions wait above it — `PR #16619 — 3 questions from round 4`. Each path has its own
options, because they answer different things:

| Path | Options |
| --- | --- |
| Fork | **Answer in chat** (recommended) · **Take all your recommendations** · **Stop monitoring, I'll take it from here** |
| Stop | **Re-arm the watch** (a transient stop — go back to Step 2, label included) · **Stop, I'll take it** · **Keep going anyway** (re-arm past a check failing for reasons outside this PR) |

Print the blocker's details — the open threads, the failing check's log excerpt — before
asking, so the answer is an informed one, and act on it immediately.

Under `--subagent` the worker reports forks and the session asks them: a question from a
background agent reaches nobody.

### Write down what an answer settles

An answer that settles a term or a decision gets captured while it is fresh: invoke
`mattpocock-skills:domain-modeling` and follow it — resolved terms into `CONTEXT.md` as
they resolve, an ADR under `docs/adr/` when the decision is hard to reverse, surprising
without context, and the result of a real trade-off. Create either file when the repo
has none.

Write and commit in the session, in the PR's worktree; the next round's push carries the
commit, which puts the ADR under review alongside the rest of the PR.
