#!/usr/bin/env bash
# Every case briefs one open PR on hoopit/api: a change from changes/ committed over a pinned api
# master on its own branch, pushed to a per-run origin, and a fake GitHub that holds the PR. The
# fake is monitor-pr's (../../monitor-pr/evals/fake_github.py), imported rather than copied: it is
# behaviour, not case data, and one copy is what both suites' cases hold to GitHub's answers. It
# answers the PR, its diff and files, the closing issues and the body PATCH from one state file,
# so the briefing the agent writes is what the checks read back. The case's frontmatter and
# github.json pick it:
#   expect_change   the patches under changes/ the branch carries, one commit each, in order
#   expect_runlog   1 — a run-log commit lands on top of them, the head a caller skips the
#                   challenge on
#   expect_branch   the PR branch, checked out in the fixture as the session's worktree
#   expect_start    master — the session starts on master instead, so the challenge has to
#                   check the head out beside it
#   expect_pr       the PR number
#   expect_codex    ran | fail — how codex-stub.py answers the merge-readiness challenge
# github.json holds the PR in the fake's shape: title, body, checks, statuses, threads, closing
# issues; a case without one takes the suite's. `{HEAD}` in it is the head setup makes,
# `{PARENT}` that head's parent and `{PARENT7}` its short sha, `{BASE}` the pinned master and
# `{PR}` the number. A case's codex-challenge.json, when present, replaces the challenge's answer
# of no findings.
set -euo pipefail

PIN=403fda6846761580f20ef569188f1ce7dc6e351c
SUITE="$EVAL_SUITE_DIR"
FAKE="$SUITE/../../monitor-pr/evals"

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
commit() {
  when=$(( when + 600 + RANDOM % 600 ))
  GIT_AUTHOR_DATE="@$when" GIT_COMMITTER_DATE="@$when" \
    git -c user.name="Kari Nordmann" -c user.email="kari@hoopit.io" commit -q "$@"
}
for change in $EVAL_EXPECT_CHANGE; do
  git apply --index "$SUITE/changes/$change.patch"
  commit -F "$SUITE/changes/$change.msg"
done
if [ "${EVAL_EXPECT_RUNLOG:-0}" = 1 ]; then
  mkdir -p docs/runs
  printf '%s\n' "$ manage.py backfill_bank_account_balances --dry-run=false (production)" \
    "processed 412 organizations, 0 errors" >docs/runs/BAC-4412-backfill.md
  git add docs/runs/BAC-4412-backfill.md
  commit -m "BAC-4412: Run log for the bank account balance backfill"
fi

# GitHub keeps refs/pull/<n>/head on the PR's head, and the challenge fetches it.
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
parent=$(git rev-parse HEAD^)
[ "${EVAL_EXPECT_START:-}" = master ] && git checkout -q master

mkdir -p "$EVAL_RUN_DIR/github"
case_json="$EVAL_CASE_DIR/github.json"
[ -f "$case_json" ] || case_json="$SUITE/github.json"
python3 - "$case_json" "$EVAL_RUN_DIR/github/state.json" "$head" "$parent" "$PIN" <<'EOF'
import json, os, sys, time
src, dst, head, parent, base = sys.argv[1:]
env = os.environ
text = (open(src).read().replace("{HEAD}", head).replace("{PARENT7}", parent[:7]).replace("{PARENT}", parent)
        .replace("{BASE}", base).replace("{PR}", env["EVAL_EXPECT_PR"]))
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
    "threads": case.get("threads", []), "issue_comments": case.get("issue_comments", []),
    "issues": case.get("issues", {}), "closing_issues": case.get("closing_issues", []),
    "required_checks": case.get("required_checks", []),
}, open(dst, "w"), indent=1)
# What the checks hold the PR against: everything but the briefing block must survive.
json.dump(pr, open(os.path.join(os.path.dirname(dst), "pr-before.json"), "w"), indent=1)
EOF

shims="$EVAL_RUN_DIR/shims"
python=$(head -1 "$shims/gh" | sed 's/^#!//')
cat >"$shims/gh" <<PY
#!$python
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, "$FAKE")
import fake_github
fake_github.main("$EVAL_RUN_DIR", "$EVAL_CALLS")
PY
chmod +x "$shims/gh"

{ echo "#!$python"; cat "$SUITE/codex-stub.py"; } >"$shims/codex"
chmod +x "$shims/codex"
python3 - "$shims/codex.json" <<EOF
import json, os, sys
challenge = "$EVAL_CASE_DIR/codex-challenge.json"
json.dump({
    "calls": "$EVAL_CALLS",
    "mode": "${EVAL_EXPECT_CODEX:-ran}",
    "review": "I did not find any discrete, actionable bugs introduced by this change.\n",
    "challenge": open(challenge).read() if os.path.isfile(challenge)
                 else json.dumps({"verdict": "approve", "summary": "No material concerns with the approach.",
                                  "findings": [], "next_steps": []}),
}, open(sys.argv[1], "w"))
EOF
