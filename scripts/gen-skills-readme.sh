#!/usr/bin/env bash
# Regenerate the "Skills by plugin" block in README.md from the source of truth:
#   - plugin order + taglines + which skills are picked → .claude-plugin/marketplace.json
#   - local skills' summaries                           → each plugins/<group>/skills/*/SKILL.md frontmatter
#   - matt-picks (github source)                        → the entry's skills[] paths (names only; descriptions live upstream)
#
# The block lives between the BEGIN/END markers below in README.md.
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

# Read a single-line frontmatter field from a SKILL.md (between the opening ---/--- fence).
frontmatter_field() {
  awk -v key="$2" '
    /^---[[:space:]]*$/ { fence++; next }
    fence==1 && $0 ~ "^" key ":" { sub("^" key ":[[:space:]]*", ""); print; exit }
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
  local count=$(jq '.plugins | length' "$MARKETPLACE")
  for i in $(seq 0 $((count - 1))); do
    local name desc src
    name=$(jq -r ".plugins[$i].name" "$MARKETPLACE")
    desc=$(jq -r ".plugins[$i].description // \"\"" "$MARKETPLACE")
    src=$(jq -r ".plugins[$i].source" "$MARKETPLACE")   # string path, or "[object Object]"-ish for github

    printf '**`%s`** — %s\n\n' "$name" "$desc"

    if jq -e ".plugins[$i].source | type == \"string\"" "$MARKETPLACE" >/dev/null; then
      # Local plugin: one table row per SKILL.md, alphabetically.
      local dir="$src"
      printf '| Skill | Invoke | Description |\n'
      printf '|-------|--------|-------------|\n'
      for skill in "$dir"/skills/*/SKILL.md; do
        [ -f "$skill" ] || continue
        local sname sdesc invocation
        sname=$(frontmatter_field "$skill" name)
        sdesc=$(first_sentence "$(frontmatter_field "$skill" description)")
        invocation="Auto"
        [ "$(frontmatter_field "$skill" disable-model-invocation)" = "true" ] && invocation="Manual"
        printf -- '| `%s` | %s | %s |\n' "$sname" "$invocation" "$sdesc"
      done
    else
      # Remote (github) pick: one table row per skill. Descriptions live upstream,
      # so the local marketplace only gives us the name (invoked namespaced) and
      # the upstream group (2nd path segment of ./skills/<group>/<name>).
      local repo; repo=$(jq -r ".plugins[$i].source.repo" "$MARKETPLACE")
      printf 'Invoked namespaced as `mattpocock-skills:<name>`; descriptions live [upstream](https://github.com/%s).\n\n' "$repo"
      printf '| Skill | Invoke | Group |\n'
      printf '|-------|--------|-------|\n'
      jq -r ".plugins[$i].skills[] | split(\"/\") | .[3] + \"\t\" + .[2]" "$MARKETPLACE" \
        | while IFS=$'\t' read -r sname group; do
            local label
            label=$(printf '%s' "$group" | sed 's/-/ /g; s/./\U&/')   # in-progress -> In progress
            printf -- '| `mattpocock-skills:%s` | Auto | %s |\n' "$sname" "$label"
          done
    fi
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
tmp=$(mktemp)
awk -v b="$BEGIN" -v e="$END" -v block="$block" '
  $0==b { print; print block; skip=1; next }
  $0==e { skip=0 }
  !skip
' "$README" > "$tmp"
mv "$tmp" "$README"
echo "Regenerated the skills block in $README."
