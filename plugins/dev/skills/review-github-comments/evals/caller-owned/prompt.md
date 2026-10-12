---
max_turns: 80
timeout_seconds: 1800
tags: [caller]
expect_change: org-admin-defect
expect_branch: BAC-4412-org-admin-check
expect_mode: caller
expect_fixed: 1
expect_push: 0
expect_commits: 1
expect_workflow: 0
---

You are the `monitor-pr` worker for https://github.com/hoopit/api/pull/18420, round 2. This checkout is the round's worktree, on the PR branch `BAC-4412-org-admin-check` at the PR head. The PR is back in draft and carries `agent-working`; the push, the labels, the ledger and the re-review are this briefing's, not the skill's. The merge-conflict axis came back clean.

Axis 2, review comments: invoke the hoopit-dev `review-github-comments` skill for https://github.com/hoopit/api/pull/18420, telling it this briefing **owns the round** (its caller-owned mode: comment work and commit only), and passing it:

- `LEDGER`: the `LEDGER.md` beside the hoopit-dev `monitor-pr` skill. Its rows so far: none, round 1 found nothing.
- `GATE_SCRIPT`: `scripts/run_external_reviewers.sh` in the hoopit-dev `review-gate` skill.

Stop when the skill returns, and report its rows. Do not run the other axes, do not push, and do not touch labels or the PR's draft state.
