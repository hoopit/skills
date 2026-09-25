# Land the merge

Step 4a of [SKILL.md](SKILL.md).

Three things follow the merge, in order.

**Tally.** Rounds, threads resolved, checks fixed, conflicts merged, and the ledger's
convergence counts. The ledger stays on the merged PR as the record of what was judged
along the way. One thing outlives the PR and is carried into the tally: commits the worktree holds and the remote does not — push
them, saying plainly that this opens a follow-up PR against the default branch.

**Report what is left open.** The merge closes the PR, not the thinking, so sweep three
places and list what survives:

- the ledger's `open` and `fork` rows — a finding nobody settled, a question nobody
  answered;
- questions this session asked and the user never came back to;
- TODOs and follow-ups written into the PR description outside the ledger block.

Offer to file them where this repo's `AGENTS.md` says work items live — one line per
proposed item, title and a sentence — and file only what the user picks. Under
`--unattended`, file them all and list each with its number; one whose worth is a
judgement is filed marked as needing the user's decision, that decision named in its
body. An empty sweep is worth saying out loud: *nothing left open.*

**Clean up, last.** The branch is spent, so invoke `clean-up-worktree` for it; its own
merge gate and safety checks stand, and its confirmation is the one place this is
approved. Skip it — saying why — when the tally just pushed commits past the merge: that
branch is live work again, not spent.

This goes last because it is the one irreversible move, and because the worktree it
removes may be the directory this session is running in — `ship` arms the watch from
inside it. Once it is gone, the shell has no working directory and nothing further runs.
Finish the tally and the sweep first, then hand the user the `cd` to the main worktree
that `clean-up-worktree` reports.
