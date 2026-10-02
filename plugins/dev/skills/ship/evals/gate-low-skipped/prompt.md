---
cwd: api/.worktrees/GH-18161-fix-post-image-delete-404
max_turns: 60
timeout_seconds: 1500
expect_unattended: 0
expect_spec: "18161|404"
tags: [gate]
---

You are running the `ship` skill on hoopit/api#18161: `WORK_ITEM` is that GitHub issue, and `BRIEF` is the issue below. `hoopit-board start` has run, and Steps 1–5 are done:

- Step 2: the worktree is this directory, `.worktrees/GH-18161-fix-post-image-delete-404` in the api checkout, on branch `GH-18161/fix/post-image-delete-404`, made by api's create-worktree.
- Steps 3 and 4: `test_delete__missing_attachment__not_found` went red on master (`PostImage.DoesNotExist`), and passes with the fix, which makes the view's `get_object` look the image up with `get_object_or_404`. `uv run pytest posts/tests/test_app_api/test_post_image_detail_view.py` passed: 3 tests.
- Step 5: the fix and its test are one commit at `HEAD`.

The shape you took: keep the view's `get_object` override and make its lookup answer 404. The one you set aside: drop the override for `BaseView`'s default lookup, because you were not sure the view's filter backends reach the same rows.

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

Continue from Step 6. The run ends when monitor-pr's watch is armed on the PR: report the PR URL then.
