#!/usr/bin/env bash
# Run the external code reviewer (Codex) on the current branch vs <base>, reporting rather
# than failing when it isn't available locally — what an outage means is the caller's call
# (review-gate blocks the pass; monitor-pr works its round but will not recommend a merge). Deterministic glue only — the always-on
# independent review and the fix/dispute judgment live in the review-gate SKILL.
#
# Usage:  run_external_reviewers.sh <base-branch> [--challenge "<focus text>"] [--challenge-only]
# (base default: master)
# With --challenge, Codex also runs its adversarial review — a challenge to the approach and
# its assumptions, weighted on the focus text — alongside its standard review, in parallel.
# --challenge-only skips the standard review, for a caller that wants the challenge alone.
# Prints, one per line:  codex=<ran|error|unavailable>[:<output-file>]
#                        codex_challenge=<ran|error|unavailable>[:<output-file>]   (with --challenge)
# and, for each that did not run:  <name>_reason=<what went wrong>
# Output files hold each reviewer's raw findings for the skill to read.
# A run that fails is retried once before it is reported as `error` — a Codex failure is as
# often transient (an auth refresh, a rate limit, a timeout) as it is durable, and a caller
# that treats `error` as gravely as a missing install should not be tripped by a blip.
# `unavailable` is never retried: a plugin that isn't installed stays uninstalled.

BASE=master
CHALLENGE=""
STANDARD=1
while [ $# -gt 0 ]; do
  case "$1" in
    --challenge) CHALLENGE="${2:-}"; shift 2 ;;
    --challenge-only) STANDARD=0; shift ;;
    *) BASE="$1"; shift ;;
  esac
done
[ -n "$CHALLENGE" ] || STANDARD=1   # nothing else to run, so the standard review it is
# Unique output dir per invocation so concurrent gates (different repos/worktrees,
# run in parallel) never clobber each other's findings. The caller reads the exact
# paths printed below, so the location is opaque to it.
OUT="$(mktemp -d "${TMPDIR:-/tmp}/review-gate.XXXXXX")"

# Resolve codex-companion.mjs (prefer the newest installed cache, else the marketplace clone).
CODEX="$(ls -1 "$HOME"/.claude/plugins/cache/openai-codex/*/scripts/codex-companion.mjs 2>/dev/null | sort -V | tail -1)"
[ -z "$CODEX" ] && CODEX="$(ls -1 "$HOME"/.claude/plugins/marketplaces/openai-codex/plugins/codex/scripts/codex-companion.mjs 2>/dev/null | head -1)"

missing="codex-companion.mjs not found under ~/.claude/plugins (codex plugin not installed)"
# The last non-empty line of a failed run is where codex-companion states its failure.
last_line() { grep -v '^[[:space:]]*$' "$1" | tail -1; }

cx=unavailable; cx_reason="$missing"
ch=unavailable; ch_reason="$missing"
if [ -n "$CODEX" ]; then
  if [ "$STANDARD" = 1 ]; then
    node "$CODEX" review --scope branch --base "$BASE" --wait >"$OUT/codex.txt" 2>&1 &
    cx_pid=$!
  fi
  if [ -n "$CHALLENGE" ]; then
    node "$CODEX" adversarial-review --scope branch --base "$BASE" --wait "$CHALLENGE" >"$OUT/codex-challenge.txt" 2>&1 &
    ch_pid=$!
  fi
  # Retries run after the parallel phase, and only for a run that failed.
  if [ "$STANDARD" = 1 ]; then
    cx=ran
    wait "$cx_pid" || node "$CODEX" review --scope branch --base "$BASE" --wait \
      >"$OUT/codex.txt" 2>&1 ||
      { cx=error; cx_reason="$(last_line "$OUT/codex.txt") [after one retry]"; }
  fi
  if [ -n "$CHALLENGE" ]; then
    ch=ran
    wait "$ch_pid" || node "$CODEX" adversarial-review --scope branch --base "$BASE" --wait \
      "$CHALLENGE" >"$OUT/codex-challenge.txt" 2>&1 ||
      { ch=error; ch_reason="$(last_line "$OUT/codex-challenge.txt") [after one retry]"; }
  fi
fi

suffix() { case "$1" in ran|error) printf ':%s' "$2" ;; esac; }
if [ "$STANDARD" = 1 ]; then
  echo "codex=$cx$(suffix "$cx" "$OUT/codex.txt")"
  [ "$cx" = ran ] || echo "codex_reason=$cx_reason"
fi
if [ -n "$CHALLENGE" ]; then
  echo "codex_challenge=$ch$(suffix "$ch" "$OUT/codex-challenge.txt")"
  [ "$ch" = ran ] || echo "codex_challenge_reason=$ch_reason"
fi
