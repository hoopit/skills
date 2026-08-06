# Conflict procedure

One axis of a **babysit-prs** per-PR pass: this PR's `mergeable` is `CONFLICTING`
(or `mergeStateStatus` is `DIRTY`). Read this file only when your prompt flagged the
merge-conflict axis.

Read the skill's *Per-PR procedures* preamble (the confidence rule) and its *Safety*
section in [`../SKILL.md`](../SKILL.md) first — every rule there governs every step
here, and nothing below repeats them.

Every `<...>` below is a value from your worker prompt. `WORKTREE_DIR` means the
literal absolute **conflicts** worktree dir it assigned
(`<REPO_ROOT>/.worktrees/babysit-<number>`). The step numbers here are this
procedure's own; they are not the orchestrator's Steps 1–5.

**Each command block runs in a fresh shell.** Your tool calls do not share an
environment, so a variable assigned in one block is *empty* in the next — and an
empty `WORKTREE_DIR` turns `git -C "$WORKTREE_DIR" clean -fd` into a `clean` of
whatever directory you happen to be in. Every block below therefore re-assigns
`WORKTREE_DIR` on its first line; keep that line when you run the block, with the
literal path substituted.

State that must outlive a block is kept in a **git ref**, not a variable: step 2
saves the PR head as `refs/babysit/pr-<number>-head`, which survives every shell,
every `reset`, and every `clean` in this file. Steps 3–5 read it back by name — so
there is no `PR_HEAD_SHA` to carry between blocks. Step 7 deletes it.

1. **Check the branch out in isolation** — never disturb the user's working tree. If
   the repo defines its own worktree skill (e.g.
   `.claude/skills/create-worktree/SKILL.md`), read and follow it — it owns venv /
   test-DB / direnv / toolchain setup. Otherwise:

   ```bash
   git fetch origin
   WORKTREE_DIR="<your assigned conflicts worktree dir>"   # <REPO_ROOT>/.worktrees/babysit-<number>
   git worktree add "$WORKTREE_DIR" "origin/<headRefName>"
   ```

   This lands on a **detached HEAD** at the remote tip — deliberately, so it can't
   collide with a stale local branch of the same name. It changes how you push (step
   5 below). Drive every later command with `git -C "$WORKTREE_DIR" …` rather than
   `cd`, so the procedure can't lose track of which tree it's in.

   If the main checkout is in a state where you can't make a worktree, stop and
   report why. Don't stash the user's work.

2. **Merge the default branch in** — merge, **never rebase**. The branch is already
   pushed; rebasing it would require a force-push. **Save the PR head first**: every
   later "back it out" step needs a SHA to return to, and a detached HEAD leaves you
   no branch name to fall back on.

   Save it as a **ref**, not a shell variable — the later steps that need it run in
   their own shells, and a `PR_HEAD_SHA` that came back empty would turn
   `reset --hard "$PR_HEAD_SHA"` into a reset to `HEAD`, silently keeping the very
   merge you meant to throw away:

   ```bash
   WORKTREE_DIR="<your assigned conflicts worktree dir>"
   git -C "$WORKTREE_DIR" update-ref "refs/babysit/pr-<number>-head" HEAD
   git -C "$WORKTREE_DIR" merge "origin/<DEFAULT_BRANCH>"
   ```

   The ref name carries this PR's number so two PRs can never read each other's
   saved head. Substitute the literal number from your prompt.

