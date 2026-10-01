#!/usr/bin/env bash
# Bring each of PLUGINS to its marketplace's latest version in every Hoopit product
# checkout on this machine, installing it at project scope where a checkout has none.
# Each of WHERE_INSTALLED is updated only where it already has an install record: at user
# scope, and at project or local scope in a checkout found here. It is never installed.
#
# Usage: update-plugins.sh [checkout-dir ...]
#
# Checkouts are found from the directories named as arguments, every project path in
# installed_plugins.json, and the siblings of each of those. A directory counts when its
# origin remote is hoopit/<repo> for one of REPOS and it is a main worktree (linked
# worktrees are skipped). Prints one line per checkout:
#   RESULT <plugin> <repo> <dir> <updated|current|installed|stale|failed> <old> -> <new>
# A user-scope record reports `user` as both <repo> and <dir>.
# `stale` means the CLI reported success but this checkout's own record is not at <new>;
# the records at fault are listed beneath it.
# then a final `MISSING <repo>` for each product repo with no checkout found.
set -uo pipefail

PLUGINS=(hoopit-dev@hoopit-skills mattpocock-skills@claude-plugins-official)
WHERE_INSTALLED=(github-tracker@hoopit-skills)
REPOS=(api web-admin flutter-app public-calendar)
INSTALLED="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/plugins/installed_plugins.json"
export MISE_QUIET=1

command -v jq >/dev/null || { echo "jq is required" >&2; exit 2; }

for m in $(printf '%s\n' "${PLUGINS[@]#*@}" "${WHERE_INSTALLED[@]#*@}" | sort -u); do
  echo "Refreshing marketplace $m..."
  claude plugin marketplace update "$m" >/dev/null || { echo "marketplace update failed: $m" >&2; exit 1; }
done

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

# Whether <plugin> has a <scope> record, for checkout <dir> unless the scope is user.
has_record() {
  jq -e --arg d "$(native "$3")" --arg p "$1" --arg s "$2" \
    "def norm: $PATH_NORM;
     .plugins[\$p] // [] | any(.scope == \$s and (\$s == \"user\" or (.projectPath | norm) == (\$d | norm)))" \
    "$INSTALLED" >/dev/null 2>&1
}

# Run `claude plugin <verb>` for <plugin> at <scope> from <dir>, and print its RESULT line.
apply() {
  local verb=$1 plugin=$2 scope=$3 repo=$4 dir=$5 out line status old new stale
  out=$(cd "$dir" && claude plugin "$verb" "$plugin" --scope "$scope" --json 2>&1)
  [[ $scope == user ]] && dir=user
  line=$(grep -m1 '^{' <<<"$out")
  if [[ -n "$line" ]] && jq -e '.outcome == "ok"' <<<"$line" >/dev/null 2>&1; then
    status=$(jq -r 'if .command == "install" then "installed"
                    elif .updateOutcome == "updated" then "updated" else "current" end' <<<"$line")
    old=$(jq -r '.oldVersion // "-"' <<<"$line")
    new=$(jq -r '.newVersion // .version // "-"' <<<"$line")
    # The CLI can write a different record than this checkout's: a nested worktree's,
    # or one of several records whose paths differ only in case.
    stale=$(jq -r --arg d "$(native "$dir")" --arg p "$plugin" --arg v "$new" --arg s "$scope" \
      "def norm: $PATH_NORM;
       .plugins[\$p] // [] | map(select(.scope == \$s and (\$s == \"user\" or (.projectPath | norm) == (\$d | norm))))
       | if length == 0 then [\"(no record)\"] else map(select(.version != \$v) | \"\(.projectPath) \(.version)\") end
       | .[]" "$INSTALLED" 2>&1)
    if [[ "$new" != "-" && -n "$stale" ]]; then
      echo "RESULT $plugin $repo $dir stale $old -> $new"
      sed 's/^/  /' <<<"$stale"
    else
      echo "RESULT $plugin $repo $dir $status $old -> $new"
    fi
  else
    echo "RESULT $plugin $repo $dir failed - -> -"
    sed 's/^/  /' <<<"$out"
  fi
}

for plugin in "${WHERE_INSTALLED[@]}"; do
  has_record "$plugin" user - && apply update "$plugin" user user "$HOME"
done

while IFS= read -r dir; do
  repo=${found[$dir]}
  for plugin in "${PLUGINS[@]}"; do
    if has_record "$plugin" project "$dir"; then
      apply update "$plugin" project "$repo" "$dir"
    else
      apply install "$plugin" project "$repo" "$dir"
    fi
  done
  for plugin in "${WHERE_INSTALLED[@]}"; do
    for scope in project local; do
      has_record "$plugin" "$scope" "$dir" && apply update "$plugin" "$scope" "$repo" "$dir"
    done
  done
done < <(for d in "${!found[@]}"; do printf '%s\n' "$d"; done | sort)

for r in "${REPOS[@]}"; do
  printf '%s\n' "${found[@]}" | grep -qx "$r" || echo "MISSING $r"
done
