#!/usr/bin/env bash
#
# What has this person actually invoked? Counts skill uses across the session
# transcripts so a recommendation rests on evidence, not on guessing.
#
#   usage.sh [days]        default 60
#
# Emits JSON: {days, transcripts, byModel: {...}, bySlash: {...}}
#   byModel — skills Claude itself reached for (Skill tool calls)
#   bySlash — skills the human typed as /name

set -euo pipefail

DAYS="${1:-60}"
ROOT="$HOME/.claude/projects"
command -v jq >/dev/null 2>&1 || { echo 'usage.sh needs jq' >&2; exit 1; }

FILES=()
if [[ -d "$ROOT" ]]; then
  while IFS= read -r f; do [[ -n "$f" ]] && FILES+=("$f"); done \
    < <(find "$ROOT" -name '*.jsonl' -mtime "-$DAYS" 2>/dev/null)
fi

counts_json() {  # stdin: one name per line -> {name: count}
  sort | uniq -c | sort -rn \
    | sed 's/^[[:space:]]*\([0-9]*\)[[:space:]]*\(.*\)$/\2\t\1/' \
    | jq -R -s 'split("\n") | map(select(length > 0) | split("\t") | {key: .[0], value: (.[1] | tonumber)}) | from_entries'
}

BY_MODEL='{}'
BY_SLASH='{}'
if (( ${#FILES[@]} )); then
  BY_MODEL=$(grep -h '"name":"Skill"' "${FILES[@]}" 2>/dev/null \
    | grep -o '"skill":"[^"]*"' | sed 's/"skill":"//;s/"//' | counts_json)
  BY_SLASH=$(grep -ho '<command-name>[^<]*</command-name>' "${FILES[@]}" 2>/dev/null \
    | sed 's|<command-name>/||;s|</command-name>||' | counts_json)
fi

jq -n --argjson d "$DAYS" --argjson n "${#FILES[@]}" \
  --argjson m "$BY_MODEL" --argjson s "$BY_SLASH" \
  '{days: $d, transcripts: $n, byModel: $m, bySlash: $s}'
