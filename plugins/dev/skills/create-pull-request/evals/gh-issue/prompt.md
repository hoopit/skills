---
tags: ship
expect_branch: ^GH-18301/
expect_title: ^GH-18301: \S
expect_closes: 18301
expect_draft: 1
---

You are running the `ship` skill on hoopit/api#18301 (GitHub issue, `WORK_ITEM`) and have reached Step 5. Steps 1–4 are done, and the review gate (Step 6) has already passed this change: one `standard` round, with Codex, Standards and Spec as reviewers and no findings. This run made no worktree in Step 2: the change sits uncommitted in the current directory, on `master`. Name the branch the way Step 2 says (mirror `git branch -r`, carry the item's key) and create it here with `git switch -c` before you commit.

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

> **hoopit/api#18301** — The urgent response reminder's cooldown is shorter than an organizer's patience
> Type: Task
>
> An organizer who presses "remind" on an occurrence and sees nobody respond presses it again ten or twenty minutes later. `OccurrenceUrgentResponseReminderNotification.COOLDOWN` is 15 minutes, so the second press reaches every invitee who has not answered yet, and they get the same push twice inside half an hour. Support has had three clubs ask how to stop the double push this month, and one of them turned push off for its members altogether, which also turns off the reminders that matter.
>
> Raise the cooldown to 30 minutes. A recipient reminded more than 30 minutes ago is still reminded again, so a second wave before training still works.

What the change in the working tree does: `COOLDOWN` goes from 15 to 30 minutes, and the cooldown tests move their 14- and 16-minute cases to 29 and 31 minutes. `uv run pytest events/tests/test_notifications/test_occurrence_urgent_response_reminder_notification.py` passed: 14 tests.

Do Steps 5 and 7, then stop and report the PR URL. Do not start `monitor-pr` (Step 8), and do not move the board item: that is done.
