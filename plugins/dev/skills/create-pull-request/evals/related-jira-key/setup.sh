#!/usr/bin/env bash
# The change for hoopit/api#18302, uncommitted on master: the cooldown says why it is 15
# minutes, citing the tickets it came from. A key in code is not a linked surface; the
# agent describing this comment puts it on one.
set -euo pipefail
python3 "$EVAL_SUITE_DIR/edit.py" events/notifications/occurrence_urgent_response_reminder_notification.py "    COOLDOWN = timedelta(minutes=15)" \
"    # BAC-7793's acceptance criteria: long enough to cover an organizer pressing twice, short
    # enough to leave room for a second wave. BAC-7801 asked for 30 minutes and was declined:
    # organizers send that wave about 20 minutes before meetup, and 30 would swallow it.
    COOLDOWN = timedelta(minutes=15)"
