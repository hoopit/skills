#!/usr/bin/env bash
# The lifecycle of a review-gate pass's scratch directory — its findings files and every probe
# worktree a reviewer builds inside it — kept out of the agent's hands, because a pass that
# aborts, is interrupted or hands back early never reaches a prose teardown step. Probe worktrees
# run to ~65k files apiece once `.venv` or `node_modules` is in.
#
# Usage:  gate_dir.sh open            create a gate dir owned by this Claude session; prints its path
#         gate_dir.sh close <dir>     remove one gate dir and deregister the worktrees inside it
#         gate_dir.sh sweep [--session <id>] [--background]
#                                     remove every gate dir whose owning session is <id>, whose
#                                     owner process is gone, or that has sat idle (IDLE_MINUTES)
#
# Gate dirs live in `review-gate-dirs` under the user's cache dir (`$XDG_CACHE_HOME`, else
# `~/.cache`) on Linux, macOS and Windows alike, never in `$TMPDIR`: a tmpfs `/tmp` caps its
# inodes, and a few passes running at once exhaust them for the whole machine. The cache dir also
# shares a filesystem with uv's cache, so uv hardlinks or clones a probe's venv in rather than
# copying it file by file. The root is a sibling of run_external_reviewers.sh's `review-gate`
# cache, never inside it: that cache's age prune deletes old-mtime files, and a hardlinked venv's
# files carry the mtime of uv's cache.
#
# `open` stamps the dir with `.owner`: the session id, and the pid and start time of the Claude
# process the caller runs under (CLAUDE_CODE_SESSION_ID, CLAUDE_PID). The start time is what
# tells a live owner from a recycled pid; where it cannot be read, the dir waits for its session's
# end or the idle rule. The plugin's SessionEnd hook sweeps the ending session's dirs, and its
# SessionStart hook and every `open` sweep dead owners' and idle ones, so a session that crashed is
# cleaned up by the next one to start. The idle rule is what reaches a pass that stopped without
# closing inside a session still running, and a `review-gate*` path with no `.owner`: nothing in
# the dir written for a day. A day, because a pass on a suspended laptop writes nothing while it
# sleeps, and a pass whose dir is swept from under it has to run again.
#
# Only paths matching `review-gate*` directly under the root, owned by this user, are ever
# touched. Removing a worktree's directory leaves its registration in the repo it came from, so
# each one is traced back through its `.git` file and that repo's `git worktree prune` runs after
# the delete.

set -u

GATE_ROOT="${XDG_CACHE_HOME:-$HOME/.cache}/review-gate-dirs"
IDLE_MINUTES=1440

proc_start() {  # <pid> — empty when the process does not exist
  ps -o lstart= -p "$1" 2>/dev/null | sed 's/^ *//'
}

owner_field() {  # <dir> <key>
  sed -n "s/^$2=//p" "$1/.owner" 2>/dev/null | head -1
}

# Git for Windows writes absolute paths as `C:/...`.
is_abs() {
  case "$1" in /*|[A-Za-z]:[/\\]*) return 0 ;; *) return 1 ;; esac
}

# The common git dir of the repo a worktree's `.git` file points into.
common_dir() {  # <path to .git file>
  local admin
  admin="$(sed -n 's/^gitdir: //p' "$1" | head -1)"
  [ -n "$admin" ] || return 1
  is_abs "$admin" || admin="$(dirname "$1")/$admin"
  if [ -f "$admin/commondir" ]; then
    local c; c="$(cat "$admin/commondir")"
    if is_abs "$c"; then printf '%s\n' "$c"; else printf '%s\n' "$admin/$c"; fi
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
  # The `+` form keeps an empty array from tripping `set -u` in bash 3.2 (macOS).
  for r in ${repos[@]+"${repos[@]}"}; do
    [ -n "$r" ] && [ -d "$r" ] && git --git-dir="$r" worktree prune 2>/dev/null
  done
  return 0
}

in_root() {  # <dir> — true when it sits directly under GATE_ROOT
  local parent
  parent="$(cd "$(dirname "$1")" 2>/dev/null && pwd -P)" || return 1
  [ "$parent" = "$(cd "$GATE_ROOT" 2>/dev/null && pwd -P)" ]
}

idle() {  # <dir> — true when nothing in it was written within IDLE_MINUTES
  [ -z "$(find "$1" -mmin -"$IDLE_MINUTES" -print 2>/dev/null | head -n 1)" ]
}

sweep() {  # [session id]
  local session="${1:-}" d pid started
  for d in "$GATE_ROOT"/review-gate*; do
    [ -d "$d" ] && [ -O "$d" ] || continue
    if [ -f "$d/.owner" ]; then
      if [ -n "$session" ] && [ "$(owner_field "$d" session)" = "$session" ]; then
        remove_dir "$d"; continue
      fi
      # An empty `started` means `open` could not read the owner's start time (Git Bash's `ps`
      # has no `-o`), so liveness is unknown: only the session's end or the idle rule removes it.
      pid="$(owner_field "$d" pid)"; started="$(owner_field "$d" started)"
      if [ -n "$started" ] && [ "$(proc_start "$pid")" != "$started" ]; then
        remove_dir "$d"; continue
      fi
    fi
    idle "$d" && remove_dir "$d"
  done
}

sweep_in_background() {  # [session id]
  # Hooks are given seconds, and a probe's `.venv` or `node_modules` takes longer than that to
  # delete, so the sweep leaves the caller's process group rather than dying with it.
  local args=(sweep); [ -n "${1:-}" ] && args+=(--session "$1")
  if command -v setsid >/dev/null; then
    setsid bash "$0" "${args[@]}" </dev/null >/dev/null 2>&1 &
  else
    nohup bash "$0" "${args[@]}" </dev/null >/dev/null 2>&1 &
  fi
}

case "${1:-}" in
  open)
    mkdir -p "$GATE_ROOT" || exit 1
    d="$(mktemp -d "$GATE_ROOT/review-gate.XXXXXX")" || exit 1
    if [ -n "${CLAUDE_PID:-}" ]; then
      printf 'session=%s\npid=%s\nstarted=%s\n' \
        "${CLAUDE_CODE_SESSION_ID:-}" "$CLAUDE_PID" "$(proc_start "$CLAUDE_PID")" >"$d/.owner"
    fi
    printf '%s\n' "$d"
    sweep_in_background
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
      sweep_in_background "$session"
    else
      sweep "$session"
    fi
    ;;
  *)
    echo "usage: gate_dir.sh open | close <dir> | sweep [--session <id>] [--background]" >&2
    exit 2
    ;;
esac
