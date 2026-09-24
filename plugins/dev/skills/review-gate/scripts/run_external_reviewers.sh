#!/usr/bin/env bash
# Run the external code reviewer (Codex) on the current branch vs <base>, reporting rather
# than failing when it isn't available locally — what an outage means is the caller's call
# (review-gate blocks the pass; monitor-pr works its round but will not recommend a merge). Deterministic glue only — the always-on
# independent review and the fix/dispute judgment live in the review-gate SKILL.
#
# Usage:  run_external_reviewers.sh <base-ref> [--challenge "<focus text>"] [--challenge-only]
#                                   [--model "<codex model>"] [--skip-docs-only] [--no-cache]
#                                   [--out <dir>]
# <base-ref> is required — the default branch differs per project, so this script refuses to guess
# rather than name one. Any ref the caller resolved is fine: a `full` pass passes
# origin/<default branch>, a `light` pass the commit its last reviewers saw.
# With --challenge, Codex also runs its adversarial review — a challenge to the approach and
# its assumptions, weighted on the focus text — alongside its standard review, in parallel.
# --challenge-only skips the standard review, for a caller that wants the challenge alone.
# --model picks the Codex model for the standard review; empty or absent leaves Codex on the model
# its own config names, which is the normal case. The challenge is deliberately not steerable:
# questioning an approach is what a strong model buys, so downgrading it is never a side effect of
# downgrading the defect hunt. Reasoning effort has no equivalent for either: codex-companion
# accepts --effort only on `task`, and the standard review runs through `review/start`, which
# carries no effort at all — both reviews take it from ~/.codex/config.toml
# (model_reasoning_effort), so that file is where to change it.
# Prints, one per line:  codex=<ran|error|unavailable>[:<output-file>]
#                        codex_challenge=<ran|error|unavailable>[:<output-file>]   (with --challenge)
# and, for each that did not run:  <name>_reason=<what went wrong>
# Output files hold each reviewer's raw findings for the skill to read.
# A run that fails is retried once before it is reported as `error` — a Codex failure is as
# often transient (an auth refresh, a rate limit, a timeout) as it is durable, and a caller
# that treats `error` as gravely as a missing install should not be tripped by a blip.
# `unavailable` is never retried: a plugin that isn't installed stays uninstalled.
#
# A run is keyed on what a reviewer would actually see — reviewer, head tree, base, model, focus —
# and a repeat of that exact key reuses the findings instead of spending Codex again, reported as
# `cached`. It is the same review of the same tree, so a caller reads `cached` exactly as `ran`.
# What it removes is re-asking a question nothing changed the answer to: a pass re-run after a
# block that was settled without touching the code, an interrupted round re-armed. A second run
# would still be a second sample, which does find what a first missed — that, and nothing more, is
# what reuse trades away. --no-cache forces a fresh run.
#
# --skip-docs-only reports `skipped` instead of running, when the diff touches nothing but *.md and
# docs/. It belongs on a narrowed pass whose diff is the change under review (a caller's later
# round over its own fix commits), NOT on a pass over a whole branch: in a docs or skills repo the
# Markdown *is* the code, and a whole-branch skip would quietly leave that repo with no external
# reviewer at all. `skipped` is not `unavailable` — nothing was there to review.
#
# --out writes the findings into a gate dir the caller already holds, so the caller's teardown
# takes them with it. Without it the script opens a gate dir of its own (gate_dir.sh), which the
# plugin's session hooks remove.

BASE=""
CHALLENGE=""
CHALLENGE_MISSING=""
MODEL=""
SKIP_DOCS_ONLY=""
OUT=""
USE_CACHE=1
STANDARD=1
while [ $# -gt 0 ]; do
  case "$1" in
    --challenge)
      CHALLENGE="${2:-}"; [ -n "$CHALLENGE" ] || CHALLENGE_MISSING=1
      shift; [ $# -gt 0 ] && shift ;;
    --challenge-only) STANDARD=0; shift ;;
    --skip-docs-only) SKIP_DOCS_ONLY=1; shift ;;
    --no-cache) USE_CACHE=0; shift ;;
    --out)
      OUT="${2:-}"
      shift; [ $# -gt 0 ] && shift ;;
    --model)
      MODEL="${2:-}"
      shift; [ $# -gt 0 ] && shift ;;
    -*) BAD_FLAG="$1"; shift ;;
    *) BASE="$1"; shift ;;
  esac
done
[ -n "$CHALLENGE" ] || STANDARD=1   # nothing else to run, so the standard review it is
# What the caller asked for. STANDARD/CHALLENGE below say what still has to be *run*, which a
# cache hit empties; these two stay the answer to what gets reported.
WANT_STANDARD="$STANDARD"
WANT_CHALLENGE="$CHALLENGE"

# Refuse rather than guess, in whichever key the caller is reading.
fail() {
  [ "$STANDARD" = 1 ] && { echo "codex=error"; echo "codex_reason=$1"; }
  [ -n "$CHALLENGE$CHALLENGE_MISSING" ] && { echo "codex_challenge=error"; echo "codex_challenge_reason=$1"; }
  exit 2
}
[ -n "${BAD_FLAG:-}" ] && fail "unknown flag $BAD_FLAG"
[ -n "$CHALLENGE_MISSING" ] && fail "--challenge given no focus text"
[ -n "$BASE" ] || fail "no base ref given (pass the base the caller resolved)"
# Unique output dir per invocation so concurrent gates (different repos/worktrees,
# run in parallel) never clobber each other's findings. The caller reads the exact
# paths printed below, so the location is opaque to it.
if [ -z "$OUT" ]; then
  OUT="$(bash "$(dirname "$0")/gate_dir.sh" open)" || fail "could not create an output dir"
