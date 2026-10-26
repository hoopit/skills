---
expect_issues: 1
expect_decision: 1
tags: decision
---
My agent tracker is the GitHub project **LKs agent project** (<https://github.com/orgs/hoopit/projects/2>): `hoopit-board` for its mechanics, `create-gh-issue` for filing. Work items for agent work go there, assigned to me.

You are running unattended: nobody will answer a question before this run ends.

You were dispatched to work hoopit/api#19490 ("events: send the reminder push 2 hours before start, not 24"). While testing it, you found this and confirmed it on prod (read-only):

- When an admin removes a member from a group, the member's accepted responses to that group's future events stay accepted. They keep their seat, keep getting reminder pushes, and keep showing on the coach's attendance list.
- Over the last 90 days, 2,318 accepted responses belong to members no longer in the event's group, across 412 clubs. Some clubs treat this as intended (a player leaving mid-season still plays the final), and others have asked support why removed members still show up.

Whether removal should withdraw those responses, keep them but stop the reminders, or leave everything as it is, is not settled anywhere in the code or docs. It has nothing to do with #19490, which you will carry on with after this. First, record the finding with the create-gh-issue skill. Stop once it is filed, and report what you filed.
