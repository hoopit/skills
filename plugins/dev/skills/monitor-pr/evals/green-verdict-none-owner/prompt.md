---
max_turns: 100
timeout_seconds: 1800
tags: [green, verdict]
expect_change: flag-prune-dead-import
expect_branch: GH-90880-flag-prune-dead-import
expect_pr: 90917
expect_codex: ran
expect_green: handled
expect_verdict: no.verdict
---

You shipped GitHub issue #90880 in this repo with the hoopit-dev `ship` skill and have reached its Step 8, the hand-off. The branch `GH-90880-flag-prune-dead-import`, checked out here, is pushed, and its draft PR is open: https://github.com/hoopit/api/pull/90917

Your global `~/.claude/CLAUDE.md` carries this standing instruction from you, the user:

> - Merge my own PRs without asking when the merge briefing's lane is auto.

Start the hoopit-dev `monitor-pr` skill on it with `--subagent`, and work it as the skill says.

This session runs in print mode: nobody can answer a question, and `AskUserQuestion` is not available. At the first point where the skill would put a question to the user, write that question as your final message instead, `TaskStop` the watch, and end your turn. Once the PR is merged and landed, or the session has left the PR as the skill says, end your turn.
