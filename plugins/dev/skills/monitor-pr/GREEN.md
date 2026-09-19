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

**The merge briefing.** A `GREEN` asks someone to merge code they have not read, so the
question carries the read that tells them how hard to look before they do. Seven lines,
not a second PR description:

- what was wrong, and who felt it;
- what this changes, in a line;
- **Warranted: yes · larger than the issues · beyond the issues**, with the reason — the
  diff's size and reach weighed against the issues it closes, the rounds' additions
  included, since a watch is where scope grows;
- the decisions that could have gone the other way — the ledger's judgement rows, read
  off it rather than re-derived;
- **Merge risk: low · moderate · high · very high**, with the reason;
- what to look at first, if they read one thing;
- anything else that moves the depth of that read — a check that passed on retry, an
  approval given on an earlier head, a challenge finding weighed and not held.

Rate the risk on blast radius and reversibility, the two things a revert cannot fix:

| Risk | What puts it there |
| --- | --- |
| **Low** | Isolated or additive, a test went red on it, and a revert is a full undo. |
| **Moderate** | Changes behaviour on a path in use, or edits code others share — still fully revertible. |
| **High** | A revert alone no longer restores it: a data migration, a permissions or money path, a job whose runs land while it is live. |
| **Very high** | Effects land before anyone can react — a destructive migration, a send to users, a deletion sweep, a credential rotation. |

Risk is not a recommendation. A low-risk PR with a reviewer still owed recommends
holding; a very-high-risk PR that is green and challenged recommends merging.
The recommendation answers *may this merge*; the risk answers *how long to look first*.

Write the briefing into the PR description before asking, so whoever merges from GitHub
reads what the chat got. It is a block of its own at the top of the body: a
`## 🤖 Merge briefing · <head sha, 7 chars>` heading, the seven lines, then the
recommendation — merge or hold — with its reason, between
`<!-- agent-merge-briefing:start -->` and `<!-- agent-merge-briefing:end -->`. Write it
the way [`LEDGER.md`](LEDGER.md) writes its block — the body read fresh, the region
between the markers replaced — and prepend it when the markers are absent. Done when the
body holds one briefing block, its heading names this head, and the rest of the
description reads as it did.

When the write fails, say so in the merge question and ask anyway.

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
