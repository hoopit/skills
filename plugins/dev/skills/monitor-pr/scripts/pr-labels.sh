#!/usr/bin/env bash
# Add and remove labels on a PR over REST.
# Usage: pr-labels.sh <owner/repo> <pr> [+label | -label]...
#   pr-labels.sh hoopit/api 123 +agent-working -ready-for-review
#
# `gh pr edit --add-label/--remove-label` is GraphQL underneath — three requests an edit —
# and every agent on the machine shares that bucket. A label is an issue label in REST,
# so the issues endpoints answer it completely. Removing a label the PR does not carry is
# not an error: the caller states the labels it wants gone, not the ones it saw.
# Exits non-zero if any edit failed, after trying them all.
set -u
export MISE_QUIET=1
REPO=$1; PR=$2; shift 2
rc=0
for arg in "$@"; do
  name=${arg:1}
  case $arg in
    +*) gh api -X POST "repos/$REPO/issues/$PR/labels" -f "labels[]=$name" --silent || rc=1 ;;
    -*) out=$(gh api -X DELETE "repos/$REPO/issues/$PR/labels/$(jq -rn --arg n "$name" '$n|@uri')" 2>&1 >/dev/null) \
          || grep -q 'HTTP 404' <<<"$out" || { echo "$out" >&2; rc=1; } ;;
    *) echo "pr-labels: '$arg' needs a + or - prefix" >&2; rc=2 ;;
  esac
done
exit $rc
