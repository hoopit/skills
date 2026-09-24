#!/usr/bin/env bash
# SessionStart / SessionEnd hook: sweep review-gate dirs in the background (see gate_dir.sh).
# On SessionEnd the ending session's own dirs go too — its Claude process is still alive while
# the hook runs, so the dead-owner rule alone would keep them. The hook never fails the session.
input="$(cat)"
event="$(printf '%s' "$input" | sed -n 's/.*"hook_event_name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)"
session="$(printf '%s' "$input" | sed -n 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)"
args=(sweep --background)
[ "$event" = SessionEnd ] && [ -n "$session" ] && args+=(--session "$session")
bash "$(dirname "$0")/gate_dir.sh" "${args[@]}" || true
exit 0
