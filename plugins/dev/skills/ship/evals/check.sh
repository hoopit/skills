#!/usr/bin/env bash
# Grades one ship run from the calls it made and the state it left: one line per check,
# `PASS <name>`, `FAIL <name> <reason>` or `SKIP <name> <reason>`. Then drops the run's
# test database, which setup.sh cloned for it.
cd "$EVAL_FIXTURE" || exit 1
python3 "$(dirname "$0")/check.py"
code=$?
if [[ -f $EVAL_RUN_DIR/test-db ]]; then
  db=$(cat "$EVAL_RUN_DIR/test-db")
  export PGHOST=127.0.0.1 PGPORT=5435 PGUSER=postgres PGPASSWORD=
  for name in $(psql -Atc "select datname from pg_database where datname = '$db' or datname like '${db}\_gw%'"); do
    psql -qc "drop database if exists \"$name\" with (force)" >/dev/null 2>&1
  done
fi
exit $code
