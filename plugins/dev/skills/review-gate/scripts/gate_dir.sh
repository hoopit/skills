#!/usr/bin/env bash
# The lifecycle of a review-gate pass's scratch directory — its findings files and every probe
# worktree a reviewer builds inside it — kept out of the agent's hands, because a pass that
# aborts, is interrupted or hands back early never reaches a prose teardown step. Probe worktrees
# run to ~60k files apiece once `node_modules` is in, and on a tmpfs `/tmp` a handful of leaked
# ones exhaust its inodes for the whole machine.
#
# Usage:  gate_dir.sh open            create a gate dir owned by this Claude session; prints its path
#         gate_dir.sh close <dir>     remove one gate dir and deregister the worktrees inside it
#         gate_dir.sh sweep [--session <id>] [--background]
#                                     remove every gate dir whose owning session is <id>, or whose
#                                     owner process is gone
#
# `open` stamps the dir with `.owner`: the session id, and the pid and start time of the Claude
# process the caller runs under (CLAUDE_CODE_SESSION_ID, CLAUDE_PID). The start time is what
# tells a live owner from a recycled pid. The plugin's SessionEnd hook sweeps the ending session's
# dirs and its SessionStart hook sweeps dead owners', so a session that crashed is cleaned up by
# the next one to start. A `review-gate*` path with no `.owner` — made outside `open` — is swept
# once it is a day old, since nothing says whether its maker is still reading it.
#
# Only paths matching `review-gate*` directly under `$TMPDIR` or `/tmp`, owned by this user, are
# ever touched. Removing a worktree's directory leaves its registration in the repo it came from,
# so each one is traced back through its `.git` file and that repo's `git worktree prune` runs
# after the delete.

set -u

ROOTS=("${TMPDIR:-/tmp}")
[ "${TMPDIR:-/tmp}" != /tmp ] && ROOTS+=(/tmp)
STALE_MINUTES=1440

proc_start() {  # <pid> — empty when the process does not exist
  ps -o lstart= -p "$1" 2>/dev/null | sed 's/^ *//'
}

owner_field() {  # <dir> <key>
  sed -n "s/^$2=//p" "$1/.owner" 2>/dev/null | head -1
}

# The common git dir of the repo a worktree's `.git` file points into.
common_dir() {  # <path to .git file>
  local admin
  admin="$(sed -n 's/^gitdir: //p' "$1" | head -1)"
  [ -n "$admin" ] || return 1
  case "$admin" in /*) ;; *) admin="$(dirname "$1")/$admin" ;; esac
  if [ -f "$admin/commondir" ]; then
    local c; c="$(cat "$admin/commondir")"
    case "$c" in /*) printf '%s\n' "$c" ;; *) printf '%s\n' "$admin/$c" ;; esac
  else
    dirname "$(dirname "$admin")"
  fi
}

remove_dir() {  # <dir>
  local d="$1" g repos=()
  [ -d "$d" ] && [ -O "$d" ] || return 0
  while IFS= read -r g; do
    repos+=("$(common_dir "$g")")
  done < <(find "$d" -maxdepth 2 -name .git -type f 2>/dev/null)
  rm -rf -- "$d"
  local r
  for r in "${repos[@]}"; do
    [ -n "$r" ] && [ -d "$r" ] && git --git-dir="$r" worktree prune 2>/dev/null
  done
  return 0
}

in_root() {  # <dir> — true when it is a review-gate path directly under a sweep root
  local root parent
  parent="$(cd "$(dirname "$1")" 2>/dev/null && pwd -P)" || return 1
  for root in "${ROOTS[@]}"; do
    [ "$parent" = "$(cd "$root" 2>/dev/null && pwd -P)" ] && return 0
  done
  return 1
}

sweep() {  # [session id]
  local session="${1:-}" root d pid started
  for root in "${ROOTS[@]}"; do
    for d in "$root"/review-gate*; do
      [ -d "$d" ] && [ -O "$d" ] || continue
      if [ -f "$d/.owner" ]; then
        if [ -n "$session" ] && [ "$(owner_field "$d" session)" = "$session" ]; then
          remove_dir "$d"; continue
        fi
        pid="$(owner_field "$d" pid)"; started="$(owner_field "$d" started)"
        if [ -z "$pid" ] || [ -z "$started" ] || [ "$(proc_start "$pid")" != "$started" ]; then
          remove_dir "$d"
        fi
      elif [ -n "$(find "$d" -maxdepth 0 -mmin +"$STALE_MINUTES" 2>/dev/null)" ]; then
        remove_dir "$d"
      fi
    done
  done
}

case "${1:-}" in
  open)
    d="$(mktemp -d "${TMPDIR:-/tmp}/review-gate.XXXXXX")" || exit 1
    if [ -n "${CLAUDE_PID:-}" ]; then
      printf 'session=%s\npid=%s\nstarted=%s\n' \
        "${CLAUDE_CODE_SESSION_ID:-}" "$CLAUDE_PID" "$(proc_start "$CLAUDE_PID")" >"$d/.owner"
    fi
    printf '%s\n' "$d"
    ;;
  close)
    [ -n "${2:-}" ] || { echo "gate_dir.sh close: no dir given" >&2; exit 2; }
    in_root "$2" && case "$(basename "$2")" in review-gate*) true ;; *) false ;; esac \
      || { echo "gate_dir.sh close: not a gate dir: $2" >&2; exit 2; }
    remove_dir "$2"
    ;;
  sweep)
    shift
    session="" background=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --session) session="${2:-}"; shift; [ $# -gt 0 ] && shift ;;
        --background) background=1; shift ;;
        *) echo "gate_dir.sh sweep: unknown argument $1" >&2; exit 2 ;;
      esac
    done
    if [ -n "$background" ]; then
      # Hooks are given seconds, and a probe's node_modules takes longer than that to delete, so
      # the sweep leaves the hook's process group rather than dying with it.
      args=(sweep); [ -n "$session" ] && args+=(--session "$session")
      if command -v setsid >/dev/null; then
        setsid bash "$0" "${args[@]}" </dev/null >/dev/null 2>&1 &
      else
        nohup bash "$0" "${args[@]}" </dev/null >/dev/null 2>&1 &
      fi
    else
      sweep "$session"
    fi
    ;;
  *)
    echo "usage: gate_dir.sh open | close <dir> | sweep [--session <id>] [--background]" >&2
    exit 2
    ;;
esac
