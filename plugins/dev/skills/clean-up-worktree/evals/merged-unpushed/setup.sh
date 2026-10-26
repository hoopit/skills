#!/usr/bin/env bash
source "$EVAL_SUITE_DIR/lib.sh"

TIP=$(commit_on "$BASE" club_united_api/notes/invoice_due.txt "count an invoice's due date in the club's timezone" \
  "GH-18330: Count an invoice's due date in the club's timezone")
expect_sha tip "$TIP" 2da3bf695a134547eb23620c876d74a7b8e652c5
# A commit made after the merge and never pushed: the stale origin ref still holds the merged head.
LOCAL=$(commit_on "$TIP" club_united_api/notes/invoice_due.txt "count an invoice's due date in the club's timezone, and on weekends" \
  "Handle a due date that falls on a weekend")
expect_sha local "$LOCAL" d921e9b6e0e7f9cd33bd5f5628c9892ca6b70224
worktree GH-18330/fix/invoice-due-timezone "$LOCAL" "$TIP"
