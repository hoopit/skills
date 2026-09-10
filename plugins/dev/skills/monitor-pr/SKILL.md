---
name: monitor-pr
description: Watch a single pull request and work each review round — merge conflicts, unresolved review threads, failing checks — one push per round, on a round budget, until it is merged. Use only when explicitly asked to monitor a PR.
argument-hint: "<PR url or number> [--rounds <N>] [--subagent[=<model>]]"
---

# Monitor PR

A **round** is one batch of work on a PR. It opens on the **first** feedback of any kind
— a new review thread, a failing check, a merge conflict — and covers everything the PR
has accumulated by the time it ends: before its single push the round takes a **last
look** for feedback that landed while it worked, and folds that in too. Opening early and
closing late is the trade: work starts the minute there is any, and the push still
carries the whole review.

## When the watch stops

The watch runs to the merge. Two things end it early, and each ends in front of the user
(Step 5):

- **the round budget is spent** — `--rounds` rounds have been worked;
- **a hard fork** — a question whose answer could invalidate work already done or
  reviews already run.

A `GREEN` line is not one of them: it puts the merge decision to the user and the watch
keeps running, because a PR can go green and then move again.

That second one is the whole test for whether a question stops the watch. A **hard fork**
makes the current head not worth reviewing — the answer may throw the approach away — so
spending rounds past it burns reviewer attention on work that may not survive. Every
other question is a **soft fork**: it rides along, the round ships its settled work, the
answer lands in the next round's push, and the watch never pauses for it. An open thread
is a soft fork by default; grade it hard only when its answer reaches the work itself.

Flags:

