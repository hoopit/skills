---
max_turns: 60
timeout_seconds: 1800
tags: [scope]
expect_change: review-follow-ups-doc
expect_branch: BE-812-review-follow-ups
expect_codex: ran
expect_reviewers: 1
expect_challenge: 0
---

You are shipping a change in this repo with the `ship` skill and have reached its Step 6, the review gate. The change is committed on the branch checked out here, `BE-812-review-follow-ups`. Nothing is pushed and no PR exists.

Run round 1 of the gate: the hoopit-dev `review-gate` skill, a `full` pass, with these inputs.

- `SCOPE`: full
- `SPEC`: BE-812 — *Say where a follow-up found in review goes.* `docs/agents/issue-tracker.md` says which tracker takes agent work, but not what happens to a follow-up a reviewer raises. Add that it is filed in the personal tracker rather than fixed in the PR it was found in, and that the issue names that PR.
- `CHALLENGE`: Shape taken: a short section in `docs/agents/issue-tracker.md`, beside the other filing rules. Set aside: a line in `AGENTS.md`, which already points at this doc for everything about trackers.
- `PRIOR_ROUNDS`: none, this is round 1.

Work the pass as the skill says. Open your final reply with the gate's verdict line in its contract form (`PASS …` or `BLOCK: …`), then the notes. Stop when the pass returns: do not push, do not open a PR, and do not run a second round.
