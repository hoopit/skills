---
tags: direct, team
expect_branch: ^GH-18301/
expect_title: ^GH-18301: \S
expect_closes: 18301
expect_team: backend
expect_draft: 0
expect_monitor: 0
max_turns: 40
---

The change for hoopit/api#18301 sits uncommitted in the current directory, on `master`, and its tests pass. Put it on a branch named the way the repo names its branches (mirror `git branch -r`), commit it, push, and open the PR. The backend team takes the review from there. Load `create-pull-request` before you name the branch.

The issue, so you need not fetch it:

> **hoopit/api#18301** — The urgent response reminder's cooldown is shorter than an organizer's patience
> Type: Task
>
> An organizer who presses "remind" on an occurrence and sees nobody respond presses it again ten or twenty minutes later. `OccurrenceUrgentResponseReminderNotification.COOLDOWN` is 15 minutes, so the second press reaches every invitee who has not answered yet, and they get the same push twice inside half an hour. Support has had three clubs ask how to stop the double push this month, and one of them turned push off for its members altogether, which also turns off the reminders that matter.
>
> Raise the cooldown to 30 minutes. A recipient reminded more than 30 minutes ago is still reminded again, so a second wave before training still works.

What the change in the working tree does: `COOLDOWN` goes from 15 to 30 minutes, and the cooldown tests move their 14- and 16-minute cases to 29 and 31 minutes. `uv run pytest events/tests/test_notifications/test_occurrence_urgent_response_reminder_notification.py` passed: 14 tests.

Report the PR URL when you are done. The run ends with that report: anything you would leave running past it, start it, then stop and report.
