---
tags: ship, jira
expect_branch: ^BAC-7851/
expect_title: ^BAC-7851: \S
expect_subject: BAC-7851
expect_link: https://hoopit.atlassian.net/browse/BAC-7851
expect_keys: BAC-7851|ITSM-2931
expect_draft: 1
---

You are running the `handle-jira-issue` skill on BAC-7851. Its Step 3 handed off to the `ship` skill with this dispatch brief:

- `TARGET_REPO`: hoopit/api, the current directory.
- `WORK_ITEM`: BAC-7851 (Jira), https://hoopit.atlassian.net/browse/BAC-7851.
- `BRIEF`: below.
- A linked ITSM ticket exists, so: a `Refs ITSM-2931` commit footer and an `## ITSM` PR section linking that ticket.

You are inside `ship` and have reached Step 5. Steps 1–4 are done, and the review gate (Step 6) has already passed this change: one `standard` round, with Codex, Standards and Spec as reviewers and no findings. This run made no worktree in Step 2: the change sits uncommitted in the current directory, on `master`. Name the branch the way Step 2 says (mirror `git branch -r`, carry the item's key) and create it here with `git switch -c` before you commit.

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

The brief, from Jira, so you need not fetch it:

> **BAC-7851** — Let organizers re-send the urgent reminder after 10 minutes
> Type: Story · Parent: PM-412 (Organizer reminders) · Linked: ITSM-2931 (is caused by), BAC-7850 (relates to)
>
> Organizers at the club behind ITSM-2931 send the urgent "please respond" reminder 15 minutes before meetup and again at meetup, and the second press reaches nobody: the cooldown is 15 minutes. Shorten `OccurrenceUrgentResponseReminderNotification.COOLDOWN` to 10 minutes.
>
> BAC-7850 is the web-admin half: it shows the organizer when the next reminder can go. It ships on its own, after this one.

What the change in the working tree does: `COOLDOWN` goes from 15 to 10 minutes, and the cooldown tests move their 14- and 16-minute cases to 9 and 11 minutes. `uv run pytest events/tests/test_notifications/test_occurrence_urgent_response_reminder_notification.py` passed: 14 tests.

Do Steps 5 and 7, then stop and report the PR URL. Do not start `monitor-pr` (Step 8), and do not move the board item: that is done.
