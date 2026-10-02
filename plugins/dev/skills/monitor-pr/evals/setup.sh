#!/usr/bin/env bash
# Every case watches one open PR on hoopit/api: a change from changes/ committed over a pinned
# api master on its own branch, pushed to a per-run origin, and a fake GitHub (fake_github.py)
# that already holds the PR at the state the case starts from — a ROUND or a GREEN on the
# watch's first poll, so no case waits on real time. The case's frontmatter and github.json
# pick it:
#   expect_change   the patches under changes/ the branch carries, one commit each, in order
#   expect_branch   the PR branch, checked out in the fixture as the session's worktree
#   expect_pr       the PR number; unique per case, since watch-pr.sh keeps resume state under
#                   ~/.local/state/monitor-pr/ by repo and number
#   expect_codex    ran | fail — how codex-stub.py answers the merge-readiness challenge
# github.json holds the PR: title, body, draft, labels, its checks and statuses on the head
# setup makes (and on any head pushed after it), review threads, issue comments. `{HEAD}` in
# it is that head's sha, `{PR}` the number, and `{CURRENT_HEAD}` in a comment the head as it
# stands when the comment is read. `merge_after_polls: <n>` has the user merge the PR from
# GitHub once the watch has polled n times; `conflicting: true` makes the head dirty until a
# push replaces it.
set -euo pipefail

PIN=403fda6846761580f20ef569188f1ce7dc6e351c
SUITE="$EVAL_SUITE_DIR"

# The origin the round pushes to and the fake reads the head from. Both URLs point at it: the
# runner's dead push URL would turn every round into a rejected push.
git clone -q --bare --shared "$EVAL_UPSTREAM" "$EVAL_RUN_DIR/origin.git"
git --git-dir "$EVAL_RUN_DIR/origin.git" update-ref refs/heads/master "$PIN"
git remote set-url origin "$EVAL_RUN_DIR/origin.git"
git remote set-url --push origin "$EVAL_RUN_DIR/origin.git"
git fetch -q origin
git checkout -q -B "$EVAL_EXPECT_BRANCH" "$PIN"
git branch -q -f master "$PIN"
git branch -q --set-upstream-to=origin/master master

# Commit dates vary by run: run_external_reviewers.sh keys its cache on HEAD, and a sha two runs
# share would hand the second run the first one's challenge as `cached`.
when=$(( $(date +%s) - 40000 - RANDOM ))
for change in $EVAL_EXPECT_CHANGE; do
  git apply --index "$SUITE/changes/$change.patch"
  when=$(( when + 600 + RANDOM % 600 ))
  GIT_AUTHOR_DATE="@$when" GIT_COMMITTER_DATE="@$when" \
    git -c user.name="Kari Nordmann" -c user.email="kari@hoopit.io" commit -q -F "$SUITE/changes/$change.msg"
done
# GitHub keeps refs/pull/<n>/head on the PR's head, and merge-briefing fetches it.
cat >"$EVAL_RUN_DIR/origin.git/hooks/post-receive" <<SH
#!/usr/bin/env bash
while read -r _ new ref; do
  [ "\$ref" = "refs/heads/$EVAL_EXPECT_BRANCH" ] && git update-ref "refs/pull/$EVAL_EXPECT_PR/head" "\$new"
done
exit 0
SH
chmod +x "$EVAL_RUN_DIR/origin.git/hooks/post-receive"
git push -q origin "HEAD:refs/heads/$EVAL_EXPECT_BRANCH"
git branch -q --set-upstream-to="origin/$EVAL_EXPECT_BRANCH"
head=$(git rev-parse HEAD)

mkdir -p "$EVAL_RUN_DIR/github"
python3 - "$EVAL_CASE_DIR/github.json" "$EVAL_RUN_DIR/github/state.json" "$head" <<'EOF'
import json, os, sys, time
src, dst, head = sys.argv[1:]
env = os.environ
text = open(src).read().replace("{HEAD}", head).replace("{PR}", env["EVAL_EXPECT_PR"])
case = json.loads(text)
now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 3600))
pr = case["pr"]
pr.setdefault("draft", True)
pr.setdefault("labels", [])
pr.setdefault("state", "open")
pr.update(number=int(env["EVAL_EXPECT_PR"]), head_ref=env["EVAL_EXPECT_BRANCH"])
for t in case.get("threads", []):
    t.setdefault("resolved", False)
json.dump({
    "repo": "hoopit/api", "base": "master", "initial_head": head, "started_at": now, "updated_at": now,
    "pr": pr, "checks": case.get("checks", []), "statuses": case.get("statuses", []),
    "new_head_checks": case.get("new_head_checks", case.get("checks", [])),
    "new_head_statuses": case.get("new_head_statuses", case.get("statuses", [])),
    "threads": case.get("threads", []), "issue_comments": case.get("issue_comments", []),
    "issues": case.get("issues", {}), "closing_issues": case.get("closing_issues", []),
    "required_checks": case.get("required_checks", []), "conflicting": case.get("conflicting", False),
    "repo_labels": case.get("repo_labels", ["monitored", "agent-working"]),
    "merge_after_polls": case.get("merge_after_polls"),
}, open(dst, "w"), indent=1)
EOF

shims="$EVAL_RUN_DIR/shims"
python=$(head -1 "$shims/gh" | sed 's/^#!//')
cat >"$shims/gh" <<PY
#!$python
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, "$SUITE")
import fake_github
fake_github.main("$EVAL_RUN_DIR", "$EVAL_CALLS")
PY
chmod +x "$shims/gh"

# hoopit-board: Step 2 ties the session to the issues the PR closes. Recorded, and answered.
cat >"$shims/hoopit-board" <<PY
#!$python
import json, os, sys
with open("$EVAL_CALLS", "a") as fh:
    fh.write(json.dumps({"tool": "hoopit-board", "argv": sys.argv[1:], "stdin": None, "cwd": os.getcwd()}) + "\n")
if sys.argv[1:2] == ["bind"]:
    print("bound: no closing issue on the board")
    sys.exit(0)
sys.exit("hoopit-board: unsupported in this eval: " + " ".join(sys.argv[1:]))
PY
chmod +x "$shims/hoopit-board"

{ echo "#!$python"; cat "$SUITE/codex-stub.py"; } >"$shims/codex"
chmod +x "$shims/codex"
python3 - "$shims/codex.json" <<EOF
import json, os, sys
json.dump({
    "calls": "$EVAL_CALLS",
    "mode": "${EVAL_EXPECT_CODEX:-ran}",
    "review": "I did not find any discrete, actionable bugs introduced by this change.\n",
    "challenge": json.dumps({"verdict": "approve", "summary": "No material concerns with the approach.",
                             "findings": [], "next_steps": []}),
}, open(sys.argv[1], "w"))
EOF

# A watch armed fresh deletes this itself; a stale one from an earlier run must not be resumed.
rm -f "${XDG_STATE_HOME:-$HOME/.local/state}/monitor-pr/hoopit_api-$EVAL_EXPECT_PR"
