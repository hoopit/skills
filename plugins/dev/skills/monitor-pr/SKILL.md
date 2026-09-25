---
name: monitor-pr
description: Monitor a single pull request. Use only when explicitly asked to monitor a PR.
argument-hint: "<PR url or number> [--subagent[=<model>]] [--unattended]"
---

# Monitor PR

A **round** is one batch of work on a PR. It opens on the **first** feedback of any kind
— a new review thread, a failing check, a merge conflict — and before its single push
takes a **last look** for feedback that landed while it worked, so work starts the minute
there is any and the push still carries the whole review.

## When the watch stops

The watch runs to the merge. Three things end it early, each in front of the user (Step 5):

- **a close holding a verdict** — a closing round that reports `verdict held` (*Closing
  the rounds* in [LEDGER.md](LEDGER.md)), whose head stays red and so never goes `GREEN`;
- **a hard fork**, below;
- **a checkpoint that stops** — every 5 rounds, the agent weighs whether the rounds are
  converging, and carries on unless it doubts they are (Step 4).

Any other **closing round** — every item declined, nothing committed — ends the rounds,
not the watch. The monitor stays armed, and the head's `GREEN` runs the merge-readiness
challenge and writes the merge briefing as any `GREEN` does, whether its checks had
settled at the close or settle after it. A new thread or a red check opens a round again.

A `GREEN` line ends nothing either: it puts the merge decision to the user and the watch
keeps running, because a PR can go green and then move again.

**Short of a stop, the watch runs until the head is `GREEN`**: the merge-readiness
challenge run, the merge briefing written into the PR description, the PR marked ready,
and the merge question asked with the briefing ([GREEN.md](GREEN.md)). A stop — the three
endings above, a *Stop, I'll take it* answer, or a stop in Step 5 — ends the watch at
once, with no challenge or briefing after it.

The hard fork is the whole test for whether a question stops the watch. A **hard fork**
is a question whose answer could invalidate work already done or reviews already run: the
head is not worth reviewing, and rounds past it burn reviewer attention on work that may
not survive. Every other question is a **soft fork**: the round ships its settled work,
the answer lands in the next round's push, and the watch never pauses for it. An open
thread is soft by default; grade it hard only when its answer reaches the work itself.

Flags:

- `--subagent[=<model>]` — run rounds in a `hoopit-dev:monitor-pr-worker` instead of yourself,
  reused across rounds and rotated as [SUBAGENT.md](SUBAGENT.md) says. The model defaults
  to `opus`: the worker carries the labour and the probing, and the design judgement stays
  with this session.
- `--unattended` — nobody is watching the session, so it **acts, then asks** (Step 5).

## Step 1 — Resolve the target

Take the PR from the arguments. With none there, read this session's name — `ListAgents`
prints `This session is <name>`, and a name like `pr16619` carries the number. Ask only
when neither yields one.

Set `OWNER_REPO` (from the URL, else `gh api 'repos/{owner}/{repo}' --jq .full_name`) and `PR`; set `REPO_ROOT=$(git rev-parse --show-toplevel)` and
`SKILL_DIR` to this skill's base directory. `GATE_SCRIPT` is review-gate's
external-reviewer script, resolved here because only this body has the token substituted:
`${CLAUDE_PLUGIN_ROOT}/skills/review-gate/scripts/run_external_reviewers.sh`.

Rounds run in a worktree for the PR branch, which the round creates when none exists. A
**back-merge** PR — its head *is* the default branch, so working it would push there —
cannot be watched: say so through `AskUserQuestion` (Step 5) rather than just printing it.

One REST read answers all of it, and the echoed URL renders Claude Code's footer PR badge:

```bash
read -r URL BRANCH DEFAULT_BRANCH < <(gh api repos/<OWNER_REPO>/pulls/<PR> \
  --jq '[.html_url, .head.ref, .base.repo.default_branch] | @tsv')
echo "$URL"
[[ "$BRANCH" == "$DEFAULT_BRANCH" ]] && echo "BACK_MERGE — do not arm"
```

## Step 2 — Arm the watch

Label the PR `monitored`, so a glance at GitHub shows which PRs have a watch running.
Where the repo lacks the label, create it first with `gh label create monitored --repo
<OWNER_REPO> --color 1D76DB --description "Claude's monitor-pr skill is watching this
PR"`. A failure here is never fatal — note it and arm the watch anyway.

```bash
bash <SKILL_DIR>/scripts/pr-labels.sh <OWNER_REPO> <PR> +monitored
```

```
Monitor(
  command: "bash <SKILL_DIR>/scripts/watch-pr.sh <OWNER_REPO> <PR> 60",
  description: "monitor-pr #<PR>",
  persistent: true,
)
```

The script polls every 60 s and prints only:

