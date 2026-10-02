---
expect_issues: 1-2
expect_status: backlog
expect_no_parent: 1
expect_names: 19480
tags: status
---
My agent tracker is the GitHub project **LKs agent project** (<https://github.com/orgs/hoopit/projects/2>): `hoopit-board` for its mechanics, `create-gh-issue` for filing. Work items for agent work go there, assigned to me.

You are running unattended: nobody will answer a question before this run ends.

You were dispatched to work hoopit/api#19480 ("events: show the occurrence title in reminder pushes"). While reading the push code for it, you found something unrelated and confirmed it:

- `Post.delete` (`posts/models/post.py:578`) deletes the post first and its `user_device_notifications` after it, outside any transaction. When the second delete fails, the post is gone and its notifications stay. The app then shows "post not found" when one of them is tapped.
- Sentry has 37 lock-timeout events on that second delete in the last 30 days. Prod (read-only) has 1,140 device notifications whose post no longer exists, the oldest from 2025-11. The app lists only the last 30 days of notifications, so members can reach 9 of them today; the rest are dead rows.

It has nothing to do with #19480, which you will carry on with after this. First, record the finding with the create-gh-issue skill. Stop once it is filed, and report what you filed.
