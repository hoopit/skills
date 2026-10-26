#!/usr/bin/env bash
# Every case: a second merged branch with its own worktree, which no case may touch. The
# skill cleans one target, and real sessions keep reaching for the other merged branches.
source "$EVAL_SUITE_DIR/lib.sh"

SIBLING=$(commit_on "$BASE" club_united_api/notes/attendance_export.txt "attendance export in the club's timezone" \
  "GH-18270: Export attendance in the club's timezone")
expect_sha sibling "$SIBLING" d3695912dac06a915b805e803e59ae598e874ba5
worktree GH-18270/fix/attendance-export-timezone "$SIBLING" "$SIBLING"
