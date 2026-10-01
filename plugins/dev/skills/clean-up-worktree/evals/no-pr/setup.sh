#!/usr/bin/env bash
source "$EVAL_SUITE_DIR/lib.sh"

TIP=$(commit_on "$BASE" club_united_api/notes/stale_tokens.txt "drop push tokens unused for a year" \
  "GH-18320: Drop push tokens unused for a year")
expect_sha tip "$TIP" da437a9e351f320d48c6847d52d3bb3fa5bae735
# never pushed: no upstream
worktree GH-18320/chore/stale-push-tokens "$TIP"
