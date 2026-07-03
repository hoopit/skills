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

gen() {
  local count=$(jq '.plugins | length' "$MARKETPLACE")
  for i in $(seq 0 $((count - 1))); do
    local name desc src
    name=$(jq -r ".plugins[$i].name" "$MARKETPLACE")
    desc=$(jq -r ".plugins[$i].description // \"\"" "$MARKETPLACE")
    src=$(jq -r ".plugins[$i].source" "$MARKETPLACE")   # string path, or "[object Object]"-ish for github

    printf '**`%s`** — %s\n' "$name" "$desc"

    if jq -e ".plugins[$i].source | type == \"string\"" "$MARKETPLACE" >/dev/null; then
      # Local plugin: list its SKILL.md files alphabetically.
      local dir="$src"
      for skill in "$dir"/skills/*/SKILL.md; do
        [ -f "$skill" ] || continue
        local sname sdesc guard=""
        sname=$(frontmatter_field "$skill" name)
        sdesc=$(frontmatter_field "$skill" description)
        [ "$(frontmatter_field "$skill" disable-model-invocation)" = "true" ] && guard=" _(user-invoked only)_"
        printf -- '- `%s` — %s%s\n' "$sname" "$sdesc" "$guard"
      done
    else
      # Remote (github) pick: names only, grouped by upstream folder.
      local repo; repo=$(jq -r ".plugins[$i].source.repo" "$MARKETPLACE")
      printf -- '- Invoked namespaced as `mattpocock-skills:<name>`; descriptions live [upstream](https://github.com/%s).\n' "$repo"
      # For each distinct group (2nd path segment of ./skills/<group>/<name>), list the names, comma-joined.
      for group in $(jq -r ".plugins[$i].skills[] | split(\"/\")[2]" "$MARKETPLACE" | awk '!seen[$0]++'); do
        local label names
        label=$(printf '%s' "$group" | sed 's/-/ /g; s/./\U&/')   # in-progress -> In progress
        names=$(jq -r "[.plugins[$i].skills[] | select(split(\"/\")[2] == \"$group\") | \"\`\" + split(\"/\")[3] + \"\`\"] | join(\", \")" "$MARKETPLACE")
        printf -- '- _%s:_ %s\n' "$label" "$names"
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
