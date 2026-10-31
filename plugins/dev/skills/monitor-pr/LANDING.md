# Land the merge

Step 4a of [SKILL.md](SKILL.md). Four steps, in order, attended or `--unattended` alike.

1. **Tally.** Rounds, threads resolved, checks fixed, conflicts merged, and the ledger's
   convergence counts. Commits the worktree holds and the remote does not are pushed here,
   saying plainly that this opens a follow-up PR against the default branch.

2. **Sweep what is left open.** Three places:

   - the ledger's `open` and `fork` rows — a finding nobody settled, a question nobody
     answered;
   - questions this session asked and the user never came back to;
   - TODOs and follow-ups written into the PR description outside the ledger block.

   Decide each item yourself, filing where this repo's `AGENTS.md` says work items live:
   drop what you would argue against, saying why, and file the rest; one you can't call
   goes into the backlog, named in the report as your call. Done when every item is filed
   (listed with its number and priority) or dropped with its reason — or the sweep says
   *nothing left open*.

   A PR naming a Sentry issue (`## Sentry`, `Fixes <SENTRY_ID>`) has that issue resolved
   in the next release, at merge. Read its status; when the merge left it unresolved — a
   squash that dropped the footer — resolve it by hand now, with the numeric id from its
   URL:

   ```bash
   sentry api organizations/<org>/issues/<numeric id>/ --method PUT \
     -d '{"status":"resolved","statusDetails":{"inNextRelease":true}}'
   ```

   `sentry issue resolve <ID>` alone skips regression tracking, and `--in @next` names
   the release built from the local HEAD; use the `inNextRelease` form above.

3. **Clean up.** Invoke `clean-up-worktree` for the branch as a caller landing a merge: the
   merge is its approval, so it asks no confirmation, and a safety stop stays a question.
   Skip it, saying why, when step 1 pushed commits past the merge: that branch is live
   work again. The worktree it removes may be this session's directory, so every command
   after it takes absolute paths.

4. **Report, and close the tab.** The report is the tally, what was filed and what was cleaned,
   opened on a merge taken on the standing instruction by the line [GREEN.md](GREEN.md) sets.
   Inside herdr (`HERDR_ENV=1`), the tab closes when the landing leaves
   nothing to come back to:

   - step 3 removed both the worktree and the branch;
   - no item step 2 filed is `P0` or `P1`;
   - no question from this landing is waiting on the user.

   Then write the report and end the turn on
   this, its last action:

   ```bash
   bash <SKILL_DIR>/scripts/close-own-tab.sh
   ```

   It waits for the turn to end, stops this session and closes the tab. Otherwise the tab
   stays: write the report, say which condition held it open, and hand the user the `cd` to the main worktree
   that `clean-up-worktree` reports.
