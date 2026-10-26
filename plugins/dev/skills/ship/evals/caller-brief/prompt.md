---
max_turns: 120
timeout_seconds: 2400
expect_board: 1
expect_red: 1
expect_cpr_order: 1
expect_unattended: 1
expect_spec: "18161|404|API-75"
expect_footer: (?m)^Fixes API-75$
expect_section: (?m)^#+\s*Sentry\b
tags: [pipeline, caller]
---

You are running `fix-sentry-issue` on Sentry issue API-75, unattended: nobody will answer a question before this run ends. Steps 1 and 2 are done. There is no Linear issue, so the Sentry issue was filed as hoopit/api#18161, and that GitHub issue is the work item. Do its Step 3 now:

> ## Step 3 — Ship the fix
>
> Hand off to the **`ship`** skill, which takes the repo from the branch to a monitored PR. Pass it:
>
> - `TARGET_REPO` — the repo you were invoked in (resolved from cwd + its AGENTS.md).
> - `BRIEF` — the error, stacktrace, and event context you fetched in Step 1, and the Sentry issue to read fuller detail from.
> - `WORK_ITEM` — the Jira issue from Step 2 and its `$JIRA_BASE_URL/browse/<JIRA_KEY>` url, tracked in Jira.
> - Ask for a `Fixes <SENTRY_ID>` commit footer and a `## Sentry` PR section linking `SENTRY_URL` (`SENTRY_ID` is the short id, e.g. `BAC-QCB`).

What Step 1 fetched:

- **API-75**, https://hoopit-io.sentry.io/issues/150364938/: `DoesNotExist: PostImage matching query does not exist.` 1 event, 1 user, app 2.149.0. `DELETE /app/posts/attachments/127024/` answered 500.
- Stacktrace, innermost last:

  ```
  club_united_api/decorators.py in wrapper: self.check_object_permissions(request, self.get_permission_object())
  club_united_api/views/base_view.py in get_permission_object: return self.get_object()
  posts/views/post_image_detail_view.py in get_object (line 32): return PostImage.objects.get(id=self.kwargs[self.lookup_url_kwarg])
  django/db/models/query.py in get: raise self.model.DoesNotExist(
  ```
- Breadcrumbs: the same user sent `DELETE /app/posts/attachments/127024/` twice, 300 ms apart. The first answered 204.

The work item, hoopit/api#18161, https://github.com/hoopit/api/issues/18161: "posts: answer 404, not 500, when deleting a post image that no longer exists". The fix is a one-liner: `get_object` should use `get_object_or_404(PostImage, id=...)`, as `BaseView._get_object_by` does.

The run ends when monitor-pr's watch is armed on the PR: report the PR URL then.
