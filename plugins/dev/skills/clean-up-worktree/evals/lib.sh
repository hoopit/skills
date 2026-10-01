# shellcheck shell=bash
# Sourced by every setup.sh in this suite. A case's commits are built with plumbing on a
# pinned api commit, with pinned author and dates, so their shas never change and a gh
# mock can name one as a PR's headRefOid.

set -euo pipefail
cd "$EVAL_FIXTURE"

BASE=403fda6846761580f20ef569188f1ce7dc6e351c
export GIT_AUTHOR_NAME="Hoopit Dev" GIT_AUTHOR_EMAIL="dev@hoopit.io"
export GIT_COMMITTER_NAME="Hoopit Dev" GIT_COMMITTER_EMAIL="dev@hoopit.io"
export GIT_AUTHOR_DATE="2026-09-30T10:00:00+02:00" GIT_COMMITTER_DATE="2026-09-30T10:00:00+02:00"

# commit_on <parent> <path> <line> <message>: a commit adding one file, printed as its sha.
commit_on() {
  local index="$EVAL_RUN_DIR/lib.index" blob tree
  rm -f "$index"
  GIT_INDEX_FILE=$index git read-tree "$1"
  blob=$(printf '%s\n' "$3" | git hash-object -w --stdin)
  GIT_INDEX_FILE=$index git update-index --add --cacheinfo "100644,$blob,$2"
  tree=$(GIT_INDEX_FILE=$index git write-tree)
  rm -f "$index"
  git commit-tree "$tree" -p "$1" -m "$4"
}

# expect_sha <name> <got> <want>: a moved sha would leave the gh mocks describing another commit.
expect_sha() {
  [[ $2 == "$3" ]] || { echo "$1 is $2, the mocks expect $3" >&2; exit 1; }
}

# worktree <branch> <sha> [pushed-sha]: the branch at <sha>, checked out under .worktrees/
# the way create-worktree names it. With [pushed-sha], origin/<branch> is its upstream there.
worktree() {
  git branch -q "$1" "$2"
  if [[ -n ${3:-} ]]; then
    git update-ref "refs/remotes/origin/$1" "$3"
    git branch -q --set-upstream-to="origin/$1" "$1"
  fi
  git worktree add -q "$EVAL_FIXTURE/.worktrees/${1//\//-}" "$1"
}
