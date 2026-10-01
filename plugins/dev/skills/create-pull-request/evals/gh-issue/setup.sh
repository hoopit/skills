#!/usr/bin/env bash
# The change for hoopit/api#18301, uncommitted on master: a 30-minute cooldown.
set -euo pipefail
e="$EVAL_SUITE_DIR/edit.py"
python3 "$e" events/notifications/occurrence_urgent_response_reminder_notification.py "COOLDOWN = timedelta(minutes=15)" "COOLDOWN = timedelta(minutes=30)"
python3 "$e" events/tests/test_notifications/test_occurrence_urgent_response_reminder_notification.py "sent_ago=timedelta(minutes=14)" "sent_ago=timedelta(minutes=29)"
python3 "$e" events/tests/test_notifications/test_occurrence_urgent_response_reminder_notification.py "sent_ago=timedelta(minutes=16)" "sent_ago=timedelta(minutes=31)"
