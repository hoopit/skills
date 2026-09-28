#!/usr/bin/env bash
# Bring hoopit-dev@hoopit-skills to the marketplace's latest version in every checkout
# on this machine that has it installed, and install it in Hoopit product checkouts.
#
# Usage: update-plugins.sh [checkout-dir ...]
#
# Only main worktrees count (linked worktrees are skipped). Every project path with a
# hoopit-dev record in installed_plugins.json is updated, whatever its remote. Siblings of
# recorded project paths get a fresh install only when their origin is hoopit/<repo> for
# one of REPOS. A directory named as an argument is installed or updated whatever its
# remote. Prints one line per checkout (<name> is the product repo, else the basename):
#   RESULT <name> <dir> <updated|current|installed|stale|failed> <old> -> <new>
# `stale` means the CLI reported success but this checkout's own record is not at <new>;
# the records at fault are listed beneath it.
set -uo pipefail

PLUGIN="hoopit-dev@hoopit-skills"
MARKETPLACE="hoopit-skills"
REPOS=(api web-admin flutter-app public-calendar)
INSTALLED="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/plugins/installed_plugins.json"
export MISE_QUIET=1

command -v jq >/dev/null || { echo "jq is required" >&2; exit 2; }

echo "Refreshing marketplace $MARKETPLACE..."
claude plugin marketplace update "$MARKETPLACE" >/dev/null || { echo "marketplace update failed" >&2; exit 1; }

# installed_plugins.json records native paths. On Windows that is `D:\x` or `d:\x`
# while Git Bash sees `/d/x`, so both sides compare as `d:/x`. Case is folded only where
# paths are case-insensitive: Windows, and macOS on its default volumes.
native() { printf '%s\n' "$1"; }
PATH_NORM='.'
if command -v cygpath >/dev/null; then
  native() { cygpath -m "$1"; }
  PATH_NORM='gsub("\\\\"; "/") | ascii_downcase'
elif [[ "$(uname -s)" == Darwin ]]; then
  PATH_NORM='ascii_downcase'
fi

has_record() {
  jq -e --arg d "$(native "$1")" --arg p "$PLUGIN" \
    "def norm: $PATH_NORM;
     .plugins[\$p] // [] | any(.scope == \"project\" and (.projectPath | norm) == (\$d | norm))" \
    "$INSTALLED" >/dev/null 2>&1
}

declare -A found=() forced=()
for arg in "$@"; do
  [[ -d "$arg" ]] && forced["$(cd "$arg" && pwd -P)"]=1
done

candidates=("$@")
if [[ -f "$INSTALLED" ]]; then
  while IFS= read -r p; do
    candidates+=("$p")
    parent=$(dirname "$p")
    for sib in "$parent"/*/; do candidates+=("${sib%/}"); done
  done < <(jq -r '.plugins[][] | .projectPath // empty' "$INSTALLED" | sort -u)
fi

for dir in "${candidates[@]}"; do
  [[ -d "$dir/.git" || -f "$dir/.git" ]] || continue
  dir=$(cd "$dir" && pwd -P)
  [[ -n "${found[$dir]:-}" ]] && continue
  # A linked worktree's git dir differs from the common dir.
  [[ "$(git -C "$dir" rev-parse --path-format=absolute --git-dir 2>/dev/null)" == \
     "$(git -C "$dir" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" ]] || continue
  url=$(git -C "$dir" remote get-url origin 2>/dev/null)
  name=$(sed -E 's#\.git$##; s#.*[/:]hoopit/([^/]+)$#\1#i' <<<"$url")
  product=
  for r in "${REPOS[@]}"; do
    [[ "$name" == "$r" ]] && product=$r
  done
  if [[ -n "$product" || -n "${forced[$dir]:-}" ]] || has_record "$dir"; then
    found["$dir"]=${product:-$(basename "$dir")}
  fi
done

while IFS= read -r dir; do
  name=${found[$dir]}
  if has_record "$dir"; then
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
    # The CLI can write a different record than this checkout's: a nested worktree's,
    # or one of several records whose paths differ only in case.
    stale=$(jq -r --arg d "$(native "$dir")" --arg p "$PLUGIN" --arg v "$new" \
      "def norm: $PATH_NORM;
       .plugins[\$p] // [] | map(select(.scope == \"project\" and (.projectPath | norm) == (\$d | norm)))
       | if length == 0 then [\"(no record)\"] else map(select(.version != \$v) | \"\(.projectPath) \(.version)\") end
       | .[]" "$INSTALLED" 2>&1)
    if [[ "$new" != "-" && -n "$stale" ]]; then
      echo "RESULT $name $dir stale $old -> $new"
      sed 's/^/  /' <<<"$stale"
    else
      echo "RESULT $name $dir $status $old -> $new"
    fi
  else
    echo "RESULT $name $dir failed - -> -"
    sed 's/^/  /' <<<"$out"
  fi
done < <(for d in "${!found[@]}"; do printf '%s\n' "$d"; done | sort)

