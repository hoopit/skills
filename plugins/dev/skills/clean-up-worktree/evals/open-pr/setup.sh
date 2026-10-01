#!/usr/bin/env bash
source "$EVAL_SUITE_DIR/lib.sh"

TIP=$(commit_on "$BASE" club_united_api/notes/venue_search.txt "search venues by postcode" \
  "GH-18312: Search venues by postcode")
expect_sha tip "$TIP" a29f6ba89c6a22fcc38b4d1df5f2330a005e2c9d
worktree GH-18312/feat/venue-postcode-search "$TIP" "$TIP"
