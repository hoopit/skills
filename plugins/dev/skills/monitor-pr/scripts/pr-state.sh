#!/usr/bin/env bash
# Print a PR's actionable state, for a round's last look: run it once when the round starts and
# again just before the push, and `diff` the two to see what landed while the round worked.
# Usage: pr-state.sh <owner/repo> <pr_number>
# Prints three lines:
#   threads=<id:commentCount,...>  — unresolved review threads, sorted; the count makes a reply
#                                    to an already-seen thread a change
#   failing=<name,...>             — checks in the fail bucket, sorted
#   conflicting=0|1
# Same keys watch-pr.sh fires ROUND lines on, so the two agree on what counts as new.
set -u
. "$(dirname "${BASH_SOURCE[0]}")/gh-pr-api.sh"
REPO=$1; PR=$2

meta=$(pr_meta "$REPO" "$PR") || { echo "pr-state: could not read the PR" >&2; exit 1; }
read -r _state conflicting head _ <<<"$meta"

# A failed read must not print a clean state: the caller diffs two of these, and empty
# threads would read as "everything got resolved while the round worked".
review=$(pr_review_state "$REPO" "$PR") || { echo "pr-state: could not read review threads" >&2; exit 1; }
threads=$(grep -v '^review=' <<<"$review" | paste -sd, -)
checks=$(pr_checks "$REPO" "$head") || { echo "pr-state: could not read checks" >&2; exit 1; }
failing=$(awk -F'\t' '$1=="fail"{print $2}' <<<"$checks" | sort | paste -sd, -)

echo "threads=$threads"
echo "failing=$failing"
echo "conflicting=$conflicting"
