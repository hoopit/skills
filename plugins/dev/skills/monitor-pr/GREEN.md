# Green

The `GREEN` path of [SKILL.md](SKILL.md)'s Step 5; steps named here are that file's.
`<SKILL_DIR>` is the path its Step 1 resolved, and `<base>` is the PR's base branch
(`.base.ref`).

**Does the base require the check?** Ask once, first: whether `<base>` requires the
`merge-briefing` status decides what a briefing that did not pass costs below. Branch
protection and rulesets are both readable with read access. A read that fails answers
`yes`: guessing `no` would ready a head the merge is then refused on, and a wrong `yes`
costs only a hold:

```bash
if p=$(gh api repos/<OWNER_REPO>/branches/<base> --jq '.protection.required_status_checks.contexts[]?') &&
   r=$(gh api repos/<OWNER_REPO>/rules/branches/<base> --jq '.[] | select(.type == "required_status_checks") | .parameters.required_status_checks[].context'); then
  printf '%s\n' "$p" "$r" | grep -qx merge-briefing && echo REQUIRED=yes || echo REQUIRED=no
else echo REQUIRED=yes; fi
```

**Green** — a `GREEN` line. Before the merge question, once per head that carries pushes
since the last one, brief the PR: invoke the `merge-briefing` skill from the PR's worktree,
as the owner of its rounds. It runs the merge-readiness challenge — the read no per-push
reviewer gives the PR — and writes the briefing into the description. Hand it the issues
the PR closes (the ones its description links, `closes #<n>`, the tracker section), the
ledger's judgement rows — the declines, the step-back picks — as the challenge's focus,
the recommendation with its reason (below), and on a run-log push (below) that it skips
the challenge. Its `CHALLENGE:` line is the challenge's score: write it into the ledger's
tally in the description as **challenge findings weighed** and **held** — no round will;
a head briefed again replaces its own earlier count rather than adding to it — and it is
what the paths below read.

**`HELD`** — a challenge finding held, and nothing was written. It opens a round rather
than a question, the same work a reviewer thread would open: under `--subagent` as
`ROUND: CHALLENGE head=<sha> findings=<n>` with the findings and the reachability read
`merge-briefing` returned in `GUIDANCE`, inline by working them yourself as the worker
briefing says. Its push brings the next `GREEN`, and that one carries the merge question.
A round that commits nothing — every held finding declined on a second read — brings no
new head and so no `GREEN`: come back here and ask the **no passing briefing** question
below, naming the held findings and the round's declines.

**`CHALLENGE: not-run`** is Step 4's `CODEX DOWN`: `merge-briefing`
has turned the recommendation to hold and named what the challenge would have weighed.
**`marker=unwritten`** with no `HELD:` is a failed write: re-send the write once. With
`REQUIRED=no` the briefing gates nothing: a write that fails again is reported, and the
merge question asked as usual.

**No passing briefing** — with `REQUIRED=yes`, a head whose challenge did not run or whose
write failed twice, and on any repo a challenge round that declined every held finding.
No briefing stands behind this head — and with `REQUIRED=yes` the check refuses the
merge — so ask this in place of the merge question, saying which and recommending hold.
Options: **Brief this head again** · **Not yet — keep watching** (nothing brings this
question back on its own: the user asks for the re-brief, or a push moves the head) ·
**Stop monitoring, I'll take it from here**. *Brief this head again* re-runs
`merge-briefing` on this head with the challenge — never skipped, and with any round's
declines among the judgement rows — and carries on from the top of this file with what
it returns. Nothing re-briefs a head on its own: the watch fires `GREEN` once per head.

Drop `agent-working` before asking (Step 4): the PR is the user's until they answer.
When this head is ready on the agent's side — the challenge ran (or was carried as `ran`)
and nothing held, the marker written where `REQUIRED=yes`, and the `GREEN` carries no
`pending_gates` — mark the PR ready for review, the
hand-off:

