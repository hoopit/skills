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
REPO=$1; PR=$2
OWNER=${REPO%/*}; NAME=${REPO#*/}

QUERY='query($owner:String!,$name:String!,$pr:Int!,$endCursor:String){
  repository(owner:$owner,name:$name){ pullRequest(number:$pr){
    reviewThreads(first:100,after:$endCursor){
      pageInfo{hasNextPage endCursor}
      nodes{ id isResolved comments{totalCount} }
    } } } }'

threads=$(gh api graphql --paginate -f query="$QUERY" \
    -F owner="$OWNER" -F name="$NAME" -F pr="$PR" \
    --jq '.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved|not) | "\(.id):\(.comments.totalCount)"' \
    | sort | paste -sd, -)
failing=$(gh pr checks "$PR" --repo "$REPO" --json name,bucket \
    --jq '.[] | select(.bucket=="fail") | .name' 2>/dev/null | sort | paste -sd, -)
mergeable=$(gh pr view "$PR" --repo "$REPO" --json mergeable --jq .mergeable)
conflicting=0; [ "$mergeable" = CONFLICTING ] && conflicting=1

echo "threads=$threads"
echo "failing=$failing"
echo "conflicting=$conflicting"
