#!/usr/bin/env bash
# Bring hoopit-dev@hoopit-skills to the marketplace's latest version in every Hoopit
# product checkout on this machine.
#
# Usage: update-plugins.sh [checkout-dir ...]
#
# Checkouts are found from the directories named as arguments, every project path in
# installed_plugins.json, and the siblings of each of those. A directory counts when its
# origin remote is hoopit/<repo> for one of REPOS and it is a main worktree (linked
# worktrees are skipped). Prints one line per checkout:
#   RESULT <repo> <dir> <updated|current|installed|failed> <old> -> <new>
# then a final `MISSING <repo>` for each product repo with no checkout found.
set -uo pipefail

PLUGIN="hoopit-dev@hoopit-skills"
MARKETPLACE="hoopit-skills"
REPOS=(api web-admin flutter-app public-calendar)
INSTALLED="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/plugins/installed_plugins.json"
export MISE_QUIET=1

command -v jq >/dev/null || { echo "jq is required" >&2; exit 2; }

echo "Refreshing marketplace $MARKETPLACE..."
claude plugin marketplace update "$MARKETPLACE" >/dev/null || { echo "marketplace update failed" >&2; exit 1; }

candidates=("$@")
if [[ -f "$INSTALLED" ]]; then
  while IFS= read -r p; do
    candidates+=("$p")
    parent=$(dirname "$p")
    for sib in "$parent"/*/; do candidates+=("${sib%/}"); done
  done < <(jq -r '.plugins[][] | .projectPath // empty' "$INSTALLED" | sort -u)
fi

declare -A found=()
for dir in "${candidates[@]}"; do
  [[ -d "$dir/.git" || -f "$dir/.git" ]] || continue
  dir=$(cd "$dir" && pwd -P)
  # A linked worktree's git dir differs from the common dir.
  [[ "$(git -C "$dir" rev-parse --path-format=absolute --git-dir 2>/dev/null)" == \
     "$(git -C "$dir" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" ]] || continue
  url=$(git -C "$dir" remote get-url origin 2>/dev/null) || continue
  name=$(sed -E 's#\.git$##; s#.*[/:]hoopit/([^/]+)$#\1#i' <<<"$url")
  [[ "$name" != "$url" ]] || continue
  for r in "${REPOS[@]}"; do
    [[ "$name" == "$r" ]] && found["$dir"]="$r"
  done
done

# installed_plugins.json records native paths. On Windows that is `D:\x` or `d:\x`
# while Git Bash sees `/d/x`, so both sides compare as `d:/x`, case-insensitively.
if command -v cygpath >/dev/null; then
  native() { cygpath -m "$1"; }
  PATH_NORM='gsub("\\\\"; "/") | ascii_downcase'
else
  native() { printf '%s\n' "$1"; }
  PATH_NORM='.'
fi

for dir in "${!found[@]}"; do
  repo=${found[$dir]}
  if jq -e --arg d "$(native "$dir")" --arg p "$PLUGIN" \
       "def norm: $PATH_NORM;
        .plugins[\$p] // [] | any(.scope == \"project\" and (.projectPath | norm) == (\$d | norm))" \
       "$INSTALLED" >/dev/null 2>&1; then
    out=$(cd "$dir" && claude plugin update "$PLUGIN" --scope project --json 2>&1)
  else
    out=$(cd "$dir" && claude plugin install "$PLUGIN" --scope project --json 2>&1)
  fi
  line=$(grep -m1 '^{' <<<"$out")
  if [[ -n "$line" ]] && jq -e '.outcome == "ok"' <<<"$line" >/dev/null 2>&1; then
    status=$(jq -r 'if .command == "install" then "installed"
                    elif .updateOutcome == "updated" then "updated" else "current" end' <<<"$line")
    old=$(jq -r '.oldVersion // "-"' <<<"$line")
    new=$(jq -r '.newVersion // .version // "-"' <<<"$line")
    echo "RESULT $repo $dir $status $old -> $new"
  else
    echo "RESULT $repo $dir failed - -> -"
    sed 's/^/  /' <<<"$out"
  fi
done | sort -k2

for r in "${REPOS[@]}"; do
  printf '%s\n' "${found[@]}" | grep -qx "$r" || echo "MISSING $r"
done
