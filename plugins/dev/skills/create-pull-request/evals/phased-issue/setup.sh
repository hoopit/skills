#!/usr/bin/env bash
# Step 1 of hoopit/api#18303, uncommitted on master: nothing reads SLOW_SQL_LOGGING.
set -euo pipefail
e="$EVAL_SUITE_DIR/edit.py"
python3 "$e" club_united_api/settings/default.py \
'SLOW_SQL_LOGGING = os.environ.get("SLOW_SQL_LOGGING", "false").lower() == "true"
"""Enable this to print slow SQL queries to the console."""
' ''
python3 "$e" club_united_api/views/base_view.py \
'    def dispatch(self, request, *args, **kwargs):
        if settings.SLOW_SQL_LOGGING:
            with SqlLoggerContext(verbose=False, log=True, name=self.__class__.__name__):
                return super().dispatch(request, *args, **kwargs)
        return super().dispatch(request, *args, **kwargs)

' ''
python3 "$e" club_united_api/views/base_view.py 'from django.conf import settings
' ''
python3 "$e" club_united_api/views/base_view.py \
'from club_united_api.debugging.debug_sql_context import SqlLoggerContext
' ''
python3 "$e" .envs/prod.env 'SLOW_SQL_LOGGING=True
' ''
