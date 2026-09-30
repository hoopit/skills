#!/usr/bin/env bash
# Run the external code reviewer (Codex) on the current branch vs <base>, reporting rather
# than failing when it isn't available locally — what an outage means is the caller's call
# (review-gate blocks the pass; monitor-pr works its round but will not recommend a merge). Deterministic glue only — the always-on
# independent review and the fix/dispute judgment live in the review-gate SKILL.
#
# Usage:  run_external_reviewers.sh <base-ref> [--challenge "<focus text>"] [--challenge-only]
#                                   [--model "<codex model>"] [--effort "<reasoning effort>"]
#                                   [--skip-docs-only] [--no-cache]
#                                   [--out <dir>]
# <base-ref> is required — the default branch differs per project, so this script refuses to guess
# rather than name one. Any ref the caller resolved is fine: a `full` pass passes
# origin/<default branch>, a `light` pass the commit its last reviewers saw.
# With --challenge, Codex also runs its adversarial review — a challenge to the approach and
# its assumptions, weighted on the focus text — alongside its standard review, in parallel.
# --challenge-only skips the standard review, for a caller that wants the challenge alone.
# The standard review requires --model and --effort: how hard a branch is read is the caller's
# decision, never a config default it inherits. It runs on the Codex CLI (`codex exec review`),
# the path that takes an effort. The challenge runs on the Codex CLI too, as a `codex exec` turn in a
# read-only sandbox, fed the adversarial prompt and output schema under ../challenge/ (vendored from
# the codex plugin — see ../challenge/NOTICE); its findings are that schema's JSON. It is not
# steerable by the caller: it always runs on CHALLENGE_MODEL at CHALLENGE_EFFORT, whichever caller
# asks, because questioning an approach is what a strong model buys and must not weaken as a side
# effect of a cheaper defect hunt. CODEX_CHALLENGE_MODEL and CODEX_CHALLENGE_EFFORT in the
# environment replace a pinned default Codex no longer accepts.
# Prints, one per line:  codex=<ran|cached|skipped|error|unavailable>[:<output-file>]
#                        codex_challenge=<same>[:<output-file>]   (with --challenge)
# and, for each that did not run:  <name>_reason=<what went wrong>
# Output files hold each reviewer's raw findings for the skill to read; an `error`'s holds its log.
# A run that fails is retried once before it is reported as `error` — a Codex failure is as
# often transient (an auth refresh, a rate limit, a timeout) as it is durable, and a caller
# that treats `error` as gravely as a missing install should not be tripped by a blip.
# `unavailable` is never retried: a CLI that isn't installed stays uninstalled.
#
# A run is keyed on what a reviewer would actually see — reviewer, head tree, base, model, effort,
# focus — and a repeat of that exact key reuses the findings instead of spending Codex again,
# reported as `cached`. It is the same review of the same tree, so a caller reads `cached` exactly as `ran`.
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
EFFORT=""
CHALLENGE_MODEL="${CODEX_CHALLENGE_MODEL:-gpt-6.1-sol}"
CHALLENGE_EFFORT="${CODEX_CHALLENGE_EFFORT:-high}"
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
    --effort)
      EFFORT="${2:-}"
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
[ "$STANDARD" = 1 ] && [ -z "$MODEL" ] && fail "no --model given for the standard review"
[ "$STANDARD" = 1 ] && [ -z "$EFFORT" ] && fail "no --effort given for the standard review"
# Unique output dir per invocation so concurrent gates (different repos/worktrees,
# run in parallel) never clobber each other's findings. The caller reads the exact
# paths printed below, so the location is opaque to it.
if [ -z "$OUT" ]; then
  OUT="$(bash "$(dirname "$0")/gate_dir.sh" open)" || fail "could not create an output dir"
fi
[ -d "$OUT" ] || fail "output dir $OUT does not exist"

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