- `ROUND head=… unresolved=N new_threads=K failing=<names> conflicting=0|1
  [pending_gates=<names>]` — there is work the previous round did not see: a new or
  newly-replied-to unresolved thread, a red check, or a conflict. The round fires on it
  immediately; `pending_gates` names the reviewers yet to report on this head, and what
  they post while the round runs is what its last look collects.
- `GREEN head=… [pending_gates=<names>]` — this head has nothing left:
  no unresolved thread, no failing check, none still running, no conflict. Fired once per
  head; the merge decision goes to the user (Step 5). `pending_gates` here means a
  reviewer never reported at all and `GATE_TIMEOUT` (default 900s) elapsed waiting.
- `PR_CLOSED state=MERGED|CLOSED` — the script exits.
- `WATCH_ERROR fetch_failures=N last=…` — GitHub could not be reached five polls in a
  row (expired auth, network, deleted PR); the script exits non-zero. The watch is dead:
  go to Step 5.

The script runs on until the session `TaskStop`s it when the watch ends.

The gate is `codex-review` alone. CodeRabbit holds a head the way any check does — while
its status is pending, or a thread of its is unresolved — and its silence holds nothing: a
rate-limited CodeRabbit never reports. For a repo whose reviewer statuses have other
names, prefix `GATE_CHECKS=<a>,<b>`. Tune the timeout with `GATE_TIMEOUT=<seconds>`.

Tell the user in one line that the watch is armed and what opens a round.

## Step 3 — Work each `ROUND`

The round briefing is the `hoopit-dev:monitor-pr-worker` agent definition, which ships
in this plugin at `<SKILL_DIR>/../../agents/monitor-pr-worker.md`.

Default: read it and follow its body yourself, ending with its report, with the paths
Step 1 resolved — `GATE_SCRIPT` in particular, since the ledger's challenge is written
against it and a round cannot decline a Critical/High without one. The step back is yours
to run, and the answer is the one you record.

`--subagent`: read [SUBAGENT.md](SUBAGENT.md) before the first round and follow it — the
worker's prompt, its reuse and rotation, and answering its `DESIGN CHECK`.

One round at a time: a `ROUND` that lands mid-round is worked after the current one — and
often finds nothing, because the running round's last look already absorbed it. Its report
says so on the `Absorbed` line.

## Step 4 — Report

Print the round's report under a `Round N — <trigger>` heading. It is the round's
**delta** — what this round did; the **ledger** the round wrote into the PR description
holds the PR's cumulative state, so the two never need to say the same thing twice. Link
the PR once beneath the heading so the ledger is one click away. A round that reports `Ledger:
not updated` says so too, with the reason — the ledger is then behind by a round.

A round that found nothing to do — the previous round's last look had taken it — is
reported in one line and does not count as a round.

Two things come before grading. A report or design check whose first line is `CODEX
DOWN` is relayed the moment it lands: print the line, then `PushNotification` with it;
the round runs on without Codex. Then read the ledger the round wrote and check convergence yourself: a
row tagged `fixes R<k>` on a mechanism another row already fixes, with no step back
recorded, is a patch to a patch — the next round's `GUIDANCE` demands the step back on
it.

Then grade the round's `QUESTIONS`. **Soft** forks go to the user in Step 5, and the next
`ROUND` is worked whether or not they have been answered. A **hard** fork ends the watch — `TaskStop` the
monitor, then ask — as does the same check "still failing" in two consecutive rounds,
unless that check is a **verdict** (*Closing the rounds* in [LEDGER.md](LEDGER.md)), which
the rounds carry themselves.

**The checkpoint.** At every 5th counted round, weigh whether more rounds will bring the
head to `GREEN`. Read it off the ledger: its convergence counts —
findings in code a round added, design reversals — the `fixes R<k>` chains, and the
severity of what the reviewers still find.

- **Converging** — the reviewers have moved to polish, and no chain is growing: carry on
  without asking. The round's report says so in one line, with the counts it turned on.
- **Churning, or in doubt** — the rounds keep finding defects in their own fixes, or
  reopen a mechanism a step back already replaced, or the counts do not settle which it
  is: stop. A real doubt is the user's to settle.

A report reading `CLOSED verdict held: …`, or a checkpoint that stops, `TaskStop`s the
monitor and takes its path in Step 5. Otherwise idle until the next `ROUND` or `GREEN` —
after a plain `CLOSED` and after `APPEALED` too: the head answers as a `GREEN` or as the
next `ROUND`.

Whenever the watch ends — a close holding a verdict, a checkpoint, a hard fork, an error stop,
or `PR_CLOSED` — drop the label again, so it only ever marks PRs under an active watch, and
`agent-working` with it: a PR waiting on the user is not being worked.

