---
max_turns: 80
timeout_seconds: 1800
tags: [main]
expect_change: org-admin-defect
expect_branch: BAC-4412-org-admin-check
expect_mode: standalone
expect_fixed: 1
expect_push: 1
expect_workflow: 0
expect_dismissed: 3301000001
expect_dismissal: '[0-9a-f]{7}'
---

Handle the review comments on https://github.com/hoopit/api/pull/18420 with the hoopit-dev `review-github-comments` skill. The PR branch, `BAC-4412-org-admin-check`, is checked out here.

Work the round as the skill says and finish with its summary table. Stop there: do not start `monitor-pr` or any other watch on the PR.