cache_path() {  # <kind> <model> <effort> <focus>
  [ "$USE_CACHE" = 1 ] || return 1
  [ -n "$HEAD_SHA" ] && [ -n "$BASE_SHA" ] || return 1
  command -v sha256sum >/dev/null 2>&1 || return 1
  local key
  key="$(printf '%s\n' "$1" "$HEAD_SHA" "$BASE_SHA" "$2" "$3" "$4" | sha256sum | cut -d' ' -f1)"
  mkdir -p "$CACHE_DIR" 2>/dev/null || return 1
  printf '%s/%s.txt' "$CACHE_DIR" "$key"
}

# The last non-empty line of a failed run is where Codex states its failure.
last_line() { grep -v '^[[:space:]]*$' "$1" | tail -1; }

CODEX_CLI="$(command -v codex)"
cx=unavailable; cx_reason="codex not found on PATH (Codex CLI not installed)"
ch=unavailable; ch_reason="$cx_reason"

# The findings are Codex's last message, written by -o; the log keeps the rest for a failure's
# reason. A run that exits 0 without writing findings has not reviewed anything.
standard_review() {
  rm -f "$OUT/codex.txt"
  codex exec review --base "$BASE" --model "$MODEL" -c model_reasoning_effort="\"$EFFORT\"" \
    --ephemeral -o "$OUT/codex.txt" </dev/null >"$OUT/codex.log" 2>&1 && [ -s "$OUT/codex.txt" ]
}

# The replacement text is a diff, so a `&` in it must stay a `&` (bash 5.2+ reads it as the match),
# and it is left unquoted because bash before 4.3 keeps quotes around a quoted replacement.
shopt -u patsub_replacement 2>/dev/null
CHALLENGE_DIR="$(cd "$(dirname "$0")/../challenge" && pwd)"

