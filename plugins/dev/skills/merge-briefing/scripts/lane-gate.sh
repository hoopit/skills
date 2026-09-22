#!/usr/bin/env bash
# The mechanical half of the merge briefing's Lane line: what code settles about a PR
# before anyone weighs its risk. Prints one line —
#   gate=pass
#   gate=human reason=<a>; <b>; ...
# Usage: lane-gate.sh <owner/repo> <pr> [<guarded-path regexes, comma-separated>]
#
# Every failing check is named, not only the first, so the briefing says everything a
# human is being asked to look at. `.github/` is guarded in every repo: workflow and CI
# definitions decide what every later PR is checked by. A read that fails is `human` with
# the failure as its reason — a gate that cannot see the PR passes nothing.
#
# REST for everything but the closing issues, which only GraphQL exposes. The files read
# pages, bounded by the PR's own file count; a PR over MAX_FILES has already failed the
# gate, and the paths are still read so the reason names the guarded ones too.
set -u
export MISE_QUIET=1
export REPO=$1
PR=$2; GUARDED=${3:-}
MAX_LINES=${LANE_MAX_LINES:-400}; MAX_FILES=${LANE_MAX_FILES:-15}
reasons=()

pr=$(gh api "repos/$REPO/pulls/$PR" --jq '[(.additions + .deletions), .changed_files, .user.type,
  (([.requested_reviewers[].login] + [.requested_teams[].slug]) | join(" "))] | @tsv') \
  || { echo "gate=human reason=could not read the PR"; exit 0; }
IFS=$'\t' read -r lines files author_type asked <<<"$pr"
(( lines > MAX_LINES )) && reasons+=("$lines changed lines, over $MAX_LINES")
(( files > MAX_FILES )) && reasons+=("$files changed files, over $MAX_FILES")
[[ $author_type == Bot ]] && reasons+=("a bot opened it")
[[ -n $asked ]] && reasons+=("a review is still requested of $asked")

# A rename is judged under both names: moving a file out of a guarded path touches it.
paths=$(gh api "repos/$REPO/pulls/$PR/files?per_page=100" --paginate \
  --jq '.[] | .filename, (.previous_filename // empty)') \
  || { echo "gate=human reason=could not read the changed files"; exit 0; }
IFS=, read -ra patterns <<<"^\\.github/${GUARDED:+,$GUARDED}"
for p in "${patterns[@]}"; do
  p=${p#"${p%%[![:space:]]*}"}; p=${p%"${p##*[![:space:]]}"}
  [[ -n $p ]] || continue
  if hit=$(grep -E -m1 -- "$p" <<<"$paths"); then
    reasons+=("\`$hit\` is a guarded path (\`$p\`)")
  fi
done

# Without an issue there is nothing to weigh the diff against but the author's own
# description of it. Same-repository only: that is what the board automation reads.
closing=$(gh api graphql -F p="$PR" -f o="${REPO%/*}" -f n="${REPO#*/}" -f query='
  query($o:String!,$n:String!,$p:Int!){ repository(owner:$o,name:$n){ pullRequest(number:$p){
    closingIssuesReferences(first:10){ nodes{ repository{ nameWithOwner } } } } } }' \
  --jq '[.data.repository.pullRequest.closingIssuesReferences.nodes[]
         | select(.repository.nameWithOwner == env.REPO)] | length') \
  || { echo "gate=human reason=could not read the closing issues"; exit 0; }
(( closing == 0 )) && reasons+=("it closes no issue in this repository")

if (( ${#reasons[@]} )); then
  out="gate=human reason="
  for r in "${reasons[@]}"; do out+="$r; "; done
  echo "${out%; }"
else
  echo "gate=pass"
fi
