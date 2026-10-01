#!/usr/bin/env bash
# Close the herdr tab this Claude session runs in, once the session's turn has ended.
# Usage: close-own-tab.sh
#
# Run it as the session's last action, then end the turn. It detaches at once, so it
# outlives the tool call. A session cannot wait on its own exit, so the detached half waits
# for herdr to report the agent idle, stops it with SIGTERM — never a stronger signal —
# waits for the process to be gone, and only then closes the tab. A tab that holds other
# panes keeps them: only this pane closes. Every failure leaves the tab open, which costs
# nothing. Prints CLOSE_SCHEDULED or SKIP <why>.
set -u

if [[ ${1-} == --detached ]]; then
  pid=$2 pane=$3 tab=$4
  herdr agent wait "$pane" --until idle --until done --timeout 600000 >/dev/null 2>&1 || exit 0
  kill -TERM "$pid" 2>/dev/null || exit 0
  for _ in $(seq 60); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
  kill -0 "$pid" 2>/dev/null && exit 0
  panes=$(herdr tab get "$tab" 2>/dev/null | jq -r '.result.tab.pane_count // empty')
  if [[ $panes == 1 ]]; then herdr tab close "$tab"; else herdr pane close "$pane"; fi >/dev/null 2>&1
  exit 0
fi

[[ ${HERDR_ENV-} == 1 && -n ${HERDR_PANE_ID-} && -n ${HERDR_TAB_ID-} ]] || { echo "SKIP not in a herdr pane"; exit 0; }

# The session is the nearest `claude` ancestor of this shell.
pid=$$
while [[ $pid -gt 1 && $(ps -o comm= -p "$pid") != claude ]]; do
  pid=$(ps -o ppid= -p "$pid" | tr -d ' ')
done
[[ $pid -gt 1 ]] || { echo "SKIP no claude ancestor"; exit 0; }

self=$(realpath "$0")
cd / && setsid -f bash "$self" --detached "$pid" "$HERDR_PANE_ID" "$HERDR_TAB_ID" </dev/null >/dev/null 2>&1
echo CLOSE_SCHEDULED
