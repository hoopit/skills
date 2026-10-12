---
max_turns: 80
timeout_seconds: 1800
tags: [closing]
expect_change: org-admin-clean
expect_branch: BAC-4412-org-admin-check
expect_mode: standalone
expect_push: 0
expect_commits: 0
expect_workflow: 0
expect_dismissed: 3301000001
expect_kept: 3301000002
---

Handle the review comments on https://github.com/hoopit/api/pull/18420 with the hoopit-dev `review-github-comments` skill. The PR branch, `BAC-4412-org-admin-check`, is checked out here.

Work the round as the skill says and finish with its summary table. Stop there: do not start `monitor-pr` or any other watch on the PR.
