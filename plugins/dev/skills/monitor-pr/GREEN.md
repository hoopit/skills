# Green

The `GREEN` path of [SKILL.md](SKILL.md)'s Step 5; steps named here are that file's.
`<GATE_SCRIPT>` and `<SKILL_DIR>` are the paths its Step 1 resolved.

**Green** — a `GREEN` line. Before the merge question, once per head that carries pushes
since the last one, challenge the whole PR — the read no per-push reviewer gives it. From
the PR's worktree, with the ledger's judgement rows — the declines, the step-back picks —
and the issues the PR closes as the focus. The **issues** are the ones its description
links (`closes #<n>`, the tracker section); a PR linking none is weighed against its
description, and the briefing says so:

```bash
git fetch origin <DEFAULT_BRANCH>
bash <GATE_SCRIPT> \
  origin/<DEFAULT_BRANCH> --challenge-only --challenge "Merge readiness. Is the whole diff warranted by these issues: <each issue, one line>? Judgements to break: <the ledger's judgement rows, one line each>"
```

Read the file its `codex_challenge=` line names. A finding that **holds** — the ledger
says when — opens a round rather than a question, the same work a reviewer thread would
open: under `--subagent` as `ROUND: CHALLENGE head=<sha> findings=<n>` with the findings
and your reachability read in `GUIDANCE`, inline by working them yourself as the worker
briefing says. Its push brings the next `GREEN`, and that one carries the merge question.
The rest go into the tally as weighed and not held. A `codex_challenge_reason` line is
Step 4's `CODEX DOWN`, and the merge question still goes — but it goes **recommending
hold**. The one read of the PR as a whole never happened, and
recommending a merge would be claiming a check that did not run. Say that in the question
and name what the challenge would have weighed: the ledger's judgement rows. *Merge it*
stays on the table, and restoring Codex, then
re-running the challenge on this head, is what turns the recommendation back.

Drop `agent-working` before asking (Step 4): the PR is the user's until they answer.
When this head is ready on the agent's side — the challenge ran and held nothing, and the
`GREEN` carries no `pending_gates` — mark the PR ready for review, the hand-off:

```bash
bash <SKILL_DIR>/scripts/pr-labels.sh <OWNER_REPO> <PR> -agent-working
gh pr ready <PR> --repo <OWNER_REPO>
```

**The merge briefing.** Settle the recommendation (below), then invoke the
`merge-briefing` skill for this PR as the owner of its rounds, handing it the issues the
challenge weighed, the recommendation with its reason, and the challenge findings weighed
and not held. It writes the briefing into the PR description; the merge question carries
the same text. When the write fails, say so in the merge question and ask anyway.

The merge is the user's call, always: ask, and recommend it. No Hoopit repo requires an
approval, so a `GREEN` waits on nobody's review; two things alone turn the recommendation
to holding. A `GREEN` carrying `pending_gates` went green with a reviewer that never
reported on the head: name it and recommend holding until it has. A merge-readiness
challenge that did not run holds it the same way, for the same reason — a reviewer that
never reported.
On *Merge it*, merge with a method the repo allows. Mark the PR ready first: a question
that went out recommending hold left it a draft, GitHub refuses to merge one, and `gh pr
merge` has no guard of its own for it. On a PR already ready the call warns and exits 0.

```bash
gh api repos/<OWNER_REPO> --jq '{squash: .allow_squash_merge, merge: .allow_merge_commit, rebase: .allow_rebase_merge}'
gh pr ready <PR> --repo <OWNER_REPO>
gh pr merge <PR> --repo <OWNER_REPO> --<squash|merge|rebase>
```

Leave the monitor running either way: on a merge it sees `PR_CLOSED state=MERGED` next
poll and Step 4a lands it, and on *keep watching* a PR that moves again still has a watch.
An unattended `GREEN` that went out without the question stops it instead
([UNATTENDED.md](UNATTENDED.md)).
