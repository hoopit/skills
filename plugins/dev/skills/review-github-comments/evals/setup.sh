#!/usr/bin/env bash
# Every case is one open PR on hoopit/api: a change from changes/ committed on a branch over a
# pinned api master, pushed to a per-run origin and checked out here, with GitHub answered by
# github.py from the case's pr.json. The case's frontmatter picks the change:
#   expect_change   the patches under changes/ the PR branch carries, one commit each, in order
#   expect_branch   the PR's head branch
set -euo pipefail

# The api master every patch applies to. Pinned so a suite measures the same PR against the
# same base whatever the checkout's default branch has moved to since.
PIN=403fda6846761580f20ef569188f1ce7dc6e351c
SUITE="$EVAL_SUITE_DIR"

# A per-run origin that takes the push: the PR branch lives there, and a fix the agent pushes
# lands where the checks can read it.
git clone -q --bare --shared "$EVAL_UPSTREAM" "$EVAL_RUN_DIR/origin.git"
git --git-dir "$EVAL_RUN_DIR/origin.git" update-ref refs/heads/master "$PIN"
git remote set-url origin "$EVAL_RUN_DIR/origin.git"
git remote set-url --push origin "$EVAL_RUN_DIR/origin.git"
git fetch -q origin
git checkout -q -B "$EVAL_EXPECT_BRANCH" "$PIN"
git branch -q -f master "$PIN"

when=$(( $(date +%s) - 90000 ))
for change in $EVAL_EXPECT_CHANGE; do
  git apply --index "$SUITE/changes/$change.patch"
  when=$(( when + 900 ))
  GIT_AUTHOR_DATE="@$when" GIT_COMMITTER_DATE="@$when" \
    git -c user.name="Kari Nordmann" -c user.email="kari@hoopit.io" commit -q -F "$SUITE/changes/$change.msg"
done
git push -q -u origin "$EVAL_EXPECT_BRANCH"

# The PR as GitHub holds it, its comments anchored to lines of the file at the PR head.
state="$EVAL_RUN_DIR/github.json"
python3 "$SUITE/github.py" init "$EVAL_CASE_DIR/pr.json" "$state" "$(git rev-parse HEAD)"

shims="$EVAL_RUN_DIR/shims"
cat >"$shims/gh" <<PY
#!$(command -v python3)
import sys
sys.path.insert(0, "$SUITE")
import github
github.main("$state", "$EVAL_CALLS")
PY
chmod +x "$shims/gh"
