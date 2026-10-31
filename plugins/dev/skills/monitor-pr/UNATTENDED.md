# Unattended: act, then ask

The `--unattended` branch of [SKILL.md](SKILL.md)'s Step 5; steps and paths named here
are that file's.

Under `--unattended` a question waits for someone who may never come, so every
**reversible** choice takes your own recommendation. A soft fork is reversible: its ledger
row reads `decided unattended: <the choice>`, and the round's push carries it. Two kinds
stay questions, asked as Step 5 says:

- **an irreversible move** — deleting work that exists nowhere else, and a run owed before
  merge ([GREEN.md](GREEN.md));
- **a decision you doubt** — a hard fork, a stop, a `GATE_STUCK`, a checkpoint that stops, and any
  recommendation you hold without the evidence to defend it to a reviewer.

## A `GREEN` with only the merge left

The merge stays the user's call unless they handed it over ([GREEN.md](GREEN.md)), and they
make it from the PR, so it holds no session open and takes no question. Once
[GREEN.md](GREEN.md) has run to the hand-off and the Step 4a sweep has run, **leave** when all
of these hold for this head:

- the PR is ready and its briefing recommends the merge;
- no approval or run is owed, and the `GREEN` carries no `pending_gates`;
- no ledger `fork` row stays open, no item the sweep filed is `P0` or `P1`, and nothing else
  waits on the user.

Anything short of that takes the Green path's question. Leave in this order:

1. Post what the chat would have carried, the verdict, the debrief and each decision taken, as
   a comment on the PR with `gh pr comment`. Done when closing the tab would lose nothing.
2. Stop the watch and drop the labels (`-monitored -agent-working`).
3. Remove the worktree and local branch where the remote holds all of it, then take absolute
   paths from here on. The push is the only copy of them that stays, and a later round makes a
   fresh worktree from it:

   ```bash
   main=$(git worktree list --porcelain | sed -n '1s/^worktree //p')
   [ -z "$(git status --porcelain)" ] && [ "$(git rev-parse HEAD)" = "<head sha>" ] &&
     git -C "$main" worktree remove "$(git rev-parse --show-toplevel)" &&
     git -C "$main" branch -D "<branch>"
   ```

   A worktree that fails the check stays, and the comment names it.
4. End the turn on `bash <SKILL_DIR>/scripts/close-own-tab.sh`, as
   [LANDING.md](LANDING.md)'s last step does, with no notification: the ready PR is the signal.

Nothing watches the PR after this. A review thread or failing check that arrives later waits
for the user, who starts `monitor-pr` on it to have it worked.

## The ending

Every other ending closes on its `AskUserQuestion`, exactly as attended: the alert is the only
thing that reaches a user who comes back. The chat above it opens with **what was done** —
each decision taken with its ledger row, each issue filed with its number, each clean-up
run — so the user can reverse any of them.

A `GREEN` first runs Step 4a's left-open sweep, filing as it says, and puts a **debrief**
after the briefing: everything relevant the briefing leaves out, each recommendation still
outstanding, and what Step 4a would still do on a merge — commits to push, the clean-up.

Done when closing the session would lose nothing: every decision is on the ledger, every
finding is on the tracker, and the question holds only what the user alone can settle.
