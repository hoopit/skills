#!/usr/bin/env bash
# Every case reviews one branch: a change from changes/ committed over a pinned api master, with
# Codex answered by codex-stub.py. The case's frontmatter picks both:
#   expect_change   the patches under changes/ the branch carries, one commit each, in order
#   expect_branch   the branch it is committed on
#   expect_codex    ran | fail
# A case's codex-review.txt, when present, replaces the answer of a review that finds nothing.
set -euo pipefail

# The api master every patch applies to. Pinned so a suite measures the same diff against the same
# base whatever the checkout's default branch has moved to since.
PIN=403fda6846761580f20ef569188f1ce7dc6e351c
SUITE="$EVAL_SUITE_DIR"

# A per-run origin, so the gate's `git fetch` keeps origin/master at the pin. The runner's upstream
# is shared by every run in the suite; this one belongs to the run. The dead push URL stays.
git clone -q --bare --shared "$EVAL_UPSTREAM" "$EVAL_RUN_DIR/origin.git"
git --git-dir "$EVAL_RUN_DIR/origin.git" update-ref refs/heads/master "$PIN"
git remote set-url origin "$EVAL_RUN_DIR/origin.git"
git fetch -q origin
git checkout -q -B "$EVAL_EXPECT_BRANCH" "$PIN"
git branch -q -f master "$PIN"
git branch -q --set-upstream-to=origin/master master

# The commit dates vary by run: run_external_reviewers.sh keys its cache on HEAD, and a sha two
# runs share would hand the second run the first one's Codex answer as `cached`.
when=$(( $(date +%s) - 40000 - RANDOM ))
for change in $EVAL_EXPECT_CHANGE; do
  git apply --index "$SUITE/changes/$change.patch"
  when=$(( when + 600 + RANDOM % 600 ))
  GIT_AUTHOR_DATE="@$when" GIT_COMMITTER_DATE="@$when" \
    git -c user.name="Kari Nordmann" -c user.email="kari@hoopit.io" commit -q -F "$SUITE/changes/$change.msg"
done

shims="$EVAL_RUN_DIR/shims"
{ echo "#!$(command -v python3)"; cat "$SUITE/codex-stub.py"; } >"$shims/codex"
chmod +x "$shims/codex"
python3 - "$shims/codex.json" <<EOF
import json, os, sys
json.dump({
    "calls": "$EVAL_CALLS",
    "mode": "${EVAL_EXPECT_CODEX:-ran}",
    "review": open("$EVAL_CASE_DIR/codex-review.txt").read() if os.path.isfile("$EVAL_CASE_DIR/codex-review.txt")
              else "I did not find any discrete, actionable bugs introduced by this change.\n",
    "challenge": json.dumps({"verdict": "approve", "summary": "No material concerns with the approach.",
                             "findings": [], "next_steps": []}),
}, open(sys.argv[1], "w"))
EOF