**A PR is a draft exactly while an agent owns its review rounds.** So an ending that hands
the PR to the user with the rounds over — a close holding a verdict, a checkpoint, or any *Stop,
I'll take it* answer — marks it ready, or it stays unmergeable with its issue parked in `AI
review` and no event left to move it. A hard fork and an error stop leave it a draft on
purpose: that work is unfinished, and re-arming the watch picks it up where it stands.

```bash
bash <SKILL_DIR>/scripts/pr-labels.sh <OWNER_REPO> <PR> -monitored -agent-working
gh pr ready <PR> --repo <OWNER_REPO>   # verdict-held close, checkpoint, or "Stop, I'll take it" only
```

## Step 4a — Land the merge

On `PR_CLOSED state=MERGED`, or a merge no monitor was left to report — the Green path's
own, or one the user wakes an unattended session for — read [LANDING.md](LANDING.md) and follow it: the tally, what is left open,
then the clean-up, last.

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

Until the PR is marked ready, ask only what the PR itself needs. A question that does not
reach its code — a follow-up to file, a finding outside its scope — is settled without
asking, filed where `create-gh-issue` says it should be, or held for the `GREEN` merge
question.

Five paths reach the user. The first two leave the watch running.

**A soft fork.** Collect every soft fork the round produced, let the round finish its
push, then ask them as one round of questions. A question left unanswered
rejoins the next round's question set, so it stays in front of the user. An answer settles
a ledger row: pass it into the next round so the row becomes `answered: <the choice>`,
which is how the PR shows the decision to a reviewer who was never asked.

**A hard fork.** Stop the watch, then ask it alongside the round's soft forks. An answer re-arms the watch (back to Step 2); the
next round carries all the answers.

**Green** — a `GREEN` line. Read [GREEN.md](GREEN.md) and follow it: the merge-readiness
challenge, the merge briefing written into the PR description, then the merge question.
A `GREEN` after a closing round also lists that round's declines — each thread, and `not
worth a round` with its evidence where that was the reason — so the user can take any of
them back; a decline taken back rides into the next round as `ANSWERED`.

**Closed or checkpointed** — a close holding a verdict, or a checkpoint that stopped.
Stop, then ask whether to keep watching. The close's question lists its declines as a
`GREEN` after a close does; a checkpoint's says what is still outstanding and the counts
that made you doubt the rounds were converging. A close holding a verdict leads with the verdict: the appeal is spent,
so what is left is taking a decline back or the bypass the repo documents, and bypassing
a check is the user's call, `--unattended` included. *Keep watching* re-arms the watch (back to Step 2, label included), and a
decline the user takes back rides into its next round as `ANSWERED`.

**A stop** — the watch ended on something going wrong. Ask immediately, on its own, once
the label is dropped. A stop covers: a back-merge head (Step 1), a PR branch the round
could not put in a worktree, `WATCH_ERROR`, `PR_CLOSED state=CLOSED`, the same check failing two rounds running, the `Monitor` task
exiting or being killed, and any round that errors out beyond working around (auth
expired, worktree gone, push rejected, the worker dying twice). The question names the real reason.

The chat round carries the substance; `AskUserQuestion` carries the attention. Fire it
once per round of questions, headed `Monitoring`, its text naming the PR and how many
questions wait above it — `PR #16619 — 3 questions from round 4`. Each path has its own
options, because they answer different things:

| Path | Options |
| --- | --- |
| Soft fork | **Answer in chat** (recommended) · **Take all your recommendations** · **Stop monitoring, I'll take it from here** |
| Hard fork | **Answer in chat** (recommended) · **Take all your recommendations** · **Stop monitoring, I'll take it from here** — the first two re-arm the watch |
| Green | **Merge it** · **Not yet — keep watching** · **Stop monitoring, I'll take it from here** |
| Closed or checkpointed | **Keep watching** · **Stop, I'll take it** · **Answer in chat** (when questions are outstanding) |
| Stop | **Re-arm the watch** (a transient stop — go back to Step 2, label included) · **Stop, I'll take it** · **Keep going anyway** (re-arm past a check failing for reasons outside this PR) |

Print the blocker's details — the open threads, the failing check's log excerpt — before
asking, so the answer is an informed one, and act on it immediately. An ending's turn
ends on the `AskUserQuestion`, never on prose: a watch that goes dark without one is a
watch the user restarts by hand, with its answers lost.

Every such turn's chat text, and every stop's, carries the full link alongside the rest:
`$URL` from Step 1, or the issue it closes if the PR does not exist yet.

Under `--subagent` the worker reports forks and the session asks them: a question from a
background agent reaches nobody.

### Unattended

Under `--unattended`, read [UNATTENDED.md](UNATTENDED.md) before the first question: it
decides which of the paths above still ask.
