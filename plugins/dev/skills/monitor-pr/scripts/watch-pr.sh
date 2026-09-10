#!/usr/bin/env bash
# Print one ROUND line the moment the PR has work the previous round did not see, and one GREEN
# line the first time a head has nothing left to do; exit when the PR leaves OPEN.
# Usage: watch-pr.sh <owner/repo> <pr_number> [interval_seconds=60]
# Env:   GATE_CHECKS     — comma-separated reviewer check names (default "CodeRabbit,codex-review").
#                          A head goes GREEN only once all of them have reported on it.
#        GATE_TIMEOUT    — seconds an otherwise-clean head waits for a gate check that never
#                          reported before going GREEN anyway (default 900 = 15m). A gate check can
#                          go missing entirely on a head (skipped, rate-limited) rather than just
#                          pending, so waiting on it forever would idle the watch; the timeout
#                          bounds that wait, and the GREEN line names what stayed silent.
#        ONCE=1          — exit right after the first ROUND or GREEN line.
#        MAX_FETCH_FAILS — consecutive `gh pr view` failures before giving up (default 5).
#
# A round fires on the *first* feedback of any kind — the actionable set holding something not in
# the previously fired round: a thread key (id:commentCount, so a reply in an old thread counts), a
# failing check (reset per head), or a conflict (reset per head). Reviewers still pending on the
# head are named in `pending_gates` rather than held for: the round starts on what has landed, and
# takes a last look for the rest before it pushes.
#
# A head goes GREEN once it has nothing left at all — no unresolved thread, no failing check, none
# still pending, no conflict — and every gate check has reported on it (or GATE_TIMEOUT elapsed
# waiting for one that never did). Fired once per head, so a quiet PR asks to be merged exactly
# once. Requiring zero unresolved threads (not merely zero *new* ones) is what keeps a GREEN from
# firing mid-round, while the session is still working threads it has seen.
set -u
REPO=$1; PR=$2; INTERVAL=${3:-60}
GATE_CHECKS=${GATE_CHECKS:-CodeRabbit,codex-review}
GATE_TIMEOUT=${GATE_TIMEOUT:-900}
MAX_FETCH_FAILS=${MAX_FETCH_FAILS:-5}
OWNER=${REPO%/*}; NAME=${REPO#*/}

QUERY='query($owner:String!,$name:String!,$pr:Int!,$endCursor:String){
  repository(owner:$owner,name:$name){ pullRequest(number:$pr){
    reviewThreads(first:100,after:$endCursor){
      pageInfo{hasNextPage endCursor}
      nodes{ id isResolved comments{totalCount} }
    } } } }'

fired_threads=""; fired_fail=""; fired_conflict=0; fired_head=""; fired_green=""; fetch_fails=0
gate_wait_start=0
while true; do
  if ! meta=$(gh pr view "$PR" --repo "$REPO" --json state,mergeable,headRefOid,reviewDecision \
                --jq '"\(.state) \(.mergeable) \(.headRefOid) \(if (.reviewDecision // "") == "" then "NONE" else .reviewDecision end)"' 2>&1); then
    fetch_fails=$((fetch_fails + 1))
    if [ "$fetch_fails" -ge "$MAX_FETCH_FAILS" ]; then
      echo "WATCH_ERROR fetch_failures=$fetch_fails last=$(tr '\n' ' ' <<<"$meta")"
      exit 1
    fi
    sleep "$INTERVAL"; continue
  fi
  fetch_fails=0
  read -r state mergeable head review <<<"$meta"
  if [ "$state" != "OPEN" ]; then echo "PR_CLOSED state=$state"; exit 0; fi

  if [ "$head" != "$fired_head" ]; then fired_fail=""; fired_conflict=0; fired_head=$head; gate_wait_start=0; fi

  checks=$(gh pr checks "$PR" --repo "$REPO" --json name,bucket 2>/dev/null)
  IFS=, read -ra gates <<<"$GATE_CHECKS"
  pending_gates=""
  for g in "${gates[@]}"; do
    jq -e --arg n "$g" 'any(.[]; .name==$n and .bucket!="pending")' <<<"$checks" >/dev/null 2>&1 \
      || pending_gates="${pending_gates:+$pending_gates,}$g"
  done
  gate_open=1; [ -n "$pending_gates" ] && gate_open=0
  failing=$(jq -r '.[] | select(.bucket=="fail") | .name' <<<"$checks" | sort)
  running=$(jq -r '.[] | select(.bucket=="pending") | .name' <<<"$checks" | grep -c .)

  threads=$(gh api graphql --paginate -f query="$QUERY" \
      -F owner="$OWNER" -F name="$NAME" -F pr="$PR" \
      --jq '.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved|not) | "\(.id):\(.comments.totalCount)"' \
      2>/dev/null | sort)
  conflicting=0; [ "$mergeable" = CONFLICTING ] && conflicting=1

  new_threads=$(comm -13 <(printf '%s\n' "$fired_threads") <(printf '%s\n' "$threads") | grep -c .)
  new_fail=$(comm -13 <(printf '%s\n' "$fired_fail") <(printf '%s\n' "$failing") | grep . | paste -sd, -)
  new_conflict=0; [ "$conflicting" = 1 ] && [ "$fired_conflict" = 0 ] && new_conflict=1
  actionable=0; { [ "$new_threads" -gt 0 ] || [ -n "$new_fail" ] || [ "$new_conflict" = 1 ]; } && actionable=1

  if [ "$actionable" = 1 ]; then
    gate_wait_start=0
    echo "ROUND head=${head:0:7} unresolved=$(grep -c . <<<"$threads") new_threads=$new_threads failing=${failing:+$(paste -sd, - <<<"$failing")} conflicting=$conflicting${pending_gates:+ pending_gates=$pending_gates}"
    fired_threads=$threads; fired_fail=$failing; fired_conflict=$conflicting
    [ "${ONCE:-0}" = 1 ] && exit 0
  elif [ "$fired_green" != "$head" ] && [ -z "$threads" ] && [ -z "$failing" ] \
       && [ "$running" = 0 ] && [ "$conflicting" = 0 ]; then
    # Nothing pending means a closed gate is a reviewer that never reported at all; give it
    # GATE_TIMEOUT to show up rather than calling the head green behind its back.
    if [ "$gate_open" = 0 ]; then
      now=$(date +%s)
      [ "$gate_wait_start" = 0 ] && gate_wait_start=$now
      if [ $((now - gate_wait_start)) -lt "$GATE_TIMEOUT" ]; then sleep "$INTERVAL"; continue; fi
    fi
    gate_wait_start=0
    echo "GREEN head=${head:0:7} review=$review${pending_gates:+ pending_gates=$pending_gates}"
    fired_green=$head
    [ "${ONCE:-0}" = 1 ] && exit 0
  else
    gate_wait_start=0
  fi
  sleep "$INTERVAL"
done