# The diff goes into the prompt when it is small, as the codex plugin's adversarial review does;
# past that, Codex is told to read it itself with read-only git. Either way it runs from the repo root.
challenge_prompt() {
  local merge_base range names log stat diff="" bytes context guidance t
  merge_base="$(git merge-base HEAD "$BASE")" || return 1
  range="$merge_base..HEAD"
  # Every git read is checked: a diff that failed must not reach Codex as an empty one.
  names="$(git diff --name-only "$range")" || return 1
  log="$(git log --oneline --decorate "$range")" || return 1
  stat="$(git diff --stat "$range")" || return 1
  bytes="$(git diff --binary --no-ext-diff --submodule=diff "$range" | wc -c; exit "${PIPESTATUS[0]}")" || return 1
  if [ "$(printf '%s' "$names" | grep -c .)" -le 2 ] && [ "$bytes" -le 262144 ]; then
    diff="$(git diff --binary --no-ext-diff --submodule=diff "$range")" || return 1
  fi
  section() { printf '## %s\n\n%s\n\n' "$1" "${2:-(none)}"; }
  context="$(section "Commit Log" "$log")
$(section "Diff Stat" "$stat")"
  if [ -n "$diff" ]; then
    context="$context
$(section "Branch Diff" "$diff")"
    guidance="Use the repository context below as primary evidence."
  else
    context="$context
$(section "Changed Files" "$names")"
    guidance="The repository context below is a lightweight summary. Inspect the target diff yourself with read-only git commands before finalizing findings."
  fi
  t="$(cat "$CHALLENGE_DIR/prompt.md")" || return 1
  fill() { local k="{{$1}}"; t=${t//"$k"/$2}; }
  fill TARGET_LABEL "branch diff against $BASE (merge-base $merge_base)"
  fill USER_FOCUS "$CHALLENGE"
  fill REVIEW_COLLECTION_GUIDANCE "$guidance"
  fill REVIEW_INPUT "$context"
  printf '%s\n' "$t"
}

# Like the standard review: the findings are the last message, the log keeps the rest. A run that
# exits 0 without a verdict in its findings has not reviewed anything.
challenge_review() {
  rm -f "$OUT/codex-challenge.txt"
  challenge_prompt >"$OUT/codex-challenge-prompt.md" 2>"$OUT/codex-challenge.log" ||
    { echo "could not build the challenge prompt against $BASE" >>"$OUT/codex-challenge.log"; return 1; }
  codex exec --model "$CHALLENGE_MODEL" -c model_reasoning_effort="\"$CHALLENGE_EFFORT\"" \
    --sandbox read-only --cd "$(git rev-parse --show-toplevel)" --output-schema "$CHALLENGE_DIR/schema.json" \
    --ephemeral -o "$OUT/codex-challenge.txt" - <"$OUT/codex-challenge-prompt.md" >"$OUT/codex-challenge.log" 2>&1 &&
    grep -q '"verdict"' "$OUT/codex-challenge.txt" 2>/dev/null
}

if docs_only; then
  skip_reason="no reviewable change in $BASE..HEAD (only docs/ and *.md)"
  [ "$WANT_STANDARD" = 1 ] && { echo "codex=skipped"; echo "codex_reason=$skip_reason"; }
  [ -n "$WANT_CHALLENGE" ] && { echo "codex_challenge=skipped"; echo "codex_challenge_reason=$skip_reason"; }
  exit 0
fi

cx_cache="$(cache_path review "$MODEL" "$EFFORT" "")"
ch_cache="$(cache_path challenge "$CHALLENGE_MODEL" "$CHALLENGE_EFFORT" "$CHALLENGE")"

if [ "$STANDARD" = 1 ] && [ -n "$cx_cache" ] && [ -s "$cx_cache" ]; then
  STANDARD=0; cx=cached; cx_file="$cx_cache"
fi
if [ -n "$CHALLENGE" ] && [ -n "$ch_cache" ] && [ -s "$ch_cache" ]; then
  CHALLENGE=""; ch=cached; ch_file="$ch_cache"
fi

[ -n "$CODEX_CLI" ] || STANDARD=0
[ -n "$CODEX_CLI" ] || CHALLENGE=""
if [ "$STANDARD" = 1 ] || [ -n "$CHALLENGE" ]; then
  if [ "$STANDARD" = 1 ]; then
    standard_review &
    cx_pid=$!
  fi
  if [ -n "$CHALLENGE" ]; then
    challenge_review &
    ch_pid=$!
  fi
  # Retries run after the parallel phase, and only for a run that failed.
  if [ "$STANDARD" = 1 ]; then
    cx=ran
    wait "$cx_pid" || standard_review ||
      { cx=error; cx_reason="$(last_line "$OUT/codex.log") [after one retry]"; }
  fi
  if [ -n "$CHALLENGE" ]; then
    ch=ran
    wait "$ch_pid" || challenge_review ||
      { ch=error; ch_reason="$(last_line "$OUT/codex-challenge.log") [after one retry]"; }
  fi
fi

# A fresh success seeds the key it was keyed on; a failure never does.
[ "$cx" = ran ] && [ -n "$cx_cache" ] && cp "$OUT/codex.txt" "$cx_cache" 2>/dev/null
[ "$ch" = ran ] && [ -n "$ch_cache" ] && cp "$OUT/codex-challenge.txt" "$ch_cache" 2>/dev/null

suffix() { case "$1" in ran|error) printf ':%s' "$2" ;; cached) printf ':%s' "$3" ;; esac; }
if [ "$WANT_STANDARD" = 1 ]; then
  cx_out="$OUT/codex.txt"; [ "$cx" = error ] && cx_out="$OUT/codex.log"
  echo "codex=$cx$(suffix "$cx" "$cx_out" "${cx_file:-}")"
  case "$cx" in ran|cached) ;; *) echo "codex_reason=$cx_reason" ;; esac
fi
if [ -n "$WANT_CHALLENGE" ]; then
  ch_out="$OUT/codex-challenge.txt"; [ "$ch" = error ] && ch_out="$OUT/codex-challenge.log"
  echo "codex_challenge=$ch$(suffix "$ch" "$ch_out" "${ch_file:-}")"
  case "$ch" in ran|cached) ;; *) echo "codex_challenge_reason=$ch_reason" ;; esac
fi
