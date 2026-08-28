---
name: clean-up-worktree
description: After this conversation's PR is merged, delete the branch and worktree this conversation worked in — and nothing else. Use when the user asks to clean up after a merged PR, or to remove the worktree/branch of the work just finished.
---

# Cleaning Up After This Conversation's Merged PR

Removes the worktree directory and local branch of **the work this conversation did**, once
GitHub confirms its PR is merged. Counterpart to the worktree made in `implement-and-ship-fix`
Step 2 — or by the repo's own `create-worktree` skill, when it has one.

## Scope — one target

The target is the single branch this conversation worked in. Resolve it in this order,
stopping at the first hit:

1. The worktree this session is running in (`git rev-parse --show-toplevel`), when that is
   not the main worktree.
2. The branch this conversation created or worked on (from the conversation itself, or the
   branch its PR was opened from). Say the name back and get a yes before touching it.
3. Neither is knowable → ask the user which branch, and stop until they answer.

Every step below acts on that one resolved target. Other stale branches and worktrees are
the user's business, not this run's.

If the target is the main worktree or the repo's default branch (the `DEFAULT_BRANCH` line
`inspect.sh` prints), there is nothing to clean. Say so and stop.

## 1. Inspect the target

```bash
INSPECT=$(find ~/.claude/plugins -path '*clean-up-worktree/scripts/inspect.sh' | head -1)
bash "$INSPECT"           # this session's worktree
bash "$INSPECT" <branch>  # a named branch
```

Read-only, single target. Every fact the gates below need is in its output — read the output
rather than re-deriving any of it. No fetch is needed first: merge state comes from GitHub
live via `gh`, not from local refs.

## 2. Gate on the merge — this is the whole point

Delete only when the PR state is **`MERGED`**. Anything else stops the run with a report
and **zero deletions**:

| PR state | Action |
|---|---|
| `MERGED` | proceed to the safety checks |
| `OPEN` | stop — still in flight. Say so; offer nothing else. |
| `CLOSED` (unmerged) | stop — never shipped. Only continue if the user explicitly says to delete it anyway. |
| no PR found | stop — report that there is no PR for this branch and ask before deleting anything. |

"Merged" means GitHub says `MERGED`. Never infer it from `git branch --merged`, an ancestry
check, the branch name, or a commit subject — these repos squash-merge, so a merged branch's
commits are *not* ancestors of the default branch.

## 3. Safety checks

Even with a merged PR, stop and ask (naming the concrete cost) when:

- the worktree is **dirty** — list the files; `git worktree remove --force` discards them;
- the branch has **unpushed commits** — quote the `UNPUSHED_COMMIT` lines; they exist only
  here;
- `TIP_MATCHES_PR` is **no** — the PR was matched by branch *name*, and this branch's tip
  is not the commit that got merged (a reused branch name, or commits added after the
  merge). Quote both shas and say which commits differ before deleting anything.

Any fact the script could not establish is also a stop: `PR_LOOKUP_FAILED`,
`TIP_MATCHES_PR unknown`, `UNPUSHED ?`, `WORKTREE_DIRTY unknown`. Each means the gate
could not be evaluated — which is not the same as passing it. Report what failed and let
the user decide; never read a missing line as an all-clear.

So is a `GUARD WORKTREE_OUTSIDE_MANAGED_ROOT` line: the branch is checked out somewhere
other than `.claude/worktrees/` or `.worktrees/`, so it may be a checkout unrelated to this
workflow. Quote the path and let the user confirm it.

Leave the remote branch alone — GitHub deletes it on merge, and its stale remote-tracking
ref is harmless.

## 4. Confirm

One short confirmation naming the branch, the PR with the state actually observed
(`#2619 MERGED`, or `#2619 CLOSED (unmerged)` when the user is overriding that gate), and
the worktree path to be removed. Nothing runs until the user says yes.

Then re-run `inspect.sh` immediately before deleting: if PR state, `TIP_MATCHES_PR`,
unpushed count or dirty count moved since the confirmation, abort and re-confirm. Approval
covers the state the user was shown, not whatever the target looks like later.

## 5. Execute — from the main worktree

A worktree cannot remove itself, but git will remove it when the command runs against the
main worktree, even if it is your current directory. Resolve `MAIN_ROOT` **first**, then
use `git -C "$MAIN_ROOT"` for every command — after the removal this session's cwd no
longer exists.

Fill `BRANCH` and `WORKTREE` from the `TARGET_BRANCH` / `TARGET_WORKTREE` lines
`inspect.sh` printed for the confirmed target. **Never re-derive them from the session**
(`git rev-parse --show-toplevel`, `git symbolic-ref HEAD`): for a target named by branch
rather than by cwd, those resolve to *this* session's worktree and branch — the wrong
thing to delete. `TARGET_WORKTREE` of `-` means the branch has no worktree; delete only
the branch.

```bash
# substr, not $2: worktree paths may contain spaces
MAIN_ROOT=$(git worktree list --porcelain | awk '/^worktree /{print substr($0, 10); exit}')
BRANCH="<TARGET_BRANCH from inspect.sh>"
WORKTREE="<TARGET_WORKTREE from inspect.sh, or - if none>"

if [[ $WORKTREE != "-" ]]; then
  # || exit: if removal fails, do NOT fall through to branch -D — that would leave a
  # worktree whose branch is gone, a worse state than the one you started in.
  git -C "$MAIN_ROOT" worktree remove "$WORKTREE" || exit 1   # --force only if the dirty worktree was approved
fi
git -C "$MAIN_ROOT" branch -D "$BRANCH"            # -D, not -d: a squash-merged branch is never "fully merged"
```

Those two commands are the whole removal — a successful `git worktree remove` already clears
its own administrative record, so nothing needs pruning afterwards.

Removing the worktree deletes its directory, so the untracked setup inside it — env files,
SDK symlinks, dependency and build output — goes with it. If `git worktree remove` reports
"contains modified or untracked files", stop and report; reach for `--force` only for a
worktree the user approved as dirty.

## 6. Verify and report

Verify both halves separately from `$MAIN_ROOT` — `inspect.sh <branch>` exits 1 with
`BRANCH_EXISTS no` once the branch is gone, which proves nothing about the directory:

```bash
git -C "$MAIN_ROOT" rev-parse --verify "refs/heads/$BRANCH"   # must fail: branch gone
test ! -e "$WORKTREE" && echo "worktree directory gone"
git -C "$MAIN_ROOT" worktree list                             # must no longer list it
```

Then report:

- what was deleted — branch, PR number, worktree path;
- that this session's working directory no longer exists, so further work continues from
  `$MAIN_ROOT` (`cd "$MAIN_ROOT"`);
- the recovery line: `git branch <name> <sha>` restores the branch, using the sha printed
  by `git branch -D`.
