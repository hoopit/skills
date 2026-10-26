#!/usr/bin/env bash
# The change for BAC-7851, uncommitted on master: a 10-minute cooldown.
set -euo pipefail
e="$EVAL_SUITE_DIR/edit.py"
python3 "$e" events/notifications/occurrence_urgent_response_reminder_notification.py "COOLDOWN = timedelta(minutes=15)" "COOLDOWN = timedelta(minutes=10)"
python3 "$e" events/tests/test_notifications/test_occurrence_urgent_response_reminder_notification.py "sent_ago=timedelta(minutes=14)" "sent_ago=timedelta(minutes=9)"
python3 "$e" events/tests/test_notifications/test_occurrence_urgent_response_reminder_notification.py "sent_ago=timedelta(minutes=16)" "sent_ago=timedelta(minutes=11)"
