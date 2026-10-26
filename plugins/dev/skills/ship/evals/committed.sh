# shellcheck shell=bash
# Sourced by a case that starts at Step 6: Steps 1–5 done the way ship would leave them. The
# worktree is create-worktree's, the regression test went red on master, and the fix and
# its test are one commit.
set -euo pipefail
cd "$EVAL_FIXTURE"

BRANCH=GH-18161/fix/post-image-delete-404
WT=$EVAL_FIXTURE/.worktrees/GH-18161-fix-post-image-delete-404
.claude/skills/create-worktree/create-worktree.sh "$BRANCH" --fetch >"$EVAL_RUN_DIR/create-worktree.log" 2>&1
cd "$WT"

python3 - <<'PY'
view = "posts/views/post_image_detail_view.py"
s = open(view).read()
s = s.replace("from typing import TYPE_CHECKING\n\n", "from typing import TYPE_CHECKING\n\nfrom django.shortcuts import get_object_or_404\n\n", 1)
s = s.replace("return PostImage.objects.get(id=self.kwargs[self.lookup_url_kwarg])",
              "return get_object_or_404(PostImage, id=self.kwargs[self.lookup_url_kwarg])", 1)
open(view, "w").write(s)
test = "posts/tests/test_app_api/test_post_image_detail_view.py"
with open(test, "a") as fh:
    fh.write('''
    def test_delete__missing_attachment__not_found(self, *args):
        """Regression test for GH-18161"""
        self.authorize_as_user(self.post_image.image.creator)
        missing_pk = self.post_image.pk
        self.post_image.delete()

        response = self.delete(url_args=[missing_pk])

        self.assert_not_found(response)
''')
PY
git add -A posts
GIT_AUTHOR_NAME="Hoopit Dev" GIT_AUTHOR_EMAIL=dev@hoopit.io GIT_COMMITTER_NAME="Hoopit Dev" \
GIT_COMMITTER_EMAIL=dev@hoopit.io GIT_AUTHOR_DATE=2026-10-02T09:00:00+02:00 \
GIT_COMMITTER_DATE=2026-10-02T09:00:00+02:00 \
  git commit -q -m "GH-18161: Answer 404 when deleting a post image that no longer exists" \
  -m "PostImageDetailView.get_object fetched with a bare .get(), so the permission check
raised PostImage.DoesNotExist on a repeated delete and the request answered 500."

