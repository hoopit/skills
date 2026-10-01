# Land the merge

Step 4a of [SKILL.md](SKILL.md).

Four things follow the merge, in order, attended or `--unattended` alike.

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

Decide each one yourself rather than putting it to the user: this session knows the work
better than a question would carry it. File it where this repo's `AGENTS.md` says work items
live — a sure item as itself, one whose worth is a judgement in `Backlog` marked as needing
the user's decision, that decision named in its body — or drop one the merge already
settled, saying why. Ask only when you cannot decide even that (which repo it belongs to,
whether it is real at all), as Step 5 asks. List each filed item with its number and
priority. An empty sweep is worth saying out loud: *nothing left open.*

**Clean up.** The branch is spent, so invoke `clean-up-worktree` for it as a caller landing
a merge: the merge is its approval, so it asks no confirmation. Its own merge gate and
safety checks stand, and a safety stop stays a question. Skip it — saying why — when the
tally just pushed commits past the merge: that branch is live work again, not spent.

This follows the tally and the sweep because it is the one irreversible move, and because
the worktree it removes may be the directory this session is running in — `ship` arms the
watch from inside it. Once it is gone, the shell has no working directory: every command
after it takes absolute paths.

**Close the tab, last.** Inside herdr (`HERDR_ENV=1`), a landing that leaves nothing to come
back to closes its own tab. Nothing is left when all of these hold:

- clean-up removed both the worktree and the branch;
- no follow-up the sweep filed is `P0` or `P1`;
- no question from this landing is waiting on the user.

Then write the report — tally, what was filed, what was cleaned — and run, as the turn's
last action:

```bash
bash <SKILL_DIR>/scripts/close-own-tab.sh
```

It waits for the turn to end, stops this session and closes the tab. When any condition
fails, or outside herdr, the tab stays: say which condition held it open, and hand the user
the `cd` to the main worktree that `clean-up-worktree` reports.
