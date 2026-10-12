#!/usr/bin/env bash
# Grades one review-github-comments round on the state it leaves: the PR as github.py holds it
# (replies, resolves, dismissals, labels, re-review runs), the PR branch here and on the per-run
# origin. One line per check: `PASS <name>`, `FAIL <name> <reason>` or `SKIP <name> <reason>`.
set -uo pipefail
cd "$EVAL_FIXTURE" || exit 1
exec python3 "$(dirname "$0")/check.py"
