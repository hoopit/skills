#!/usr/bin/env bash
# Close the herdr tab this Claude session runs in, once the session's turn has ended.
# Usage: close-own-tab.sh
#
# Run it as the session's last action, then end the turn. It detaches at once, so it
# outlives the tool call. A session cannot wait on its own exit, so the detached half waits
# for herdr to report the agent idle, stops it with SIGTERM — never a stronger signal —
# waits for the process to be gone, and only then closes the tab. A tab that holds other
# panes keeps them: only this pane closes. Every failure leaves the tab open, which costs
# nothing, and the detached half logs why to $LOG. Prints CLOSE_SCHEDULED or SKIP <why>.
#
# The pane is found by the Claude session id herdr records on it. HERDR_PANE_ID and
# HERDR_TAB_ID are set once at spawn and name a pane that no longer exists after a move.
set -u

LOG=${XDG_STATE_HOME:-$HOME/.local/state}/close-own-tab.log

# Prints "<pane_id> <tab_id>" for the pane running Claude session $1, or nothing.
pane_of_session() {
  herdr pane list 2>/dev/null | jq -r --arg s "$1" \
    'first(.result.panes[] | select(.agent_session.value == $s) | "\(.pane_id) \(.tab_id)") // empty'
}

if [[ ${1-} == --detached ]]; then
  pid=$2 session=$3
  give_up() {
    mkdir -p "$(dirname "$LOG")" && printf '%s session=%s %s\n' "$(date -Is)" "$session" "$1" >>"$LOG"
    exit 0
  }
  read -r pane _ <<<"$(pane_of_session "$session")"
  [[ -n $pane ]] || give_up "no herdr pane carries the session"
  herdr agent wait "$pane" --until idle --until 'done' --timeout 600000 >/dev/null 2>&1 ||
    give_up "agent $pane did not go idle"
  # Read again: the pane may have moved while the turn ran, and the session id is gone
  # from it once Claude exits.
  read -r pane tab <<<"$(pane_of_session "$session")"
  [[ -n $pane ]] || give_up "no herdr pane carries the session after the turn"
  kill -TERM "$pid" 2>/dev/null || give_up "SIGTERM to $pid failed"
  for _ in $(seq 60); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
  kill -0 "$pid" 2>/dev/null && give_up "$pid outlived SIGTERM"
  panes=$(herdr tab get "$tab" 2>/dev/null | jq -r '.result.tab.pane_count // empty')
  if [[ $panes == 1 ]]; then herdr tab close "$tab"; else herdr pane close "$pane"; fi >/dev/null 2>&1 ||
    give_up "closing $tab ($panes panes) failed"
  exit 0
fi

[[ ${HERDR_ENV-} == 1 ]] || { echo "SKIP not in a herdr pane"; exit 0; }
session=${CLAUDE_CODE_SESSION_ID-}
[[ -n $session ]] || { echo "SKIP no CLAUDE_CODE_SESSION_ID"; exit 0; }
[[ -n $(pane_of_session "$session") ]] || { echo "SKIP no herdr pane carries session $session"; exit 0; }

# The session is the nearest `claude` ancestor of this shell.
pid=$$
while [[ $pid -gt 1 && $(ps -o comm= -p "$pid") != claude ]]; do
  pid=$(ps -o ppid= -p "$pid" | tr -d ' ')
done
[[ $pid -gt 1 ]] || { echo "SKIP no claude ancestor"; exit 0; }

self=$(realpath "$0")
cd / && setsid -f bash "$self" --detached "$pid" "$session" </dev/null >/dev/null 2>&1
echo CLOSE_SCHEDULED
