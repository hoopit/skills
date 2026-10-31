#!/usr/bin/env bash
# Bring each of PLUGINS to its marketplace's latest version in every checkout on this
# machine that has it installed, and install it at project scope in Hoopit product
# checkouts. Each of WHERE_INSTALLED is updated only where it already has an install
# record: at user scope, and at project or local scope in any checkout. It is never
# installed, and a checkout found only by its record gets no PLUGINS. Each of PLUGINS is
# updated, never installed, at user scope too.
#
# Usage: update-plugins.sh [checkout-dir ...]
#
# Only main worktrees count (linked worktrees are skipped). Every project path with a
# PLUGINS record in installed_plugins.json is updated, whatever its remote. Siblings of
# recorded project paths get a fresh install only when their origin is hoopit/<repo> for
# one of REPOS. A directory named as an argument is installed or updated whatever its
# remote. Prints one line per plugin and checkout (<repo> is the product repo, else the
# directory's basename):
#   RESULT <plugin> <repo> <dir> <updated|current|installed|stale|failed> <old> -> <new>
# A user-scope record reports `user` as both <repo> and <dir>.
# `stale` means the CLI reported success but this checkout's own record is not at <new>;
# the records at fault are listed beneath it. Exits non-zero if any line is stale or failed.
set -uo pipefail

PLUGINS=(hoopit-dev@hoopit-skills mattpocock-skills@claude-plugins-official)
WHERE_INSTALLED=(github-tracker@hoopit-skills hoopit-product@hoopit-skills)
REPOS=(api web-admin flutter-app public-calendar)
INSTALLED="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/plugins/installed_plugins.json"
export MISE_QUIET=1
unsettled=0

command -v jq >/dev/null || { echo "jq is required" >&2; exit 2; }

# An inherited GIT_DIR, GIT_WORK_TREE etc. would point every git call at the caller's repo.
mapfile -t git_env < <(git rev-parse --local-env-vars)
unset "${git_env[@]}"

for m in $(printf '%s\n' "${PLUGINS[@]#*@}" "${WHERE_INSTALLED[@]#*@}" | sort -u); do
  echo "Refreshing marketplace $m..."
  claude plugin marketplace update "$m" >/dev/null || { echo "marketplace update failed: $m" >&2; exit 1; }
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

candidates=("$@")
if [[ -f "$INSTALLED" ]]; then
  while IFS= read -r p; do
    candidates+=("$p")
    parent=$(dirname "$p")
    for sib in "$parent"/*/; do candidates+=("${sib%/}"); done
  done < <(jq -r '.plugins[][] | .projectPath // empty' "$INSTALLED" | sort -u)
fi

declare -A found=() forced=() where_only=()
for arg in "$@"; do
  [[ -d "$arg" ]] && forced["$(cd "$arg" && pwd -P)"]=1
done

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
  recorded=
  for plugin in "${PLUGINS[@]}"; do
    has_record "$plugin" project "$dir" && recorded=1
  done
  if [[ -n "$product" || -n "${forced[$dir]:-}" || -n "$recorded" ]]; then
    found["$dir"]=${product:-$(basename "$dir")}
    continue
  fi
  for plugin in "${WHERE_INSTALLED[@]}"; do
    if has_record "$plugin" project "$dir" || has_record "$plugin" local "$dir"; then
      found["$dir"]=$(basename "$dir")
      where_only["$dir"]=1
    fi
  done
done

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
      unsettled=1
      sed 's/^/  /' <<<"$stale"
    else
      echo "RESULT $plugin $repo $dir $status $old -> $new"
    fi
  else
    echo "RESULT $plugin $repo $dir failed - -> -"
    unsettled=1
    sed 's/^/  /' <<<"$out"
  fi
}

for plugin in "${PLUGINS[@]}" "${WHERE_INSTALLED[@]}"; do
  has_record "$plugin" user - && apply update "$plugin" user user "$HOME"
done

while IFS= read -r dir; do
  repo=${found[$dir]}
  for plugin in "${PLUGINS[@]}"; do
    [[ -n "${where_only[$dir]:-}" ]] && break
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

exit "$unsettled"
