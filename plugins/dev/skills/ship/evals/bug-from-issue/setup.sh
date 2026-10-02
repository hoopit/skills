#!/usr/bin/env bash
# The session begins in the triage checkout, not in api: TARGET_REPO is ../api.
set -euo pipefail
mkdir -p "$EVAL_RUN_DIR/triage"
git -C "$EVAL_RUN_DIR/triage" init -q