fi
[ -d "$OUT" ] || fail "output dir $OUT does not exist"

# An empty MODEL must expand to no arguments at all, so build the flag as an array. It goes to the
# standard review alone — see --model above.
MODEL_ARGS=()
[ -n "$MODEL" ] && MODEL_ARGS=(--model "$MODEL")

# Everything below keys on the tree as git sees it. Outside a repo there is nothing to key on, so
# reuse and the docs-only skip both fail open into a plain run.
HEAD_SHA="$(git rev-parse HEAD 2>/dev/null)"
BASE_SHA="$(git rev-parse "$BASE" 2>/dev/null)"

# Only the diff the reviewers are given counts — a branch may carry docs commits either side of it.
docs_only() {
  [ -n "$SKIP_DOCS_ONLY" ] || return 1
  [ -n "$HEAD_SHA" ] && [ -n "$BASE_SHA" ] || return 1
  local files
  files="$(git diff --name-only "$BASE_SHA...$HEAD_SHA" 2>/dev/null)"
  [ -n "$files" ] || return 1
  ! printf '%s\n' "$files" | grep -qvE '(^|/)docs/|\.md$'
}

CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/review-gate"
# Keys are immutable (they name a tree), so age is the only thing that retires one.
[ "$USE_CACHE" = 1 ] && find "$CACHE_DIR" -type f -mtime +14 -delete 2>/dev/null

cache_path() {  # <kind> <focus>
  [ "$USE_CACHE" = 1 ] || return 1
  [ -n "$HEAD_SHA" ] && [ -n "$BASE_SHA" ] || return 1
  command -v sha256sum >/dev/null 2>&1 || return 1
  local key
  key="$(printf '%s\n' "$1" "$HEAD_SHA" "$BASE_SHA" "$MODEL" "$2" | sha256sum | cut -d' ' -f1)"
  mkdir -p "$CACHE_DIR" 2>/dev/null || return 1
  printf '%s/%s.txt' "$CACHE_DIR" "$key"
}

# Resolve codex-companion.mjs (prefer the newest installed cache, else the marketplace clone).
CODEX="$(ls -1 "$HOME"/.claude/plugins/cache/openai-codex/*/*/scripts/codex-companion.mjs 2>/dev/null | sort -V | tail -1)"
[ -z "$CODEX" ] && CODEX="$(ls -1 "$HOME"/.claude/plugins/marketplaces/openai-codex/plugins/codex/scripts/codex-companion.mjs 2>/dev/null | head -1)"

missing="codex-companion.mjs not found under ~/.claude/plugins (codex plugin not installed)"
# The last non-empty line of a failed run is where codex-companion states its failure.
last_line() { grep -v '^[[:space:]]*$' "$1" | tail -1; }

cx=unavailable; cx_reason="$missing"
ch=unavailable; ch_reason="$missing"

if docs_only; then
  skip_reason="no reviewable change in $BASE..HEAD (only docs/ and *.md)"
  [ "$WANT_STANDARD" = 1 ] && { echo "codex=skipped"; echo "codex_reason=$skip_reason"; }
  [ -n "$WANT_CHALLENGE" ] && { echo "codex_challenge=skipped"; echo "codex_challenge_reason=$skip_reason"; }
  exit 0
fi

cx_cache="$(cache_path review "")"
ch_cache="$(cache_path challenge "$CHALLENGE")"

if [ "$STANDARD" = 1 ] && [ -n "$cx_cache" ] && [ -s "$cx_cache" ]; then
  STANDARD=0; cx=cached; cx_file="$cx_cache"
fi
if [ -n "$CHALLENGE" ] && [ -n "$ch_cache" ] && [ -s "$ch_cache" ]; then
  CHALLENGE=""; ch=cached; ch_file="$ch_cache"
fi

if [ -n "$CODEX" ] && { [ "$STANDARD" = 1 ] || [ -n "$CHALLENGE" ]; }; then
  if [ "$STANDARD" = 1 ]; then
    node "$CODEX" review --scope branch --base "$BASE" "${MODEL_ARGS[@]}" --wait >"$OUT/codex.txt" 2>&1 &
    cx_pid=$!
  fi
  if [ -n "$CHALLENGE" ]; then
    node "$CODEX" adversarial-review --scope branch --base "$BASE" --wait "$CHALLENGE" >"$OUT/codex-challenge.txt" 2>&1 &
    ch_pid=$!
  fi
  # Retries run after the parallel phase, and only for a run that failed.
  if [ "$STANDARD" = 1 ]; then
    cx=ran
    wait "$cx_pid" || node "$CODEX" review --scope branch --base "$BASE" "${MODEL_ARGS[@]}" --wait \
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

# A fresh success seeds the key it was keyed on; a failure never does.
[ "$cx" = ran ] && [ -n "$cx_cache" ] && cp "$OUT/codex.txt" "$cx_cache" 2>/dev/null
[ "$ch" = ran ] && [ -n "$ch_cache" ] && cp "$OUT/codex-challenge.txt" "$ch_cache" 2>/dev/null

suffix() { case "$1" in ran|error) printf ':%s' "$2" ;; cached) printf ':%s' "$3" ;; esac; }
if [ "$WANT_STANDARD" = 1 ]; then
  echo "codex=$cx$(suffix "$cx" "$OUT/codex.txt" "${cx_file:-}")"
  case "$cx" in ran|cached) ;; *) echo "codex_reason=$cx_reason" ;; esac
fi
if [ -n "$WANT_CHALLENGE" ]; then
  echo "codex_challenge=$ch$(suffix "$ch" "$OUT/codex-challenge.txt" "${ch_file:-}")"
  case "$ch" in ran|cached) ;; *) echo "codex_challenge_reason=$ch_reason" ;; esac
fi
