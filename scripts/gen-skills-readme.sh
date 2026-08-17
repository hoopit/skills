#!/usr/bin/env bash
# Regenerate the "Skills by plugin" block in README.md from the source of truth:
#   - plugin order + taglines → .claude-plugin/marketplace.json
#   - skills' summaries       → each plugins/<group>/skills/*/SKILL.md frontmatter
#
# The block lives between the BEGIN/END markers below in README.md. Every plugin is a
# local directory, so this script is fully offline — it never hits the network.
#
# Usage:
#   scripts/gen-skills-readme.sh            # rewrite the block in README.md
#   scripts/gen-skills-readme.sh --check    # exit 1 (and diff) if README.md is out of date
set -euo pipefail

cd "$(dirname "$0")/.."
MARKETPLACE=.claude-plugin/marketplace.json
README=README.md
BEGIN='<!-- BEGIN generated skills: scripts/gen-skills-readme.sh — do not edit between these markers -->'
END='<!-- END generated skills -->'

# Every mktemp below appends to TMPFILES; the EXIT trap clears them on *any* exit path,
# since `set -e` can abort between the mktemp and its intended cleanup.
TMPFILES=()
cleanup() { [ ${#TMPFILES[@]} -eq 0 ] || rm -f "${TMPFILES[@]}"; }
trap cleanup EXIT

# Read a single-line frontmatter field from a SKILL.md (between the opening ---/--- fence).
frontmatter_field() {
  awk -v key="$2" '
    /^---[[:space:]]*$/ { fence++; next }
    fence==1 && $0 ~ "^" key ":" {
      sub("^" key ":[[:space:]]*", "")
      q = substr($0, 1, 1)                       # strip one layer of surrounding YAML quotes
      if ((q == "\"" || q == "\047") && length($0) >= 2 && substr($0, length($0), 1) == q)
        $0 = substr($0, 2, length($0) - 2)
      print; exit
    }
  ' "$1"
}

# First sentence of a string: up to and including the first period that is
# followed by whitespace or end-of-string (so "Python 3.14" isn't split).
first_sentence() {
  printf '%s' "$1" | awk '{
    n = length($0)
    for (i = 1; i <= n; i++) {
      if (substr($0, i, 1) == ".") {
        nx = substr($0, i + 1, 1)
        if (nx == "" || nx == " ") { print substr($0, 1, i); exit }
      }
    }
    print $0
  }'
}

gen() {
  local count; count=$(jq '.plugins | length' "$MARKETPLACE")
  for i in $(seq 0 $((count - 1))); do
    local name desc
    name=$(jq -r ".plugins[$i].name" "$MARKETPLACE")
    desc=$(jq -r ".plugins[$i].description // \"\"" "$MARKETPLACE")

    printf '#### `%s`\n\n%s\n\n' "$name" "$desc"

    # One table row per SKILL.md in the plugin's directory, alphabetically.
    local dir; dir=$(jq -r ".plugins[$i].source" "$MARKETPLACE")
    printf '| Skill | Invoke | Description |\n'
    printf '|-------|--------|-------------|\n'
    local skill sname sdesc invocation
    for skill in "$dir"/skills/*/SKILL.md; do
      [ -f "$skill" ] || continue
      sname=$(frontmatter_field "$skill" name)
      sdesc=$(first_sentence "$(frontmatter_field "$skill" description)")
      invocation="Auto"
      [ "$(frontmatter_field "$skill" disable-model-invocation)" = "true" ] && invocation="Manual"
      printf -- '| `%s` | %s | %s |\n' "$sname" "$invocation" "$sdesc"
    done
    printf '\n'
  done
}

block="$(gen)"

if [ "${1:-}" = "--check" ]; then
  current=$(awk -v b="$BEGIN" -v e="$END" '$0==b{f=1;next} $0==e{f=0} f' "$README")
  if [ "$current" != "$block" ]; then
    echo "README.md skills block is out of date. Run: scripts/gen-skills-readme.sh" >&2
    diff <(printf '%s\n' "$current") <(printf '%s\n' "$block") >&2 || true
    exit 1
  fi
  echo "README.md skills block is up to date."
  exit 0
fi

# Rewrite the block in place (between the markers), preserving everything else.
# The block goes through a file, not `awk -v`: macOS's awk rejects newlines inside a
# -v assignment, so a multi-line -v works only under gawk.
tmp=$(mktemp); TMPFILES+=("$tmp")
blockfile=$(mktemp); TMPFILES+=("$blockfile")
printf '%s\n' "$block" > "$blockfile"
awk -v b="$BEGIN" -v e="$END" -v bf="$blockfile" '
  $0==b { print; while ((getline line < bf) > 0) print line; close(bf); skip=1; next }
  $0==e { skip=0 }
  !skip
' "$README" > "$tmp"
mv "$tmp" "$README"
echo "Regenerated the skills block in $README."
