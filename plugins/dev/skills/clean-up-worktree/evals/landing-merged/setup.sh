#!/usr/bin/env bash
source "$EVAL_SUITE_DIR/lib.sh"

TIP=$(commit_on "$BASE" club_united_api/notes/guardian_invite.txt "resend a guardian invite that bounced" \
  "GH-18301: Resend a guardian invite that bounced")
expect_sha tip "$TIP" a5f49ad519e129e16073f6f9cb7b9c8f0df1eb6b
worktree GH-18301/fix/guardian-invite-resend "$TIP" "$TIP"