```bash
bash <SKILL_DIR>/scripts/pr-labels.sh <OWNER_REPO> <PR> -agent-working
gh pr ready <PR> --repo <OWNER_REPO>
```

The merge is the user's call, always: ask, and recommend it.

**An approval owed.** A `GREEN` waits on nobody's review, but the merge can: a repo on the
shared team-review gate requires a `<team>-approval` status, which the watch leaves out
(`pr_checks`), because the approval comes only after the hand-off. Read it after the
hand-off — a gate that skips drafts judges the PR only once it is ready:

```bash
gh api repos/<OWNER_REPO>/commits/<head sha>/status --jq '.statuses[] | select(.context | endswith("-approval")) | "\(.context) \(.state) \(.description)"'
```

One that is not `success` is an approval still owed: name it with its description in the
merge question, and say GitHub refuses the merge until it passes. It does not turn the
recommendation to holding — the PR is done on the agent's side, and the approval is the
team's to give.

These alone turn the recommendation to holding. A `GREEN` carrying `pending_gates` went
green with a gate that never reported on the head: name it and recommend holding until it has. A merge-readiness
challenge that did not run holds it the same way, for the same reason — a reviewer that
never reported — and, with `REQUIRED=yes`, so does a briefing that never reached the
description, which the check will not pass on a head it does not already cover. And a run still owed (below) holds it until the run is done.

**A run owed before merge.** A description whose `## Run before merge` section still has
an unticked box puts the run question in place of the merge question, once the PR is
ready and briefed — the briefing recommending hold, naming the run. The question carries
the exact command, how it will run and against what, and anything the output should
show. Run it the way the repo's `AGENTS.md` says a command runs against that
environment. Options: **Run it** · **I'll run it — output to follow in chat** ·
**Not yet — keep watching**.

With the output in hand, from you or the user, read it against what it should show. A
failed run, or one that did something other than expected, is a stop: report it and ask,
never re-run on your own. A good run writes its **run log** where the repo's convention
puts it, in one commit touching nothing else, and ticks the box in the description with
the date and a line of what the run did. Push that commit with no review round: it
changes no code, so the head it makes needs green checks alone — its `GREEN` briefs the
new head with the challenge skipped and the run's result in the briefing, and asks the
merge question. Done when every box is ticked and the merge question names the run's
result.

On *Merge it*, merge with a method the repo allows. Mark the PR ready first: a question
that went out recommending hold left it a draft, GitHub refuses to merge one, and `gh pr
merge` has no guard of its own for it. On a PR already ready the call warns and exits 0.

```bash
gh api repos/<OWNER_REPO> --jq '{squash: .allow_squash_merge, merge: .allow_merge_commit, rebase: .allow_rebase_merge}'
gh pr ready <PR> --repo <OWNER_REPO>
```

With `REQUIRED=yes`, readying is what makes the status post, a minute or so later, and
the watch leaves that status out (`pr_checks`). So wait in the background for the head's
status to read `success`. Waiting on `success` alone, not on any settled state, is what
lets a stale `failure` from before the briefing be replaced:

```bash
for i in $(seq 30); do
  s=$(gh api repos/<OWNER_REPO>/commits/<head sha>/status --jq '[.statuses[] | select(.context == "merge-briefing") | .state][0] // empty')
  [ "$s" = success ] && break; sleep 10
done; echo "merge-briefing=${s:-missing}"
```

Then merge, never with `--admin`: GitHub's own refusal is what guards a head the check
fails. A refusal, or a status that never reached `success`, goes to the user with the
status's description; a bypass is theirs.

```bash
gh pr merge <PR> --repo <OWNER_REPO> --<squash|merge|rebase>
```

Leave the monitor running either way: on a merge it sees `PR_CLOSED state=MERGED` next
poll and Step 4a lands it, and on *keep watching* a PR that moves again still has a watch.