- `--rounds <N>` — the round budget. Default 5.
- `--subagent[=<model>]` — run rounds in a `hoopit-dev:monitor-pr-worker` instead of yourself,
  reusing it across rounds until it nears its context limit, then rotating to a fresh
  one. The model defaults to `opus`; `--subagent=fable` (or `sonnet`, `haiku`) overrides
  it. `opus` is deliberate: the worker carries the thread labour and the probing, while
  the design judgement (a round's design check, Step 3) is this session's, on whatever
  model it runs. Reach for `fable` on a design-heavy PR when the ledger's convergence
  counts say the rounds are patching their own patches.

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

Rounds run in a worktree for the PR branch — the round creates one when none exists — and
only on a PR whose head is not the default branch: a same-repo back-merge PR has the
default branch *as* its head, and working it would push there. That one means the watch
cannot arm: say so through `AskUserQuestion` (Step 5) rather than just printing it.

```bash
BRANCH=$(gh pr view <PR> --repo <OWNER_REPO> --json headRefName --jq .headRefName)
DEFAULT_BRANCH=$(gh repo view <OWNER_REPO> --json defaultBranchRef --jq .defaultBranchRef.name)
[[ "$BRANCH" == "$DEFAULT_BRANCH" ]] && echo "BACK_MERGE — do not arm"
```

The worker checks this again each round; catching it here just saves arming a watch that
would halt on its first round.

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
  command: "ONCE=<1 when the budget is 1, else 0> bash <SKILL_DIR>/scripts/watch-pr.sh <OWNER_REPO> <PR> 60",
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
- `GREEN head=… review=<decision> [pending_gates=<names>]` — this head has nothing left:
  no unresolved thread, no failing check, none still running, no conflict. Fired once per
  head; the merge decision goes to the user (Step 5). `pending_gates` here means a
  reviewer never reported at all and `GATE_TIMEOUT` (default 900s) elapsed waiting.
- `PR_CLOSED state=MERGED|CLOSED` — the script exits.
- `WATCH_ERROR fetch_failures=N last=…` — GitHub could not be reached five polls in a
  row (expired auth, network, deleted PR); the script exits non-zero. The watch is dead:
  go to Step 5.

With `ONCE=1` the script exits after its first `ROUND` or `GREEN` line. For any larger
budget the script runs on and the session `TaskStop`s it when the budget is spent.

For a repo whose reviewer statuses have other names, prefix `GATE_CHECKS=<a>,<b>`. Tune
the timeout with `GATE_TIMEOUT=<seconds>`.

Tell the user in one line that the watch is armed, what opens a round, and the budget.

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
  prompt: "PR_URL=<PR_URL> OWNER_REPO=<OWNER_REPO> PR=<PR> REPO_ROOT=<REPO_ROOT> LEDGER=<SKILL_DIR>/LEDGER.md PR_STATE=<SKILL_DIR>/scripts/pr-state.sh\nROUND: <the ROUND line verbatim>\nANSWERED: <every fork the user has settled, and the choice>\nGUIDANCE: <this session's scope and facts for the round> | none",
)
```

`ANSWERED` goes on **both** prompts. A fresh worker knows nothing the last one was told,
so a re-arm after a hard fork, or a rotation, would otherwise drop the very answer that
unblocked the watch. Carry every answer the PR has collected, not only the newest. A
re-arm from a fresh session recovers them from the ledger's `answered:` rows.

`GUIDANCE` is this session's own direction for the round, kept apart from `ANSWERED` so
the worker can tell a user's decision from a session's opinion. It carries scope — apply
minimally, no migration, file rather than fold — facts the worker cannot see, and a
demand for a step back on a mechanism the ledger shows patched before. A choice between
two remedies a reviewer offered travels the other way: the worker's design check probes
it and this session answers it, below.

Each completion notification reports `subagent_tokens`; keep a running total per worker.
Next round while the total is under 100k:

```
SendMessage(to: "pr-<PR>-worker", message: "ROUND: <the ROUND line verbatim>\nANSWERED: <each fork the user settled since the last round, and the choice>\nGUIDANCE: <this round's direction> | none")
```

The worker already holds the earlier answers, so this one carries only what is new.

**A design check.** A worker turn ending in `DESIGN CHECK` is a round paused before its
push, not a report: a fix tripped the worker briefing's step back, and the worker has
probed the shapes and put them to Codex's adversarial review. Answer it yourself, at
once, with the brief and the ledger in hand — the decision is this session's, not the
user's, and nothing waits on it:

```
SendMessage(to: "pr-<PR>-worker", message: "DESIGN: push | reshape to <n> — <why>")
```

Choose among the shapes the worker probed; a shape nobody probed is one more probe to ask
for, not an answer. Inline, the step back is yours to run, and the answer is the one you
record.

The worker's worktree is the worker's: verify its work by reading it — an edit of yours
between its commits is a change it did not make and cannot explain.

At 100k or above, rotate: spawn a fresh worker with the full prompt (use a new name,
e.g. `pr-<PR>-worker-2`) and start its total at zero.

One round at a time: a `ROUND` that lands mid-round is worked after the current one — and
often finds nothing, because the running round's last look already absorbed it. Its report
says so on the `Absorbed` line.

## Step 4 — Report

Print the round's report under a `Round N — <trigger>` heading. It is the round's
**delta** — what this round did; the **ledger** the round wrote into the PR description
holds the PR's cumulative state, so the two never need to say the same thing twice. Link
the PR once beneath the heading so the ledger is one click away, and put the budget in
the heading — `Round 3/5 — <trigger>` — so the user can see the watch running out before
it does. A round that reports `Ledger: not updated` says so too, with the reason — the
ledger is then behind by a round.

A round that found nothing to do — the previous round's last look had taken it — is
reported in one line and does not spend budget.

Two things come before grading. A report or design check whose first line is `CODEX
DOWN` is relayed the moment it lands: print the line, then `PushNotification` with it —
the user wants to know the external engine is out as soon as it is, and the round runs
on without it. Then read the ledger the round wrote and check convergence yourself: a
row tagged `fixes R<k>` on a mechanism another row already fixes, with no step back
recorded, is a patch to a patch — the next round's `GUIDANCE` demands the step back on
it.

Then grade the round's `QUESTIONS`. A section of **soft** forks is not an ending: the
watch stays armed, the questions go to the user in Step 5, and the next `ROUND` is worked
whether or not they have been answered. A **hard** fork ends the watch — `TaskStop` the
monitor, then ask — as does the same check "still failing" in two consecutive rounds.

Count the round. At the budget, `TaskStop` the monitor and take the budget path in Step
5. Below it, idle until the next `ROUND`.

Whenever the watch ends — budget spent, a hard fork, an error stop, or `PR_CLOSED` —
drop the label again, so it only ever marks PRs under an active watch:

```bash
gh pr edit <PR> --repo <OWNER_REPO> --remove-label monitored
```

## Step 4a — Land the merge

The PR is merged — a `PR_CLOSED state=MERGED` line, or a merge the Green path in Step 5
just performed with no monitor left to report it. Three things follow, in order.

**Tally.** Rounds, threads resolved, checks fixed, conflicts merged, and the ledger's
convergence counts. The ledger stays on the merged PR as the record of what was judged
along the way. One thing outlives the PR and is carried into the tally: commits the worktree holds and the remote does not — push
them, saying plainly that this opens a follow-up PR against the default branch.

**Report what is left open.** The merge closes the PR, not the thinking, so sweep three
places and list what survives:

- the ledger's `open` and `fork` rows — a finding nobody settled, a question nobody
  answered;
- questions this session asked and the user never came back to;
- TODOs and follow-ups written into the PR description outside the ledger block.

Offer to file them where this repo's `CLAUDE.md` says work items live — one line per
proposed item, title and a sentence — and file only what the user picks. An empty sweep
is worth saying out loud: *nothing left open.*

**Clean up, last.** The branch is spent, so invoke `clean-up-worktree` for it; its own
merge gate and safety checks stand, and its confirmation is the one place this is
approved. Skip it — saying why — when the tally just pushed commits past the merge: that
branch is live work again, not spent.

This goes last because it is the one irreversible move, and because the worktree it
removes may be the directory this session is running in — `ship` arms the watch from
inside it. Once it is gone, the shell has no working directory and nothing further runs.
Finish the tally and the sweep first, then hand the user the `cd` to the main worktree
that `clean-up-worktree` reports.

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

Five paths reach the user. The first two leave the watch running.

**A soft fork** — a decision the round turned up whose answer cannot invalidate the work.
Collect every soft fork the round produced, let the round finish its push (settled work
ships while the question waits), then ask them as one round of questions. The watch stays
armed meanwhile and the answer ships in the next round's push. A question left unanswered
rejoins the next round's question set, so it stays in front of the user. An answer settles
a ledger row: pass it into the next round so the row becomes `answered: <the choice>`,
which is how the PR shows the decision to a reviewer who was never asked.

**A hard fork** — the answer could invalidate work already done or reviews already run,
so further rounds would review something that may not survive. Stop the watch, then ask
it alongside the round's soft forks. An answer re-arms the watch (back to Step 2) with
the rest of the budget intact; the next round carries all the answers.

**Green** — a `GREEN` line. Before the merge question, once per head that carries pushes
since the last one, challenge the whole PR — the read no per-push reviewer gives it. From
the PR's worktree, with the ledger's judgement rows — the declines, the step-back picks —
as the focus:

```bash
bash "$(find ~/.claude/plugins -path '*review-gate/scripts/run_external_reviewers.sh' | head -1)" \
  <DEFAULT_BRANCH> --challenge-only --challenge "Merge readiness. Judgements to break: <the ledger's judgement rows, one line each>"
