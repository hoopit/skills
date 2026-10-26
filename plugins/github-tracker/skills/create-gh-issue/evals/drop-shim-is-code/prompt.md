---
expect_issues: 1
expect_types: Task,Bug,Feature
tags: type
---
My agent tracker is the GitHub project **LKs agent project** (<https://github.com/orgs/hoopit/projects/2>): `hoopit-board` for its mechanics, `create-gh-issue` for filing. Work items for agent work go there, assigned to me.

You are running unattended: nobody will answer a question before this run ends.

You shipped hoopit/api#19530. Its PR, hoopit/api#19533, merged an hour ago. It adds `fee_breakdown` to the user payment serializer, and it keeps the old top-level `fee_amount` field in the response only for app builds older than 4.12, which still read it. flutter-app 4.12, which reads `fee_breakdown` instead, goes to the stores on 2026-10-06. Once older builds are below 2% of sessions (about six weeks after the release, judging by past releases), `fee_amount` and the compatibility code that fills it can be deleted from the api.

Use the create-gh-issue skill to file the follow-up for removing `fee_amount`. Stop once it is filed, and report what you filed.
