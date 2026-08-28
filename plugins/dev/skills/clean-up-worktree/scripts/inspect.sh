#!/usr/bin/env bash
# Read-only facts about ONE cleanup target: this session's worktree, or the branch
# passed as $1. Never mutates the repo, never enumerates other branches/worktrees.
#
# Usage: bash <plugin>/skills/clean-up-worktree/scripts/inspect.sh [branch]
#
# Contract: this script reports, it does not decide. Exit 1 means the target itself
# could not be inspected (no such branch, not a repo); otherwise 0. Any fact it could
# not establish is printed explicitly; SKILL.md section 3 owns what each such line means
# for the caller.

set -uo pipefail

WANT_BRANCH=${1:-}

CWD_ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || { echo "not a git repository" >&2; exit 1; }
# substr, not $2: worktree paths may contain spaces
MAIN_ROOT=$(git worktree list --porcelain | awk '/^worktree /{print substr($0, 10); exit}')
DEFAULT_BRANCH=$(git -C "$MAIN_ROOT" symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||')
DEFAULT_BRANCH=${DEFAULT_BRANCH:-master}

if [[ -n $WANT_BRANCH ]]; then
  BRANCH=$WANT_BRANCH
  # the worktree that has this branch checked out, if any
  TARGET_WT=$(git worktree list --porcelain | awk -v b="refs/heads/$BRANCH" '
    /^worktree /{p=substr($0, 10)} $0=="branch "b{print p; exit}')
  git -C "$MAIN_ROOT" rev-parse --quiet --verify "refs/heads/$BRANCH" >/dev/null \
    || { echo "BRANCH_EXISTS	no	$BRANCH"; exit 1; }
else
  TARGET_WT=$CWD_ROOT
  BRANCH=$(git -C "$TARGET_WT" symbolic-ref --quiet --short HEAD 2>/dev/null || echo "")
fi

echo "MAIN_ROOT	$MAIN_ROOT"
echo "TARGET_WORKTREE	${TARGET_WT:--}"
echo "TARGET_BRANCH	${BRANCH:-DETACHED}"
echo "DEFAULT_BRANCH	$DEFAULT_BRANCH"

# --- guards: nothing session-scoped to clean -------------------------------
[[ -z $WANT_BRANCH && $CWD_ROOT == "$MAIN_ROOT" ]] && echo "GUARD	IN_MAIN_WORKTREE"
[[ $BRANCH == "$DEFAULT_BRANCH" ]] && echo "GUARD	IS_DEFAULT_BRANCH"
[[ -z $BRANCH ]] && echo "GUARD	DETACHED_NO_BRANCH"
[[ -n $TARGET_WT && $TARGET_WT == "$MAIN_ROOT" ]] && echo "GUARD	TARGET_IS_MAIN_WORKTREE"

# A named branch can be checked out in a worktree anywhere on disk, including a checkout
# that has nothing to do with this workflow. Managed worktrees live under .claude/worktrees/
# (FleetView) or .worktrees/ (create-worktree); anything else gets flagged so the removal
# path is never a surprise.
if [[ -n $TARGET_WT && $TARGET_WT != "$MAIN_ROOT" ]] &&
  [[ $TARGET_WT != "$MAIN_ROOT/.claude/worktrees/"* && $TARGET_WT != "$MAIN_ROOT/.worktrees/"* ]]; then
  echo "GUARD	WORKTREE_OUTSIDE_MANAGED_ROOT	$TARGET_WT"
fi

# --- the merge gate -------------------------------------------------------
if [[ -n $BRANCH && $BRANCH != "$DEFAULT_BRANCH" ]]; then
  pr_line() { # $1 = state filter; empty output + rc 0 means "no such PR"
    gh pr list --head "$BRANCH" --state "$1" --limit 20 \
      --json number,state,mergedAt,headRefOid,url,title \
      --jq 'sort_by(.number) | last | select(.) | [(.number|tostring), .state, (.mergedAt//"-"), .headRefOid, .url, .title] | @tsv' 2>/dev/null
  }

  # An OPEN PR wins over a higher-numbered merged one from the same head branch:
  # picking the newest PR alone could green-light a branch that still has work in review.
  PR=$(pr_line open); RC=$?
  if [[ $RC -eq 0 && -z $PR ]]; then
    PR=$(pr_line all); RC=$?
  fi

  if [[ $RC -ne 0 ]]; then
    # Cannot tell "not merged" from "GitHub unreachable / not authenticated" — say so.
    echo "PR_LOOKUP_FAILED	gh exited $RC — merge state unknown, do not delete"
    PR=""
  elif [[ -n $PR ]]; then
    printf 'PR\t%s\n' "$PR"
    # A PR is matched by branch NAME, so "MERGED" alone does not prove that the commit
    # sitting here is the one that got merged (reused branch name, commits added after
    # the merge). Compare the tips and say so.
    PR_STATE=$(printf '%s' "$PR" | cut -f2)
    PR_NUMBER=$(printf '%s' "$PR" | cut -f1)
    PR_HEAD_OID=$(printf '%s' "$PR" | cut -f4)
    LOCAL_TIP=$(git -C "$MAIN_ROOT" rev-parse "refs/heads/$BRANCH" 2>/dev/null || echo "")
    if [[ -z $PR_HEAD_OID || -z $LOCAL_TIP ]]; then
      echo "TIP_MATCHES_PR	unknown	could not read local tip (${LOCAL_TIP:-empty}) or pr head (${PR_HEAD_OID:-empty})"
    elif [[ $PR_HEAD_OID == "$LOCAL_TIP" ]]; then
      TIP_MATCH=yes
      echo "TIP_MATCHES_PR	yes	$LOCAL_TIP"
    else
      echo "TIP_MATCHES_PR	no	local $LOCAL_TIP vs pr head $PR_HEAD_OID"
    fi
  else
    echo "PR	-	NONE	-	-	-	no pull request found for this branch"
  fi

  # GitHub deletes the head branch on merge, so origin/$BRANCH is usually gone by now and
  # the comparison would fall back to origin/$DEFAULT_BRANCH. Under squash-merge the merged
  # commits are not ancestors of the default branch, so that fallback reports every merged
  # commit as unpushed and blocks the cleanup this skill exists for. A MERGED PR whose head
  # oid IS the local tip is proof GitHub received exactly these commits — nothing to lose.
  if [[ ${PR_STATE:-} == MERGED && ${TIP_MATCH:-} == yes ]]; then
    BASE=""
    echo "UPSTREAM	-	(merged head branch deleted on GitHub)"
    echo "UNPUSHED	0	(tip is the merged head of pr #${PR_NUMBER:-?})"
  elif git -C "$MAIN_ROOT" rev-parse --quiet --verify "$BRANCH@{upstream}" >/dev/null; then
    BASE=$(git -C "$MAIN_ROOT" rev-parse --abbrev-ref "$BRANCH@{upstream}")
    echo "UPSTREAM	$BASE"
    NOTE=""
  elif git -C "$MAIN_ROOT" rev-parse --quiet --verify "origin/$DEFAULT_BRANCH" >/dev/null; then
    BASE="origin/$DEFAULT_BRANCH"
    echo "UPSTREAM	-"
    NOTE="	(vs $BASE; branch was never pushed)"
  else
    BASE=""
    echo "UPSTREAM	-"
    echo "UNPUSHED	?	(no upstream and no origin/$DEFAULT_BRANCH to compare against)"
  fi

  if [[ -n $BASE ]]; then
    AHEAD=$(git -C "$MAIN_ROOT" rev-list --count "$BASE..$BRANCH" 2>/dev/null || echo "?")
    echo "UNPUSHED	$AHEAD$NOTE"
    # these commits exist only locally — list them so they can be weighed before deleting
    [[ $AHEAD != 0 && $AHEAD != "?" ]] &&
      git -C "$MAIN_ROOT" log --oneline "$BASE..$BRANCH" | sed 's/^/UNPUSHED_COMMIT	/'
  fi
fi

# --- what removing the worktree would discard ------------------------------
if [[ -n $TARGET_WT && -d $TARGET_WT ]]; then
  # Assigning through a pipe would turn a failing git status into a count of 0, i.e. report
  # a broken worktree as clean and invite a --force removal. Capture the status first.
  if STATUS=$(git -C "$TARGET_WT" status --porcelain 2>&1); then
    DIRTY=$(printf '%s' "$STATUS" | grep -c . | tr -d ' ')
    echo "WORKTREE_DIRTY	$DIRTY"
    [[ $DIRTY != 0 ]] && printf '%s\n' "$STATUS" | sed 's/^/DIRTY_FILE	/'
  else
    echo "WORKTREE_DIRTY	unknown	git status failed: $(printf '%s' "$STATUS" | head -1)"
  fi
fi

# a clean target leaves the last [[ ]] test as the script's status — don't report failure
exit 0
