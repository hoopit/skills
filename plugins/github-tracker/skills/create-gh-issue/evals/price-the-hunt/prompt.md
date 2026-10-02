---
expect_issues: 1
expect_effort: L,XL
tags: effort
---
My agent tracker is the GitHub project **LKs agent project** (<https://github.com/orgs/hoopit/projects/2>): `hoopit-board` for its mechanics, `create-gh-issue` for filing. Work items for agent work go there, assigned to me.

You are running unattended: nobody will answer a question before this run ends.

You are triaging Sentry issue API-5QR, which I asked you to file as an issue rather than fix: `IntegrityError: duplicate key value violates unique constraint "events-occurrence-id-event-unq"`, logged from `persist_occurrences` (`events/tasks/persist_occurrences_task.py:37`, the `occurrence.save()` in the savepoint). What you established:

- 14 events in the last 60 days, the last on 2026-09-28. The task catches the error and logs it, so no member sees a failure; that occurrence is just not persisted on that pass, and the next pass normally fills it.
- Its cause is not found. The task now locks the event first (`lock_event`, line 22), so two runs of the task no longer race each other. Every colliding pair Sentry still holds came from a single task run, within the same second, on events whose start an admin had moved earlier that day. That points at `Event._update_start_and_end` (`events/models/event.py:1668`), which shifts occurrence ids in bulk, or at a miss in the replacer's matching. You could not reproduce it locally.
- Once found, the fix may well be a few lines.

File it with the create-gh-issue skill. Do not investigate further. Stop once it is filed, and report what you filed.
