#!/usr/bin/env bash
# Mid-session: the head already went GREEN, was briefed and readied, and the merge question is
# out. The PR branch lives in a worktree, as ship leaves it, and the watch's resume state says
# what that watch fired: this head's GREEN. The user merges from GitHub on the third poll.
set -euo pipefail
head=$(git rev-parse HEAD)
git checkout -q master
git worktree add -q ".worktrees/$EVAL_EXPECT_BRANCH" "$EVAL_EXPECT_BRANCH"
state="${XDG_STATE_HOME:-$HOME/.local/state}/monitor-pr"
mkdir -p "$state"
cat >"$state/hoopit_api-$EVAL_EXPECT_PR" <<STATE
declare -- fired_threads=""
declare -- fired_fail=""
declare -- fired_conflict="0"
declare -- fired_head="$head"
declare -- fired_green="$head"
STATE
