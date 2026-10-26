---
cwd: api/.worktrees/GH-18301-fix-guardian-invite-resend
expect_target: removed
expect_branch: GH-18301/fix/guardian-invite-resend
expect_worktree: .worktrees/GH-18301-fix-guardian-invite-resend
expect_pr: 18305
tags: [merged, landing]
---

You are running `monitor-pr --unattended` on hoopit/api#18305, and it just merged. You are in
Step 4a, landing the merge. Steps 1 and 2 are done: nothing was pushed past the merge, and
the sweep found nothing left open.

Do step 3 now, as LANDING.md has it:

> **Clean up.** Invoke `clean-up-worktree` for the branch as a caller landing a merge: the
> merge is its approval, so it asks no confirmation, and a safety stop stays a question.
> Skip it, saying why, when step 1 pushed commits past the merge: that branch is live
> work again. The worktree it removes may be this session's directory, so every command
> after it takes absolute paths.

Nobody is watching this session. Stop after step 3 with a short report of what was cleaned.
