---
tags: ship
expect_branch: ^GH-18302/
expect_title: ^GH-18302: \S
expect_closes: 18302
expect_draft: 1
---

You are running the `ship` skill on hoopit/api#18302 (GitHub issue, `WORK_ITEM`) and have reached Step 5. Steps 1–4 are done, and the review gate (Step 6) has already passed this change: one `standard` round, with Codex, Standards and Spec as reviewers. Spec raised one finding, which you declined: "The comment should also cite BAC-7840, which fixed the same double-press class on the payment-created notification." Declined because BAC-7840 is a different notification with its own guard, and the comment explains this constant only. This run made no worktree in Step 2: the change sits uncommitted in the current directory, on `master`. Name the branch the way Step 2 says (mirror `git branch -r`, carry the item's key) and create it here with `git switch -c` before you commit.

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

> **hoopit/api#18302** — Say why the urgent response reminder waits 15 minutes
> Type: Task
>
> `OccurrenceUrgentResponseReminderNotification.COOLDOWN` is 15 minutes, and nothing in the code says why, so every request to change it starts the argument over. The number came with BAC-7793 (hoopit/api#17320), whose acceptance criteria asked for "long enough to cover an organizer pressing twice, short enough to leave room for a second wave before training". BAC-7801 later asked for 30 minutes and was closed as Won't Do, because organizers send that second wave about 20 minutes before meetup and 30 minutes would swallow it.
>
> Put that reasoning in a comment on `COOLDOWN`, naming the tickets it came from.

What the change in the working tree does: a three-line comment above `COOLDOWN` that cites both tickets, nothing else. It is a comment-only change, so no test was added; the cooldown tests still pass.

Do Steps 5 and 7, then stop and report the PR URL. Do not start `monitor-pr` (Step 8), and do not move the board item: that is done.
