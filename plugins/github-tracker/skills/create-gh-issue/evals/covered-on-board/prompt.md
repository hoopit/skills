---
expect_issues: 0
expect_reads: 19460
tags: search
---
My agent tracker is the GitHub project **LKs agent project** (<https://github.com/orgs/hoopit/projects/2>): `hoopit-board` for its mechanics, `create-gh-issue` for filing. Work items for agent work go there, assigned to me.

You are running unattended: nobody will answer a question before this run ends.

You were dispatched to measure how often staff merge duplicate users in the Django admin, for hoopit/api#19470. Along the way you found this, and confirmed it in the code:

- `HoopitAdmin.response_action` (`club_united_api/django/admin.py:712`) logs `Executed action on N objects: merge_users` for every selected row as soon as the action returns. `merge_users` (`users/admin/user_admin.py`) first renders `MergeUserForm`, so opening the merge form is logged as a merge, cancelling it too, and a confirmed merge is logged twice.
- So the `django_admin_log` rows for `merge_users` (35,296 in prod) are an upper bound, not a count of merges.

Use the create-gh-issue skill to record this finding. Stop once it is recorded, and report what you did. #19470 carries on after this.
