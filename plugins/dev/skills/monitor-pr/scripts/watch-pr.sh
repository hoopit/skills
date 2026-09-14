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
#        MAX_FETCH_FAILS — consecutive failed GitHub reads before giving up (default 5).
#        REVIEW_MAX_AGE  — seconds a review-thread read is reused while nothing says it changed
#                          (default 600). The thread read is the watch's only GraphQL call, and
#                          GraphQL is the bucket every agent on the machine shares, so it is
#                          re-asked only when the head or pr_meta's review marker moves. A
#                          thread resolved in the UI without a reply moves neither; this bounds
#                          how late the watch sees it.
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
REVIEW_MAX_AGE=${REVIEW_MAX_AGE:-600}
. "$(dirname "${BASH_SOURCE[0]}")/gh-pr-api.sh"

fired_threads=""; fired_fail=""; fired_conflict=0; fired_head=""; fired_green=""; fetch_fails=0
gate_wait_start=0
review_state=""; review_key=""; review_read_at=0
while true; do
  if ! meta=$(pr_meta "$REPO" "$PR" 2>&1); then
    fetch_fails=$((fetch_fails + 1))
    if [ "$fetch_fails" -ge "$MAX_FETCH_FAILS" ]; then
      echo "WATCH_ERROR fetch_failures=$fetch_fails last=$(tr '\n' ' ' <<<"$meta")"
      exit 1
    fi
    sleep "$INTERVAL"; continue
  fi
  read -r state conflicting head review_marker <<<"$meta"
  if [ "$state" != "OPEN" ]; then echo "PR_CLOSED state=$state"; exit 0; fi

  if [ "$head" != "$fired_head" ]; then fired_fail=""; fired_conflict=0; fired_head=$head; gate_wait_start=0; fi

  # An empty read here reads as "no failing checks, none running", which is half of what
  # GREEN tests for — so a failure polls again rather than calling the head clean.
  if ! checks=$(pr_checks "$REPO" "$head" 2>&1); then
    fetch_fails=$((fetch_fails + 1))
    if [ "$fetch_fails" -ge "$MAX_FETCH_FAILS" ]; then
      echo "WATCH_ERROR fetch_failures=$fetch_fails last=$(tr '\n' ' ' <<<"$checks")"
      exit 1
    fi
    sleep "$INTERVAL"; continue
  fi
  IFS=, read -ra gates <<<"$GATE_CHECKS"
  pending_gates=""
  for g in "${gates[@]}"; do
    awk -F'\t' -v n="$g" '$2==n && $1!="pending"{found=1} END{exit !found}' <<<"$checks" \
      || pending_gates="${pending_gates:+$pending_gates,}$g"
  done
  gate_open=1; [ -n "$pending_gates" ] && gate_open=0
  failing=$(awk -F'\t' '$1=="fail"{print $2}' <<<"$checks" | sort)
  running=$(awk -F'\t' '$1=="pending"{print $2}' <<<"$checks" | grep -c .)

  now=$(date +%s)
  if [ "$head $review_marker" != "$review_key" ] || [ $((now - review_read_at)) -ge "$REVIEW_MAX_AGE" ]; then
    if ! fresh=$(pr_review_state "$REPO" "$PR" 2>&1); then
      fetch_fails=$((fetch_fails + 1))
      if [ "$fetch_fails" -ge "$MAX_FETCH_FAILS" ]; then
        echo "WATCH_ERROR fetch_failures=$fetch_fails last=$(tr '\n' ' ' <<<"$fresh")"
        exit 1
      fi
      sleep "$INTERVAL"; continue
    fi
    review_state=$fresh; review_key="$head $review_marker"; review_read_at=$now
  fi
  fetch_fails=0
  review=$(sed -n 's/^review=//p' <<<"$review_state" | head -1)
  threads=$(grep -v '^review=' <<<"$review_state")

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
