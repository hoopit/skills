---
cwd: triage
max_turns: 120
timeout_seconds: 2400
expect_board: 1
expect_red: 1
expect_cpr_order: 1
expect_unattended: 1
expect_spec: "18161|404"
tags: [pipeline]
---

/hoopit-dev:ship https://github.com/hoopit/api/issues/18161 --unattended

Work hoopit/api#18161 to a monitored PR. hoopit/api is checked out at `../api`. Nobody is watching this session: nobody will answer a question before the run ends.

The issue, so you need not fetch it:

> **hoopit/api#18161** — posts: answer 404, not 500, when deleting a post image that no longer exists
> Type: Bug
>
> `DELETE /app/posts/attachments/<id>/` answers 500 when the `PostImage` does not exist, instead of 404.
>
> Sentry: https://hoopit-io.sentry.io/issues/150364938/ (API-75) — `PostImage.DoesNotExist`, app 2.149.0, attachment 127024.
>
> `PostImageDetailView.get_object` (`posts/views/post_image_detail_view.py:32`) uses a bare `PostImage.objects.get(...)`, bypassing the `get_object_or_404` in `BaseView._get_object_by` (`club_united_api/views/base_view.py:500`). The permission check calls it, so a repeated delete of an already-deleted image surfaces as an unhandled 500.
>
> The client side of the repeat (the app's deferred image delete can re-send a DELETE) is tracked separately in flutter-app.
>
> **Acceptance:** a DELETE of a missing post image returns 404, pinned by a regression test; API-75 resolved once the fix reaches `production`.

The run ends when monitor-pr's watch is armed on the PR: report the PR URL then.
