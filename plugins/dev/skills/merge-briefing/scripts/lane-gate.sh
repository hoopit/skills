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
# The size limits count no test file: a fixture or a snapshot is not code a human has to
# read. A test file is anything under a `tests/`, `test/` or `__snapshots__/` directory, or
# named `*_test.*`, `test_*.*` or `*.snap`, and it is still read against the guarded paths.
# LANE_MAX_LINES and LANE_MAX_FILES replace the default limits; the merge briefing sets them
# from a repo's Lane limits line.
#
# REST for everything but the closing issues, which only GraphQL exposes. The files read
# page by page, as many pages as the PR's own file count.
set -u
export MISE_QUIET=1
export REPO=$1
PR=$2; GUARDED=${3:-}
MAX_LINES=${LANE_MAX_LINES:-400}; MAX_FILES=${LANE_MAX_FILES:-15}
for limit in "$MAX_LINES" "$MAX_FILES"; do
  [[ $limit =~ ^(0|[1-9][0-9]*)$ ]] \
    || { echo "gate=human reason=lane limit \`$limit\` is not a whole number"; exit 0; }
done
TEST_FILE='(^|/)(tests?|__snapshots__)/|(^|/)test_[^/]*\.[^/]*$|_test\.[^/]*$|\.snap$'
reasons=()

pr=$(gh api "repos/$REPO/pulls/$PR" --jq '[.changed_files, .user.type,
  (([.requested_reviewers[].login] + [.requested_teams[].slug]) | join(" "))] | @tsv') \
  || { echo "gate=human reason=could not read the PR"; exit 0; }
IFS=$'\t' read -r changed author_type asked <<<"$pr"

# A rename is judged under both names: moving a file out of a guarded path touches it.
paths="" lines=0 files=0
for (( page = 1; page <= (changed + 99) / 100; page++ )); do
  rows=$(gh api "repos/$REPO/pulls/$PR/files?per_page=100&page=$page" \
    --jq '.[] | [.filename, .changes, (.previous_filename // "")] | @tsv') \
    || { echo "gate=human reason=could not read the changed files"; exit 0; }
  while IFS=$'\t' read -r name changes previous; do
    [[ -n $name ]] || continue
    paths+=$name$'\n'
    [[ -n $previous ]] && paths+=$previous$'\n'
    [[ $name =~ $TEST_FILE ]] && continue
    (( lines += changes, files += 1 ))
  done <<<"$rows"
done
(( lines > MAX_LINES )) && reasons+=("$lines changed lines outside tests, over $MAX_LINES")
(( files > MAX_FILES )) && reasons+=("$files changed files outside tests, over $MAX_FILES")
[[ $author_type == Bot ]] && reasons+=("a bot opened it")
[[ -n $asked ]] && reasons+=("a review is still requested of $asked")

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