3. **Resolve the conflicts.** Use the `mattpocock-skills:resolving-merge-conflicts`
   skill when it's installed; otherwise resolve them directly. Apply the confidence
   rule per conflict. If **any** conflict in the PR needs judgment, abandon the whole
   resolution rather than pushing a half-merge — and **back out on the merge's actual
   state, not on the assumption that it's still in progress.** `git merge --abort`
   only works while `MERGE_HEAD` exists; a resolution skill (or a merge that turned
   out to be clean) may already have committed, which removes `MERGE_HEAD` and makes
   `--abort` fail with *"There is no merge to abort"*:

   ```bash
   WORKTREE_DIR="<your assigned conflicts worktree dir>"
   # restore the PR head, whether or not the merge is still in progress
   if git -C "$WORKTREE_DIR" rev-parse -q --verify MERGE_HEAD >/dev/null; then
     git -C "$WORKTREE_DIR" merge --abort
   else
     git -C "$WORKTREE_DIR" reset --hard "refs/babysit/pr-<number>-head"
   fi
   git -C "$WORKTREE_DIR" clean -fd   # neither branch above removes untracked files
   ```

   **The `clean` is what makes the restore an actual restore.** Both branches rewind
   only *tracked* state, so a conflict-resolution leftover — or a file a test run
   dropped — survives and breaks the two things that come next: a redone merge dies
   with *"The following untracked working tree files would be overwritten by
   merge"*, and step 7's `git worktree remove` refuses with *"contains modified or
   untracked files"*.

   A blanket `clean` is safe here precisely because step 1 built this worktree fresh
   from a remote ref — it started with zero untracked files, so anything `clean`
   finds is something this procedure created. That reasoning holds **only** inside
   the procedure's own worktree; never run it in the user's checkout. And no `-x`:
   ignored paths (dependency dirs, `.pytest_cache`, coverage output) block neither a
   re-merge nor `worktree remove`, so deleting them only makes the next pass
   re-download them.

   Then report the PR as needing a human, naming the files and what the two sides
   disagree about. Every later step that says *abort* means this same restore —
   guarded rewind **plus** the `clean` — never a bare `merge --abort`.

4. **Verify** — run the tests covering the conflicted files, per the repo's
   `CLAUDE.md` / its `running-tests` skill. If they fail, **classify the failure
   before reacting** — a red test is not automatically proof your resolution is
   wrong. Re-run the same tests on the pre-merge tip to find out:

   ```bash
   WORKTREE_DIR="<your assigned conflicts worktree dir>"
   git -C "$WORKTREE_DIR" stash list   # expect empty; the merge is committed or in progress
   # back to the PR head, un-merged — same restore as step 3, because by now the
   # merge may well be committed and `merge --abort` would fail
   if git -C "$WORKTREE_DIR" rev-parse -q --verify MERGE_HEAD >/dev/null; then
     git -C "$WORKTREE_DIR" merge --abort
   else
     git -C "$WORKTREE_DIR" reset --hard "refs/babysit/pr-<number>-head"
   fi
   git -C "$WORKTREE_DIR" clean -fd   # test-run droppings too, not just merge leftovers
   # …re-run the same tests here, then redo the merge if you need to
   ```

   The `clean` matters most on **this** path, because it's the one that goes back to
   the merge afterwards: the tests you just ran created the untracked files, and
   redoing the merge with them still in place fails on paths the merge wants to
   write.

   **"Redo the merge", as the bullets below use it, is not a single command** — the
   restore threw your resolution away along with the merge. The same paths come back
   conflicted, identically, and nothing is committable until you re-apply the same
   resolution you already decided on:

   ```bash
   WORKTREE_DIR="<your assigned conflicts worktree dir>"
   git -C "$WORKTREE_DIR" merge "origin/<DEFAULT_BRANCH>"   # conflicts again, the same ones
   # …re-apply the same resolution, then commit it:
   git -C "$WORKTREE_DIR" commit --no-edit
   ```

   Skipping it is the one mistake this procedure can't feel: a restored PR head is
   exactly what the remote already has, so pushing it succeeds as a
   **no-op** and the pass reports a conflict "fixed" having changed nothing. Step 5
   below asserts against that rather than trusting this step to have happened.

   - **Fails the same way without the merge** → pre-existing on the PR head, or an
     infrastructure failure (no network, no test DB, missing credentials); either way
     the resolution isn't implicated. Redo the merge, push it, and report the red tests
     separately as pre-existing/infra so nobody reads the ✅ as "tests green".
   - **Only fails with the merge applied** → **two** causes fit and the rerun above
     can't separate them: your resolution, or commits the default branch brought in.
     Measure the incoming side before blaming yourself — check out the merge's other
     parent, re-run there, then come back to the PR head:

     ```bash
     WORKTREE_DIR="<your assigned conflicts worktree dir>"
     git -C "$WORKTREE_DIR" clean -fd   # the rerun's droppings, before switching trees
     git -C "$WORKTREE_DIR" checkout --detach "origin/<DEFAULT_BRANCH>"
     # …re-run the same tests here…
     git -C "$WORKTREE_DIR" clean -fd
     git -C "$WORKTREE_DIR" checkout --detach "refs/babysit/pr-<number>-head"
     ```

     **Do not push from inside this detour.** Between the two checkouts your `HEAD`
     *is* the default branch — pushing there would overwrite the PR's branch with
     the default branch's contents and drop every commit the PR was made of. Step 5's
     first guard exists to catch exactly this; come back to the PR head before you
     go near it.

     Red on the default branch too → it's already broken; treat it like the first
     bullet (redo the merge, push, report the failure as inherited, not yours). Green
     there → the resolution really is wrong: restore and report, naming the failing
     tests. A baseline you **can't** run — no network, a tree the default branch can't
     even build — leaves the cause **indeterminate**: restore and report it as that,
     never as a bad resolution you didn't demonstrate.
   - **Can't tell** → restore and report. That's the confidence rule; don't push a
     merge you couldn't verify.

