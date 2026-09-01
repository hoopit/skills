#!/usr/bin/env bash
# Print one ROUND line each time the PR's reviewers have finished and there is new work; exit when it leaves OPEN.
# Usage: watch-pr.sh <owner/repo> <pr_number> [interval_seconds=60]
# Env:   GATE_CHECKS — comma-separated check names that must all be non-pending (default "CodeRabbit,codex-review").
#        ONCE=1      — exit right after the first ROUND line.
#        MAX_FETCH_FAILS — consecutive `gh pr view` failures before giving up (default 5).
#
# A round fires when every gate check on the current head is present and not pending, and the
# actionable set holds something not in the previously fired round: a thread key (id:commentCount,
# so a reply in an old thread counts), a failing check (reset per head), or a conflict (reset per head).
set -u
REPO=$1; PR=$2; INTERVAL=${3:-60}
GATE_CHECKS=${GATE_CHECKS:-CodeRabbit,codex-review}
MAX_FETCH_FAILS=${MAX_FETCH_FAILS:-5}
OWNER=${REPO%/*}; NAME=${REPO#*/}

QUERY='query($owner:String!,$name:String!,$pr:Int!,$endCursor:String){
  repository(owner:$owner,name:$name){ pullRequest(number:$pr){
    reviewThreads(first:100,after:$endCursor){
      pageInfo{hasNextPage endCursor}
      nodes{ id isResolved comments{totalCount} }
    } } } }'

fired_threads=""; fired_fail=""; fired_conflict=0; fired_head=""; fetch_fails=0
while true; do
  if ! meta=$(gh pr view "$PR" --repo "$REPO" --json state,mergeable,headRefOid \
                --jq '"\(.state) \(.mergeable) \(.headRefOid)"' 2>&1); then
    fetch_fails=$((fetch_fails + 1))
    if [ "$fetch_fails" -ge "$MAX_FETCH_FAILS" ]; then
      echo "WATCH_ERROR fetch_failures=$fetch_fails last=$(tr '\n' ' ' <<<"$meta")"
      exit 1
    fi
    sleep "$INTERVAL"; continue
  fi
  fetch_fails=0
  read -r state mergeable head <<<"$meta"
  if [ "$state" != "OPEN" ]; then echo "PR_CLOSED state=$state"; exit 0; fi

  if [ "$head" != "$fired_head" ]; then fired_fail=""; fired_conflict=0; fired_head=$head; fi

  checks=$(gh pr checks "$PR" --repo "$REPO" --json name,bucket 2>/dev/null)
  gate_open=1
  IFS=, read -ra gates <<<"$GATE_CHECKS"
  for g in "${gates[@]}"; do
    jq -e --arg n "$g" 'any(.[]; .name==$n and .bucket!="pending")' <<<"$checks" >/dev/null 2>&1 || gate_open=0
  done
  if [ "$gate_open" = 0 ]; then sleep "$INTERVAL"; continue; fi
  failing=$(jq -r '.[] | select(.bucket=="fail") | .name' <<<"$checks" | sort)

  threads=$(gh api graphql --paginate -f query="$QUERY" \
      -F owner="$OWNER" -F name="$NAME" -F pr="$PR" \
      --jq '.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved|not) | "\(.id):\(.comments.totalCount)"' \
      2>/dev/null | sort)
  conflicting=0; [ "$mergeable" = CONFLICTING ] && conflicting=1

  new_threads=$(comm -13 <(printf '%s\n' "$fired_threads") <(printf '%s\n' "$threads") | grep -c .)
  new_fail=$(comm -13 <(printf '%s\n' "$fired_fail") <(printf '%s\n' "$failing") | grep . | paste -sd, -)
  new_conflict=0; [ "$conflicting" = 1 ] && [ "$fired_conflict" = 0 ] && new_conflict=1

  if [ "$new_threads" -gt 0 ] || [ -n "$new_fail" ] || [ "$new_conflict" = 1 ]; then
    echo "ROUND head=${head:0:7} unresolved=$(grep -c . <<<"$threads") new_threads=$new_threads failing=${failing:+$(paste -sd, - <<<"$failing")} conflicting=$conflicting"
    fired_threads=$threads; fired_fail=$failing; fired_conflict=$conflicting
    [ "${ONCE:-0}" = 1 ] && exit 0
  fi
  sleep "$INTERVAL"
done
