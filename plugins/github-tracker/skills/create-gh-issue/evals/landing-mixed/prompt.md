---
expect_issues: 2
expect_gate: 19540
expect_proposals: backlog
expect_dropped: index
tags: landing
---
My agent tracker is the GitHub project **LKs agent project** (<https://github.com/orgs/hoopit/projects/2>): `hoopit-board` for its mechanics, `create-gh-issue` for filing. Work items for agent work go there, assigned to me.

You are running unattended: nobody will answer a question before this run ends.

You shipped hoopit/api#19537 ("users: expire invitations nobody answered in 90 days"). Its PR, hoopit/api#19540, merged ten minutes ago and closed #19537. It is not in production yet: the production branch is promoted by hand, usually within a day. The PR adds a nightly Celery beat task, `expire_stale_invitations`, that deletes pending invitations older than 90 days, plus migration `users/migrations/0187_invitation_created_at_index.py`, which indexes `created_at` for it.

Your notes from the run list three loose ends:

1. Nobody has seen the task run against prod data. Prod (read-only) has 41,206 pending invitations older than 90 days and 3,980 younger. Once it is live, someone has to check that its first nightly run deleted about 41,200 rows and none younger than 90 days.
2. A reviewer suggested expiring unanswered `GroupJoinRequest` rows the same way. Nobody has asked for it, but you would argue for it: 18,000 of them are older than a year and clutter the admins' request list.
3. A reviewer asked for an index on `invitation.created_at` before the task scans the table. The PR's migration 0187 adds exactly that index.

Use the create-gh-issue skill to deal with all three. Stop once done, and report what you filed and what you dropped.