5. **Commit and push.** Because the worktree is on a detached HEAD, a bare
   `git push` **fails** — push the explicit, quoted refspec
   `origin "HEAD:<headRefName>"` instead. Never `--force`.

   ```bash
   WORKTREE_DIR="<your assigned conflicts worktree dir>"
   if git -C "$WORKTREE_DIR" rev-parse -q --verify MERGE_HEAD >/dev/null; then
     git -C "$WORKTREE_DIR" commit --no-edit   # the merge is still in progress
   fi
   SAVED_SHA=$(git -C "$WORKTREE_DIR" rev-parse -q --verify "refs/babysit/pr-<number>-head^{commit}") || SAVED_SHA=""
   # Assert you're pushing the resolved merge: both sides of it have to be in HEAD.
   if [ -z "$SAVED_SHA" ]; then
     echo "STOP: step 2's saved-head ref is gone — nothing proves what this push would replace. Do not push."
   elif ! git -C "$WORKTREE_DIR" merge-base --is-ancestor "$SAVED_SHA" HEAD; then
     echo "STOP: the PR head is not in HEAD — you are on a baseline checkout, not the merge. Do not push."
   elif ! git -C "$WORKTREE_DIR" merge-base --is-ancestor "origin/<DEFAULT_BRANCH>" HEAD; then
     echo "STOP: the default branch is not in HEAD — the merge was never redone. Redo it or report; do not push."
   elif git -C "$WORKTREE_DIR" grep -nI -e '^<<<<<<< ' -e '^>>>>>>> ' HEAD; then
     echo "STOP: committed conflict markers — fix the resolution before pushing."
   else
     git -C "$WORKTREE_DIR" push --force-with-lease="<headRefName>:$SAVED_SHA" origin "HEAD:<headRefName>"
   fi
   ```

   The commit is **gated on `MERGE_HEAD`** because by step 5 the merge may already be
   committed — a clean re-merge auto-commits, and a resolution skill may have
   committed for you. With no merge in progress, `git commit --no-edit` exits
   non-zero, and a fail-fast shell would die right there — *before* the guards and
   the push — turning a finished resolution into a silent no-push.

   The push carries `--force-with-lease="<headRefName>:$SAVED_SHA"` — a
   compare-and-swap, not a force. The remote accepts the push only if the branch tip
   is still exactly the head this pass started from (step 2's saved ref). Anything
   that landed on the branch mid-pass rejects it — including a force-push to an
   *ancestor*, which a plain push would silently bury by reinstating the commits
   someone just deliberately removed. Because the first guard already proved
   `$SAVED_SHA` is an ancestor of `HEAD`, a push the lease lets through is an
   ordinary fast-forward: pinned to an explicit SHA, the lease can only **refuse**
   pushes a plain push would have accepted, never rewrite history, so it doesn't
   breach the never-force rail. Bare `--force`, and bare `--force-with-lease`
   without an expected value (it trusts whatever your remote-tracking ref says),
   stay forbidden. A lease rejection means the branch moved under you mid-pass:
   treat it as a failed guard — restore, clean up, report; don't refetch and retry.

   `SAVED_SHA` is read **once**, verified, and that one value feeds both the
   ancestry guard and the lease — so the commit the guard validated is the commit
   the lease pins. The emptiness check ahead of the guards matters twice over: an
   unresolvable ref would error the ancestry check, and an *empty* lease value
   flips its meaning to "expect the branch to be absent".

   The three substantive checks cover the same failure mode from three sides. **Both** ancestry
   checks are needed, and neither substitutes for the other: the default-branch one
   catches a merge that never happened, but on its own it *passes* on step 4's
   baseline detour — where `HEAD` is the default branch, making it trivially its own
   ancestor — and would push the default branch over the PR's head branch, discarding
   the PR. The PR-head check is what rejects that. The `grep` then catches a merge
   that was "resolved" by committing the markers. None of this is hypothetical once
   step 4 has rewound or switched the tree — and a push is the one action in this
   procedure that a later pass can't quietly undo.

   The refspec is **quoted** (`"HEAD:<headRefName>"`) because git accepts branch names
   containing shell metacharacters — `;`, `$(…)`, backticks are all legal in a ref name
   (only spaces, `~^:?*[\` and a few patterns are not). Unquoted, a branch named
   `feature;rm-something` would end the `git push` command and run the rest as a
   second command. Quote it here and everywhere else you name a branch.

   **The `if`/`elif`/`else` is load-bearing** — the checks have to *gate* the push, not
   just print next to it. Written as two bare commands that only `echo`, the `git push`
   on the following line runs regardless, so the procedure pushes the very head the
   check just declared unpushable. A failed guard ends this axis: record it for your
   RESULT, run the step 3 restore, clean up the worktree (step 7), and report — don't
   push, and don't abandon the cleanup.

6. **Confirm** it took. GitHub recomputes mergeability asynchronously, so poll rather
   than checking once — but **bound the poll**, or one stuck PR eats the pass budget:

   ```bash
   MERGEABLE=UNKNOWN
   for _ in $(seq 12); do   # 12 × 5s ≈ 1 minute, then give up
     MERGEABLE=$(gh pr view <pr_number> --json mergeable --jq .mergeable)
     [ "$MERGEABLE" != "UNKNOWN" ] && break
     sleep 5
   done
   echo "$MERGEABLE"   # expect MERGEABLE
   ```

   Still `UNKNOWN` when the budget runs out → report the push as done but the
   mergeability as *undetermined*, and move on. Never keep polling.

7. **Clean up** the worktree you created (leave repo-skill-managed worktrees to that
   skill's own convention):

   ```bash
   WORKTREE_DIR="<your assigned conflicts worktree dir>"
   git -C "$WORKTREE_DIR" clean -fd   # the success path never ran a restore
   git -C "$WORKTREE_DIR" update-ref -d "refs/babysit/pr-<number>-head"   # step 2's saved head
   git worktree remove "$WORKTREE_DIR"
   ```

   Delete the saved-head ref on **every** exit from this axis, including the failure
   paths — it lives in the shared ref store, not in the worktree, so removing the
   worktree does not take it with it.

   The `clean` is here for the path where **nothing went wrong**: a merge that
   resolved cleanly, passed its tests and pushed never hits a restore step, so the
   artifacts the test run left behind are still sitting there — and `git worktree
   remove` refuses on untracked files exactly as it does on modified ones.

   With that out of the way, a refusal means what it should: *tracked* state you
   didn't finish dealing with. Investigate and report it; don't reach for `--force`
   to make the error go away.

**Next axis:** if your prompt also flagged failing checks, continue with
[`ci-procedure.md`](ci-procedure.md) — and read its step 1 first, because the push
you just made makes your CI triage evidence stale.
