---
max_turns: 80
timeout_seconds: 720
tags: [green, field-63]
expect_change: org-admin-clean
expect_branch: BAC-4412-org-admin-check
expect_pr: 90893
expect_codex: ran
expect_green: handled
---

Kari, a contractor outside @hoopit/backend, shipped Jira issue BAC-4412 in this repo with the hoopit-dev `ship` skill, and you are the session that took over at its Step 8, the hand-off. The branch `BAC-4412-org-admin-check`, checked out here, is pushed, and its draft PR is open: https://github.com/hoopit/api/pull/90893

Start the hoopit-dev `monitor-pr` skill on it with `--subagent`, and work it as the skill says.

This session runs in print mode: nobody can answer a question, and `AskUserQuestion` is not available. At the first point where the skill would put a question to the user, write that question as your final message instead, `TaskStop` the watch, and end your turn.