```

Read the file its `codex_challenge=` line names. A finding that **holds** — the ledger
says when — opens a round rather than a question, the same work a reviewer thread would
open: under `--subagent` as `ROUND: CHALLENGE head=<sha> findings=<n>` with the findings
and your reachability read in `GUIDANCE`, inline by working them yourself as the worker
briefing says. Its push brings the next `GREEN`, and that one carries the merge question.
The rest go into the tally as weighed and not held. A `codex_challenge_reason` line is
Step 4's `CODEX DOWN`, and the merge question goes ahead without the challenge.

The merge is the user's call, always: ask. Recommend it when
`review` reads `APPROVED` or `NONE` — `NONE` means the repo requires no approval, not that
one is missing — and recommend holding on `REVIEW_REQUIRED` or `CHANGES_REQUESTED`, naming
the reviewer the PR is waiting on. A `GREEN` carrying `pending_gates` went green with a
reviewer that never reported on the head: name it and recommend holding until it has.
On *Merge it*, merge with a method the repo allows:

```bash
gh repo view <OWNER_REPO> --json squashMergeAllowed,mergeCommitAllowed,rebaseMergeAllowed
gh pr merge <PR> --repo <OWNER_REPO> --<squash|merge|rebase>
```

Leave the monitor running either way: on a merge it sees `PR_CLOSED state=MERGED` next
poll and Step 4a lands it, and on *keep watching* a PR that moves again still has a watch.

**Budget spent** — the last round of `--rounds` is worked and reported. Stop, then ask
whether to spend another budget, saying what is still outstanding and whether the rounds
are converging: fewer findings each round argues for more, the same finding recurring
argues for the user. *Another N rounds* re-arms the watch (back to Step 2, label
included) with a fresh budget. The turn ends on the `AskUserQuestion`, never on prose: a
watch that goes dark without one is a watch the user restarts by hand, with its answers
lost.

**A stop** — the watch ended on something going wrong. Ask immediately, on its own, once
the label is dropped. A stop covers: a back-merge head (Step 1), a PR branch the round
could not put in a worktree, `WATCH_ERROR`, `PR_CLOSED state=CLOSED`, the same check failing two rounds running, the `Monitor` task
exiting or being killed, and any round that errors out beyond working around (auth
expired, worktree gone, push rejected, the worker dying twice). A watch always ends in
front of the user: the question is the last thing the turn does, and it names the real
reason.

The chat round carries the substance; `AskUserQuestion` carries the attention. Fire it
once per round of questions, headed `Monitoring`, its text naming the PR and how many
questions wait above it — `PR #16619 — 3 questions from round 4`. Each path has its own
options, because they answer different things:

| Path | Options |
| --- | --- |
| Soft fork | **Answer in chat** (recommended) · **Take all your recommendations** · **Stop monitoring, I'll take it from here** |
| Hard fork | **Answer in chat** (recommended) · **Take all your recommendations** · **Stop monitoring, I'll take it from here** — the first two re-arm the watch |
| Green | **Merge it** · **Not yet — keep watching** · **Stop monitoring, I'll take it from here** |
| Budget spent | **Another <N> rounds** · **Stop, I'll take it** · **Answer in chat** (when questions are outstanding) |
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
