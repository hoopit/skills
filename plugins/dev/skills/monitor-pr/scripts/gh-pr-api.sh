#!/usr/bin/env bash
# Shared GitHub reads for the monitor-pr scripts. Source it; don't run it.
#
# REST and GraphQL are metered in separate hourly buckets, and gh's porcelain
# (`gh pr view`, `gh pr checks`) is GraphQL underneath — so a 60 s watch built on it
# spends three GraphQL calls a minute per PR, and a machine running several agents
# exhausts the GraphQL bucket while the REST one sits idle. Everything REST can answer
# is asked over REST here. Only review-thread resolution stays on GraphQL, because no
# REST endpoint exposes it. A poller spends even that one only when `pr_meta`'s review
# marker says the threads can have changed.
#
# mise prints its activation banner to stdout on every tool invocation, which would land
# inside these command substitutions and corrupt every parse below.
export MISE_QUIET=1

# pr_meta <owner/repo> <pr> — prints "<state> <conflicting> <head_sha> <review_marker>".
#   state          OPEN | CLOSED | MERGED
#   conflicting    1 only once GitHub has computed the merge and found it dirty. While
#                  that computation is in flight `mergeable` is null and this reads 0,
#                  the same way GraphQL's UNKNOWN did; the next poll sees the answer.
#   review_marker  "<review_comment_count>@<updated_at>". A new thread or a reply raises
#                  the count, and a submitted review moves updated_at, so a marker that
#                  has not moved means `pr_open_threads` would answer what it answered
#                  last time — except a thread resolved or unresolved without a comment,
#                  which moves neither. Read it with `read -r state conflicting head _`.
pr_meta() {
  gh api "repos/$1/pulls/$2" --jq '
    (if .merged then "MERGED" elif .state == "closed" then "CLOSED" else "OPEN" end)
    + " " + (if .mergeable == false then "1" else "0" end)
    + " " + .head.sha
    + " " + (.review_comments | tostring) + "@" + .updated_at'
}

# pr_checks <owner/repo> <head_sha> — prints "<bucket>\t<name>\t<link>" per check.
# Reads check runs and commit statuses both: external CI reports as a status, not a
# run, and on a Hoopit PR the CodeRabbit and codex-review reviewers are statuses.
# Buckets carry the same names `gh pr checks --json bucket` used: pass, fail, pending,
# skipping, cancel.
#
# One name can come back several times — a re-run, or two workflows defining the same job
# name — so the newest run wins. Downstream reads a check by name, so a name has to answer
# with one state, and it has to be the current one: a stale failed re-run left in would pin
# the PR red forever. A run with no timestamp is one GitHub has only just created, so it
# sorts newest — better to read a check as pending than as an older run's failure.
pr_checks() {
  local runs statuses
  runs=$(gh api --paginate --slurp "repos/$1/commits/$2/check-runs?per_page=100") || return 1
  statuses=$(gh api --paginate --slurp "repos/$1/commits/$2/status?per_page=100") || return 1
  jq -r '[.[].check_runs[]] | group_by(.name) | map(max_by(.started_at // "9999")) | .[]
    | [(
      if .status != "completed" then "pending"
      elif .conclusion == "success" then "pass"
      elif .conclusion == "neutral" or .conclusion == "skipped" then "skipping"
      elif .conclusion == "cancelled" then "cancel"
      else "fail" end), .name, (.html_url // "")] | @tsv' <<<"$runs"
  jq -r '[.[].statuses[]] | group_by(.context) | map(max_by(.updated_at // "9999")) | .[]
    | [(
      if .state == "pending" then "pending"
      elif .state == "success" then "pass"
      else "fail" end), .context, (.target_url // "")] | @tsv' <<<"$statuses"
}

# pr_open_threads <owner/repo> <pr> — the one GraphQL call. Prints one
# `<thread_id>:<comment_count>` line per unresolved thread, sorted. The comment count is
# what makes a reply to an already-seen thread a change.
#
# GraphQL because a review thread's resolved flag appears in no REST response. The PR's
# review decision is deliberately not read: no Hoopit repo requires an approval, so it
# never says anything a merge could wait on.
PR_REVIEW_QUERY='query($owner:String!,$name:String!,$pr:Int!,$endCursor:String){
  repository(owner:$owner,name:$name){ pullRequest(number:$pr){
    reviewThreads(first:100,after:$endCursor){
      pageInfo{hasNextPage endCursor}
      nodes{ id isResolved comments{totalCount} }
    } } } }'

pr_open_threads() {
  local raw
  raw=$(gh api graphql --paginate -f query="$PR_REVIEW_QUERY" \
          -F owner="${1%/*}" -F name="${1#*/}" -F pr="$2") || return 1
  # --paginate prints one document per page; jq reads the node arrays across all of them.
  jq -r '.data.repository.pullRequest.reviewThreads.nodes[]
         | select(.isResolved | not) | "\(.id):\(.comments.totalCount)"' <<<"$raw" | sort
}
