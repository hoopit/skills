---
tags: ship
expect_branch: ^GH-18303/
expect_title: ^GH-18303: \S
expect_closes: 18303
expect_draft: 1
expect_followup: 1
---

You are running the `ship` skill on hoopit/api#18303 (GitHub issue, `WORK_ITEM`) and have reached Step 5. Steps 1–4 are done, and the review gate (Step 6) has already passed this change: one `standard` round, with Codex, Standards and Spec as reviewers and no findings. This run made no worktree in Step 2: the change sits uncommitted in the current directory, on `master`. Name the branch the way Step 2 says (mirror `git branch -r`, carry the item's key) and create it here with `git switch -c` before you commit.

> ## Step 5 — Commit
>
> Follow the repo's commit conventions; `git log` is the source of truth for its subject style and footers. Reference `WORK_ITEM` the way its tracker expects, and load `create-pull-request` before writing the message — it owns which work-item keys are allowed on a commit.
>
> ## Step 7 — Push and open the PR
>
> ```bash
> git push -u origin "$BRANCH"
> ```
>
> Follow the **`create-pull-request`** skill for the body, the labels-at-creation rule, and link hygiene. Add to the body it specifies:
>
> - the `WORK_ITEM` link section — or, unset, a line saying the change is untracked;
> - a `## Testing` line covering the tests added, or why none was feasible;
> - the review-gate notes across every round: the scope it ran at, which reviewers ran, findings addressed, findings skipped and why;
> - any extra sections the caller asked for.

The issue, so you need not fetch it:

> **hoopit/api#18303** — Retire the SLOW_SQL_LOGGING switch
> Type: Task
>
> `BaseView.dispatch` wraps every request in `SqlLoggerContext` when `SLOW_SQL_LOGGING` is on, and production has it on (`.envs/prod.env`). Nobody reads the lines it logs: slow queries reach us through Performance Insights and Sentry's spans, and the context makes every request capture its SQL for nothing.
>
> Two steps, in this order:
>
> 1. Drop the setting, the branch in `BaseView.dispatch`, and the line in `.envs/prod.env`.
> 2. Once step 1 is deployed to production, delete the `/api/prod/env/SLOW_SQL_LOGGING` parameter from the prod SSM parameter store. It is applied by hand, and step 1's deploy is the point from which nothing can read it.
>
> This issue is done when both steps are.

What the change in the working tree does: step 1 — the setting, `BaseView.dispatch` and its two imports, and the `.envs/prod.env` line are gone. Nothing else read the setting (`git grep SLOW_SQL_LOGGING` is empty). No test was added: the code that went away had none, and `uv run pytest club_united_api/tests` still passes.

Do Steps 5 and 7, then stop and report the PR URL. Do not start `monitor-pr` (Step 8), and do not move the board item: that is done.
