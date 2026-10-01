#!/usr/bin/env bash
# Grades one create-pull-request run in an api fixture from the branch it pushed, its
# commits and the recorded `gh pr create` / `gh pr edit` calls: one line per check,
# `PASS <name>`, `FAIL <name> <reason>` or `SKIP <name> <reason>`.
set -uo pipefail
cd "$EVAL_FIXTURE" || exit 1
exec python3 "$(dirname "$0")/check.py"
