#!/usr/bin/env bash
# The mechanical half of the merge briefing's Lane line: what code settles about a PR
# before anyone weighs its risk. Prints one line —
#   gate=pass
#   gate=human reason=<a>; <b>; ...
# Usage: lane-gate.sh <owner/repo> <pr> [<AGENTS.md guarded-path regexes, comma-separated>]
#
# The guarded paths are the `guarded` list of the base's `.github/review-judgement.json`, the
# list the team-review gate holds a PR by, matched as that gate matches them: Python regexes,
# searched against each path. Like that gate it reads the base's copy, so a PR cannot edit its
# own list, and it adds agent-read Markdown whatever the list says. The argument counts only in
# a repo without that file; leave it off when the repo names no list at all, and pass '' for an
# empty one.
#
# Every failing check is named, not only the first, so the briefing says everything a
# human is being asked to look at. `.github/` is guarded in every repo: workflow and CI
# definitions decide what every later PR is checked by. A read that fails is `human` with
# the failure as its reason — a gate that cannot see the PR passes nothing.
#
# The files are read page by page, as many pages as the PR's own file count. A listing short of
# that count is a read that failed — GitHub serves at most 3,000 of a PR's files — and so is one
# the PR's head or base moved under, since a push between pages can swap a file without changing
# the count.
set -u
export MISE_QUIET=1
export REPO=$1
PR=$2; GUARDED=${3-}
REVISION='"\(.head.sha)..\(.base.sha)"'
# ALWAYS_GUARDED in hoopit/workflows' judgement.py, past its `^\.github/`: change them together.
AGENT_READ='(^|/)(AGENTS(\.override)?|CLAUDE(\.local)?)\.md$|(^|/)(\.agents|\.claude|docs/agents)/.*\.md$'
reasons=()

pr=$(gh api "repos/$REPO/pulls/$PR" --jq "[.changed_files, $REVISION, .user.type,
  (([.requested_reviewers[].login] + [.requested_teams[].slug]) | join(\" \"))] | @tsv") \
  || { echo "gate=human reason=could not read the PR"; exit 0; }
IFS=$'\t' read -r changed revision author_type asked <<<"$pr"

# A rename is judged under both names: moving a file out of a guarded path touches it.
paths="" seen=0
for (( page = 1; page <= (changed + 99) / 100; page++ )); do
  rows=$(gh api "repos/$REPO/pulls/$PR/files?per_page=100&page=$page" \
    --jq '.[] | [.filename, (.previous_filename // "")] | @tsv') \
    || { echo "gate=human reason=could not read the changed files"; exit 0; }
  while IFS=$'\t' read -r name previous; do
    [[ -n $name ]] || continue
    (( seen += 1 ))
    paths+=$name$'\n'
    [[ -n $previous ]] && paths+=$previous$'\n'
  done <<<"$rows"
done
(( seen == changed )) \
  || { echo "gate=human reason=could read only $seen of the $changed changed files"; exit 0; }
now=$(gh api "repos/$REPO/pulls/$PR" --jq "$REVISION") \
  || { echo "gate=human reason=could not re-read the PR"; exit 0; }
[[ $now == "$revision" ]] || { echo "gate=human reason=the PR moved while its files were read"; exit 0; }
[[ $author_type == Bot ]] && reasons+=("a bot opened it")
[[ -n $asked ]] && reasons+=("a review is still requested of $asked")

patterns=('^\.github/')
config=$(gh api -H 'Accept: application/vnd.github.raw+json' \
  "repos/$REPO/contents/.github/review-judgement.json?ref=${revision#*..}" 2>&1)
if (( $? == 0 )); then
  listed=$(jq -r --arg agent_read "$AGENT_READ" '.guarded | if type == "array" and all(type == "string")
    then $agent_read, .[] else error end' <<<"$config") \
    || { echo "gate=human reason=could not read the guarded list in review-judgement.json"; exit 0; }
  mapfile -t -O 1 patterns <<<"$listed"
elif [[ $config == *"HTTP 404"* ]]; then
  (( $# >= 3 )) || reasons+=("no guarded paths configured")
  IFS=, read -ra listed <<<"$GUARDED"
  patterns+=("${listed[@]}")
else
  echo "gate=human reason=could not read review-judgement.json"; exit 0
fi

guarded=$(python3 -c '
import re, sys
paths = sys.stdin.read().splitlines()
for p in map(str.strip, sys.argv[1:]):
    if not p:
        continue
    try:
        hit = next(filter(re.compile(p).search, paths), None)
    except re.error:
        print(f"`{p}` is not a regex the gate can read")
        continue
    if hit:
        print(f"`{hit}` is a guarded path (`{p}`)")
' "${patterns[@]}" <<<"$paths") || { echo "gate=human reason=could not match the guarded paths"; exit 0; }
while IFS= read -r reason; do
  [[ -n $reason ]] && reasons+=("$reason")
done <<<"$guarded"

if (( ${#reasons[@]} )); then
  out="gate=human reason="
  for r in "${reasons[@]}"; do out+="$r; "; done
  echo "${out%; }"
else
  echo "gate=pass"
fi
