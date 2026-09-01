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

- default — keep working rounds until the PR is merged or closed, or a round leaves
  something only a human can settle.
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

Rounds run only in an existing worktree for the PR branch. Confirm one exists, and stop
here if it does not:

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

Otherwise two outcomes end the watch early — `TaskStop` the monitor and say why:

- The report has an `OPEN THREADS` section: those need a human decision; present them.
- The same check is "still failing" in two consecutive rounds.

Failing those, idle until the next `ROUND`. On `PR_CLOSED`, print a tally — rounds,
threads resolved, checks fixed, conflicts merged — and stop.

Whenever the watch ends — `--single` done, an early stop, or `PR_CLOSED` — drop the label
again, so it only ever marks PRs under an active watch:

```bash
gh pr edit <PR> --repo <OWNER_REPO> --remove-label monitored
```
