#!/usr/bin/env bash
# Print one ROUND line the moment the PR has work the previous round did not see, and one GREEN
# line the first time a head has nothing left to do; re-request a review that has gone quiet; exit
# when the PR leaves OPEN.
# Usage: watch-pr.sh <owner/repo> <pr_number> [interval_seconds=60]
# Env:   GATE_CHECKS     — comma-separated reviewer gates (default "codex-review,CodeRabbit").
#                          A head goes GREEN only once all of them have reported on it. Each is
#                          a check name, except `CodeRabbit`, which posts no check: it reports
#                          through its summary comment (`pr_coderabbit`), and a CodeRabbit that
#                          has said it will not review the head (rate-limited, paused, skipped)
#                          counts as reported.
#        GATE_TIMEOUT    — seconds an otherwise-clean head waits for a gate check that has not
#                          reported before going GREEN anyway (default 900 = 15m). A gate check can
#                          go missing entirely on a head (skipped, rate-limited), or sit at pending
#                          for good (a reviewer that reviewed another head), so waiting on it
#                          forever would idle the watch; the timeout bounds that wait, and the GREEN
#                          line names what stayed silent.
#        STALL_AFTER     — seconds a head held by nothing but a red gate check waits before one
#                          STALLED line (default 900 = 15m). Declined findings leave a verdict red
#                          until a fresh review clears it, so a re-review that never started would
#                          hold the head forever with nothing to fire a ROUND or a GREEN.
#        REREQUEST_AFTER — seconds codex-review may read pending before its review is stale
#                          (default 1500 = 25m; the slowest of 735 healthy reviews took 1252 s, and
#                          20 stalled ones never answered). Also the wait after each re-request.
#        REREQUEST_MAX   — re-requests per head before GATE_STUCK (default 2).
#        MAX_FETCH_FAILS — consecutive failed GitHub reads before giving up (default 5).
#        REVIEW_MAX_AGE  — seconds a review-thread read is reused while nothing says it changed
#                          (default 600). The thread read is the watch's only GraphQL call, and
#                          GraphQL is the bucket every agent on the machine shares, so it is
#                          re-asked only when the head or pr_meta's review marker moves. A
#                          thread resolved in the UI without a reply moves neither; this bounds
#                          how late the watch sees it.
#        WATCH_RESUME    — 1 to pick up where the last watch on this PR left off: the threads,
#                          checks, conflict, GREEN and re-requests it already fired on stay fired. A
#                          Monitor is killed after 30 minutes at most, and a re-arm that started
#                          fresh would fire every open thread as a new ROUND and the same head
#                          GREEN again. Any other start forgets that state, so a watch armed anew —
#                          after a stop or a hard fork — sees everything still open as work.
#
# A round fires on the *first* feedback of any kind — the actionable set holding something not in
# the previously fired round: a thread key (id:commentCount, so a reply in an old thread counts), a
# failing check (reset per head, and when it leaves the fail bucket), or a conflict (reset per
# head). Reviewers still pending on the head are named in `pending_gates` rather than held for:
# the round starts on what has landed, and takes a last look for the rest before it pushes.
#
# A head goes GREEN once it has nothing left at all — no unresolved thread, no failing check, none
# still pending but a gate, no conflict — and every gate check has reported on it (or GATE_TIMEOUT
# elapsed waiting for one that never did). Fired once per head, so a quiet PR asks to be merged
# exactly once, unless that GREEN named pending_gates: once they have all reported on a head that is
# still settled, a second GREEN names them in `cleared`, so the merge question held for them goes
# out. Requiring zero unresolved threads (not merely zero *new* ones) is what keeps a GREEN from
# firing mid-round, while the session is still working threads it has seen.
#
# A head goes STALLED when its only failing checks are gate checks and it has no unresolved
# thread, nothing pending and no conflict, for STALL_AFTER. `verdicts=<check>:<n>` counts how
# many times the watch saw that check turn red on this head, so 1 means no re-review has run on it.
# Fired once per verdict.
#
# A codex-review stale at pending gets a REREQUESTED line per re-request, and a GATE_STUCK line once
# the last one has gone stale too or a dispatch failed. `last_verdict` is the status the pending
# row replaced on this head, `none` on a first review. This holds whatever else is open on the
# head, and after its GREEN. A head reading pass or fail is left alone: the rounds own a verdict's
# appeal, and the watch, which has the clock, owns a stale pending.
set -u
REPO=$1; PR=$2; INTERVAL=${3:-60}
GATE_CHECKS=${GATE_CHECKS:-codex-review,CodeRabbit}
GATE_TIMEOUT=${GATE_TIMEOUT:-900}
MAX_FETCH_FAILS=${MAX_FETCH_FAILS:-5}
REVIEW_MAX_AGE=${REVIEW_MAX_AGE:-600}
STALL_AFTER=${STALL_AFTER:-900}
REREQUEST_AFTER=${REREQUEST_AFTER:-1500}
REREQUEST_MAX=${REREQUEST_MAX:-2}
REVIEW_GATE=codex-review
. "$(dirname "${BASH_SOURCE[0]}")/gh-pr-api.sh"

