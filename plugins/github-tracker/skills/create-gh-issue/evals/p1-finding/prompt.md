---
expect_issues: 1
expect_status: backlog
expect_no_parent: 1
expect_names: 19485
tags: status
---
My agent tracker is the GitHub project **LKs agent project** (<https://github.com/orgs/hoopit/projects/2>): `hoopit-board` for its mechanics, `create-gh-issue` for filing. Work items for agent work go there, assigned to me.

You are running unattended: nobody will answer a question before this run ends.

You were dispatched to work hoopit/api#19485 ("users: list a child's guardians on the web profile"). While reading the guardian code for it, you found a hole and confirmed it with a throwaway test:

- `_UserChildrenListDeserializer.validate` (`users/web/views/user_children_list_view.py:101`) allows the link when `_child_or_guardian_in_a_group_admin_can_manage(...) or admin == guardian`. A caller who posts to their own id passes no check on the child at all: `POST /web/users/<own id>/children/ {"child_id": <any user id>}` answers 201 and creates the `GuardianToChildRelationship`.
- The endpoint needs only a signed-in user, so any account in production can make itself guardian of any user, and gets the guardian's access to that profile.
- Nothing in prod (read-only) shows it has been used: every guardian link made through this endpoint in the last 90 days was made by an admin of one of the child's groups.

It has nothing to do with #19485, which you will carry on with after this. First, record the finding with the create-gh-issue skill. Stop once it is filed, and report what you filed.
