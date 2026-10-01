#!/usr/bin/env bash
source "$EVAL_SUITE_DIR/lib.sh"

TIP=$(commit_on "$BASE" club_united_api/notes/price_option.txt "hide archived price options" \
  "GH-18340: Hide archived price options from the signup form")
expect_sha tip "$TIP" 87a67e36215a741ec0967d6efdad3398c7ede387
worktree GH-18340/fix/archived-price-options "$TIP" "$TIP"