fired_threads=""; fired_fail=""; fired_conflict=0; fired_head=""; fired_green=""; fetch_fails=0
gate_wait_start=0
gate_fail_prev=""; verdict_events=""; stall_start=0; fired_stall=""
green_held=""; review_requests=0; review_request_at=0; fired_stuck=""
threads=""; review_key=""; review_read_at=0
STATE_DIR=${XDG_STATE_HOME:-$HOME/.local/state}/monitor-pr
STATE=$STATE_DIR/${REPO//\//_}-$PR
mkdir -p "$STATE_DIR"
if [ "${WATCH_RESUME:-0}" = 1 ] && [ -r "$STATE" ]; then
  # shellcheck disable=SC1090  # written by save_state below, from this script's own variables
  . "$STATE"
else
  rm -f "$STATE"
fi
# Written whenever a fired_* or stall value changes — on a ROUND, GREEN, STALLED, REREQUESTED or
# GATE_STUCK, when a check leaves the fail bucket, and as a verdict starts its STALL_AFTER — so a
# resumed watch fires again on exactly what this one would have.
saved_state=""
save_state() {
  local now
  now=$(declare -p fired_threads fired_fail fired_conflict fired_head fired_green \
    gate_fail_prev verdict_events stall_start fired_stall green_held review_requests \
    review_request_at fired_stuck)
  [ "$now" = "$saved_state" ] && return
  printf '%s\n' "$now" > "$STATE.tmp" && mv "$STATE.tmp" "$STATE" && saved_state=$now
}
# Codex can acknowledge a request and never answer it, and a fresh one is answered within minutes.
# Only codex-review-manual.yml asks again: the `Codex review request` workflow reads a pending
# status as a review in flight and exits. Each pending row is a request, so the count and the wait
# survive a fresh arm, and review_request_at covers a dispatch that has not written its row yet. A
# gate that reported nothing at all has no pending row, and stays GATE_TIMEOUT's.
recover_review() {
  local requests since verdict asked now why=""
  read -r requests since verdict < <(pr_gate_wait "$REPO" "$PR" "$head" "$REVIEW_GATE" 2>/dev/null)
  [ -n "$requests" ] || return 0
  asked=$((requests - 1))
  [ "$review_requests" -gt "$asked" ] && asked=$review_requests
  [ "$review_request_at" -gt "$since" ] && since=$review_request_at
  now=$(date +%s)
  [ $((now - since)) -ge "$REREQUEST_AFTER" ] || return 0
  if [ "$asked" -lt "$REREQUEST_MAX" ]; then
    if gh workflow run codex-review-manual.yml -f pr="$PR" --repo "$REPO" >/dev/null 2>&1; then
      review_requests=$((asked + 1)); review_request_at=$now
      echo "REREQUESTED head=$head gate=$REVIEW_GATE request=$review_requests/$REREQUEST_MAX"
      save_state
      return 0
    fi
    why=" reason=dispatch-failed"
  fi
  echo "GATE_STUCK head=$head gate=$REVIEW_GATE requests=$asked last_verdict=$verdict$why"
  fired_stuck=$head
  save_state
}
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
  if [ "$state" != "OPEN" ]; then rm -f "$STATE"; echo "PR_CLOSED state=$state"; exit 0; fi

  if [ "$head" != "$fired_head" ]; then
    fired_fail=""; fired_conflict=0; fired_head=$head; gate_wait_start=0
    gate_fail_prev=""; verdict_events=""; stall_start=0
    green_held=""; review_requests=0; review_request_at=0; fired_stuck=""
  fi

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
    if [ "$g" = CodeRabbit ]; then
      # A failed read holds the gate like a silent CodeRabbit, and GATE_TIMEOUT bounds both.
      rabbit=$(pr_coderabbit "$REPO" "$PR" "$head" 2>/dev/null) || rabbit=pending
      [ "$rabbit" = pending ] && pending_gates="${pending_gates:+$pending_gates,}$g"
      continue
    fi
    awk -F'\t' -v n="$g" '$2==n && $1!="pending"{found=1} END{exit !found}' <<<"$checks" \
      || pending_gates="${pending_gates:+$pending_gates,}$g"
  done
  gate_open=1; [ -n "$pending_gates" ] && gate_open=0
  failing=$(awk -F'\t' '$1=="fail"{print $2}' <<<"$checks" | sort)
  # A gate still pending is waited on as a gate, under GATE_TIMEOUT, not as a running check:
  # nothing else would end the wait on one stuck there.
  running=$(awk -F'\t' -v gates=",$GATE_CHECKS," '$1=="pending" && !index(gates, "," $2 ","){print $2}' <<<"$checks" | grep -c .)
  gate_fail=$(grep -Fxf <(printf '%s
' "${gates[@]}") <<<"$failing")
  other_fail=$(grep -vFxf <(printf '%s
' "${gates[@]}") <<<"$failing" | grep .)
  # One line per gate check turning red on this head; a check's line count is its verdict count.
  verdict_events=$(printf '%s
%s
' "$verdict_events"     "$(comm -13 <(printf '%s
' "$gate_fail_prev") <(printf '%s
' "$gate_fail"))" | grep .)
  gate_fail_prev=$gate_fail

  now=$(date +%s)
  if [ "$head $review_marker" != "$review_key" ] || [ $((now - review_read_at)) -ge "$REVIEW_MAX_AGE" ]; then
    if ! fresh=$(pr_open_threads "$REPO" "$PR" 2>&1); then
      fetch_fails=$((fetch_fails + 1))
      if [ "$fetch_fails" -ge "$MAX_FETCH_FAILS" ]; then
        echo "WATCH_ERROR fetch_failures=$fetch_fails last=$(tr '\n' ' ' <<<"$fresh")"
        exit 1
      fi
      sleep "$INTERVAL"; continue
    fi
    threads=$fresh; review_key="$head $review_marker"; review_read_at=$now
  fi
  fetch_fails=0

  new_threads=$(comm -13 <(printf '%s\n' "$fired_threads") <(printf '%s\n' "$threads") | grep -c .)
  # A fired check that left the fail bucket is forgotten, so a re-run or re-review that comes
  # back red on the same head fires again instead of reading as already seen.
  fired_fail=$(comm -12 <(printf '%s\n' "$fired_fail") <(printf '%s\n' "$failing") | grep .)
  save_state
  new_fail=$(comm -13 <(printf '%s\n' "$fired_fail") <(printf '%s\n' "$failing") | grep . | paste -sd, -)
  new_conflict=0; [ "$conflicting" = 1 ] && [ "$fired_conflict" = 0 ] && new_conflict=1
  actionable=0; { [ "$new_threads" -gt 0 ] || [ -n "$new_fail" ] || [ "$new_conflict" = 1 ]; } && actionable=1
  stalled=0
  [ -n "$gate_fail" ] && [ -z "$other_fail" ] && [ -z "$threads" ] && [ "$running" = 0 ]     && [ "$conflicting" = 0 ] && stalled=1
  [ "$actionable" = 1 ] || [ "$stalled" = 0 ] && stall_start=0
  settled=0
  [ -z "$threads" ] && [ -z "$failing" ] && [ "$running" = 0 ] && [ "$conflicting" = 0 ] && settled=1
  [[ ",$pending_gates," == *",$REVIEW_GATE,"* ]] && [ "$fired_stuck" != "$head" ] && recover_review

  if [ "$actionable" = 1 ]; then
    gate_wait_start=0
    echo "ROUND head=$head unresolved=$(grep -c . <<<"$threads") new_threads=$new_threads failing=${failing:+$(paste -sd, - <<<"$failing")} conflicting=$conflicting${pending_gates:+ pending_gates=$pending_gates}"
    fired_threads=$threads; fired_fail=$failing; fired_conflict=$conflicting
    save_state
  elif [ "$settled" = 1 ] && [ "$fired_green" != "$head" ]; then
    # Everything else has settled, so a closed gate is a reviewer that has not reported, posted
    # nothing or stuck at pending; give it GATE_TIMEOUT rather than calling the head green
    # behind its back.
    if [ "$gate_open" = 0 ]; then
      now=$(date +%s)
      [ "$gate_wait_start" = 0 ] && gate_wait_start=$now
      if [ $((now - gate_wait_start)) -lt "$GATE_TIMEOUT" ]; then sleep "$INTERVAL"; continue; fi
    fi
    gate_wait_start=0
    echo "GREEN head=$head${pending_gates:+ pending_gates=$pending_gates}"
    fired_green=$head; green_held=$pending_gates
    save_state
  elif [ "$settled" = 1 ] && [ -n "$green_held" ] && [ "$gate_open" = 1 ]; then
    echo "GREEN head=$head cleared=$green_held"
    green_held=""
    save_state
  elif [ "$stalled" = 1 ]; then
    gate_wait_start=0
    now=$(date +%s)
    [ "$stall_start" = 0 ] && stall_start=$now
    verdicts=$(while IFS= read -r g; do echo "$g:$(grep -cFx "$g" <<<"$verdict_events")"; done       <<<"$gate_fail" | paste -sd, -)
    if [ $((now - stall_start)) -ge "$STALL_AFTER" ] && [ "$fired_stall" != "$head $verdicts" ]; then
      echo "STALLED head=$head verdicts=$verdicts"
      fired_stall="$head $verdicts"
    fi
  else
    gate_wait_start=0
  fi
  save_state
  sleep "$INTERVAL"
done
