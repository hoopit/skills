---
max_turns: 50
timeout_seconds: 1200
expect_change: org-admin-clean
expect_branch: BAC-4412-org-admin-check
expect_pr: 90957
tags: [briefed, direct]
expect_codex: ran
expect_outcome: briefed
expect_challenge: ran
expect_marker: ran
expect_recommend: hold
expect_risk: 'moderate|high|very high'
expect_lane: human
expect_line: 'CHALLENGE: ran weighed=0 held=0 marker=ran'
---

How risky is https://github.com/hoopit/api/pull/90957 to merge, and what should I read first? Use the hoopit-dev `merge-briefing` skill. Its branch, `BAC-4412-org-admin-check`, is checked out here. Write the briefing into the PR description as well; you don't need to ask me first.

This session runs in print mode: nobody can answer a question. Stop when the skill returns, and end your reply with its `CHALLENGE:` line, and `HELD:` with its findings if it held. Do not push, mark the PR ready, merge it or answer review threads.
