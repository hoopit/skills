#!/usr/bin/env bash
# Run the external code reviewer (Codex) on the current branch vs <base>, skipping it
# if it isn't available locally. Deterministic glue only — the always-on independent
# review and the fix/dispute judgment live in the review-gate SKILL.
#
# Usage:  run_external_reviewers.sh <base-branch> [--challenge "<focus text>"]   (base default: master)
# With --challenge, Codex runs its adversarial review — a challenge to the approach and its
# assumptions, weighted on the focus text — instead of its standard review.
# Prints, one per line:  <reviewer>=<ran|error|unavailable>[:<output-file>]
# and, when a reviewer did not run:  <reviewer>_reason=<what went wrong>
# Output files hold each reviewer's raw findings for the skill to read.

BASE=master
CHALLENGE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --challenge) CHALLENGE="${2:-}"; shift 2 ;;
    *) BASE="$1"; shift ;;
  esac
done
# Unique output dir per invocation so concurrent gates (different repos/worktrees,
# run in parallel) never clobber each other's findings. The caller reads the exact
# paths printed below, so the location is opaque to it.
OUT="$(mktemp -d "${TMPDIR:-/tmp}/review-gate.XXXXXX")"

# Resolve codex-companion.mjs (prefer the newest installed cache, else the marketplace clone).
CODEX="$(ls -1 "$HOME"/.claude/plugins/cache/openai-codex/*/scripts/codex-companion.mjs 2>/dev/null | sort -V | tail -1)"
[ -z "$CODEX" ] && CODEX="$(ls -1 "$HOME"/.claude/plugins/marketplaces/openai-codex/plugins/codex/scripts/codex-companion.mjs 2>/dev/null | head -1)"

cx=unavailable
reason="codex-companion.mjs not found under ~/.claude/plugins (codex plugin not installed)"
if [ -n "$CODEX" ]; then
  cx=ran
  if [ -n "$CHALLENGE" ]; then
    node "$CODEX" adversarial-review --scope branch --base "$BASE" --wait "$CHALLENGE" >"$OUT/codex.txt" 2>&1
  else
    node "$CODEX" review --scope branch --base "$BASE" --wait >"$OUT/codex.txt" 2>&1
  fi
  if [ $? != 0 ]; then
    cx=error
    # The last non-empty line is where codex-companion states its failure.
    reason="$(grep -v '^[[:space:]]*$' "$OUT/codex.txt" | tail -1)"
  fi
fi

suffix() { case "$1" in ran|error) printf ':%s' "$2" ;; esac; }
echo "codex=$cx$(suffix "$cx" "$OUT/codex.txt")"
[ "$cx" = ran ] || echo "codex_reason=$reason"
