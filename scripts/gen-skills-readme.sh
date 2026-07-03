#!/usr/bin/env bash
# Regenerate the "Skills by plugin" block in README.md from the source of truth:
#   - plugin order + taglines + which skills are picked → .claude-plugin/marketplace.json
#   - local skills' summaries                           → each plugins/<group>/skills/*/SKILL.md frontmatter
#   - matt-picks (github source)                        → matt-picks-lock.json (name/description/invoke,
#                                                         cached from upstream by --refresh)
#
# The block lives between the BEGIN/END markers below in README.md.
#
# The matt-picks table needs upstream frontmatter (descriptions + model-invocation
# status), which lives in another repo. Rather than hit the network on every run, we
# cache it in matt-picks-lock.json and read from there. `--refresh` is the only mode
# that touches the network: it fetches each pick's SKILL.md, VERIFIES the pick still
# exists upstream (fails loudly on a rename/removal), and rewrites the lockfile. Every
# other mode is offline and fails if a pick isn't covered by the lockfile.
#
# Usage:
#   scripts/gen-skills-readme.sh            # rewrite the block in README.md (offline)
#   scripts/gen-skills-readme.sh --check    # exit 1 (and diff) if README.md is out of date (offline)
#   scripts/gen-skills-readme.sh --refresh  # re-fetch matt-picks from upstream, verify, then rewrite (needs gh + network)
set -euo pipefail

cd "$(dirname "$0")/.."
MARKETPLACE=.claude-plugin/marketplace.json
LOCK=matt-picks-lock.json
README=README.md
BEGIN='<!-- BEGIN generated skills: scripts/gen-skills-readme.sh — do not edit between these markers -->'
END='<!-- END generated skills -->'

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

# --refresh: pull each matt-pick's frontmatter from upstream, verify it still exists,
# and rewrite matt-picks-lock.json. Exits 1 (without touching the lock) if any pick 404s.
refresh_lock() {
  command -v gh >/dev/null || { echo "ERROR: --refresh needs the 'gh' CLI (authenticated)." >&2; exit 1; }

  local repo ref
  repo=$(jq -r '.plugins[] | select(.source | type == "object") | .source.repo' "$MARKETPLACE")
  ref=$(jq -r '.plugins[]  | select(.source | type == "object") | (.source.ref // "main")' "$MARKETPLACE")
  mapfile -t picks < <(jq -r '.plugins[] | select(.source | type == "object") | .skills[]' "$MARKETPLACE")

  echo "Refreshing ${#picks[@]} matt-picks from $repo@$ref …" >&2
  local missing=() entries; entries=$(mktemp)
  local p path content name desc invoke
  for p in "${picks[@]}"; do
    path="${p#./}/SKILL.md"
    if ! content=$(gh api "repos/$repo/contents/$path?ref=$ref" -H "Accept: application/vnd.github.raw" 2>/dev/null); then
      missing+=("$p"); continue
    fi
    name=$(frontmatter_field <(printf '%s\n' "$content") name)
    desc=$(frontmatter_field <(printf '%s\n' "$content") description)
    invoke="Auto"
    [ "$(frontmatter_field <(printf '%s\n' "$content") disable-model-invocation)" = "true" ] && invoke="Manual"
    jq -n --arg path "$p" --arg name "$name" --arg desc "$desc" --arg invoke "$invoke" \
      '{key: $path, value: {name: $name, invoke: $invoke, description: $desc}}' >> "$entries"
  done

  if [ ${#missing[@]} -gt 0 ]; then
    rm -f "$entries"
    echo "ERROR: these picks no longer exist upstream ($repo@$ref):" >&2
    printf '  - %s\n' "${missing[@]}" >&2
    echo "They were renamed or removed upstream. Fix the skills[] list in $MARKETPLACE, then re-run --refresh." >&2
    exit 1
  fi

  jq -n --arg repo "$repo" --arg ref "$ref" --slurpfile e <(jq -s 'from_entries' "$entries") \
    '{version: 1, repo: $repo, ref: $ref, skills: $e[0]}' > "$LOCK"
  rm -f "$entries"
  echo "Wrote ${#picks[@]} picks to $LOCK." >&2
}

# Offline guard: every matt-pick in the marketplace must be covered by the lockfile.
verify_lock_coverage() {
  [ -f "$LOCK" ] || { echo "ERROR: $LOCK is missing — run: scripts/gen-skills-readme.sh --refresh" >&2; exit 1; }
  local missing
  missing=$(comm -23 \
    <(jq -r '.plugins[] | select(.source | type == "object") | .skills[]' "$MARKETPLACE" | sort) \
    <(jq -r '.skills | keys[]' "$LOCK" | sort))
  if [ -n "$missing" ]; then
    echo "ERROR: these picks aren't in $LOCK — run: scripts/gen-skills-readme.sh --refresh" >&2
    printf '  - %s\n' $missing >&2
    exit 1
  fi
}

gen() {
  local count; count=$(jq '.plugins | length' "$MARKETPLACE")
  for i in $(seq 0 $((count - 1))); do
    local name desc
    name=$(jq -r ".plugins[$i].name" "$MARKETPLACE")
    desc=$(jq -r ".plugins[$i].description // \"\"" "$MARKETPLACE")

    printf '#### `%s`\n\n%s\n\n' "$name" "$desc"

    if jq -e ".plugins[$i].source | type == \"string\"" "$MARKETPLACE" >/dev/null; then
      # Local plugin: one table row per SKILL.md, alphabetically.
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
    else
      # Remote (github) pick: one table row per skill, from the cached lockfile.
      local repo; repo=$(jq -r ".plugins[$i].source.repo" "$MARKETPLACE")
      printf 'Invoked namespaced as `mattpocock-skills:<name>`. Descriptions cached from [%s](https://github.com/%s) by `scripts/gen-skills-readme.sh --refresh`.\n\n' "$repo" "$repo"
      printf '| Skill | Invoke | Description |\n'
      printf '|-------|--------|-------------|\n'
      local p sname inv sdesc
      while IFS= read -r p; do
        sname=$(jq -r --arg p "$p" '.skills[$p].name'   "$LOCK")
        inv=$(  jq -r --arg p "$p" '.skills[$p].invoke' "$LOCK")
        sdesc=$(first_sentence "$(jq -r --arg p "$p" '.skills[$p].description' "$LOCK")")
        printf -- '| `mattpocock-skills:%s` | %s | %s |\n' "$sname" "$inv" "$sdesc"
      done < <(jq -r ".plugins[$i].skills[]" "$MARKETPLACE")
    fi
    printf '\n'
  done
}

[ "${1:-}" = "--refresh" ] && refresh_lock

verify_lock_coverage
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
