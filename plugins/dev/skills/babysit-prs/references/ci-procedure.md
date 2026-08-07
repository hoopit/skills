# CI procedure

One axis of a **babysit-prs** per-PR pass: this PR has at least one check in the
`fail` bucket. Read this file only when your prompt flagged the failing-checks axis.

Read the worker briefing in [`worker-briefing.md`](worker-briefing.md) first — its
confidence rule, safety rails, and worktree hygiene govern every step here, and
nothing below repeats them.

Every `<...>` below is a value from your worker prompt. `WORKTREE_DIR` means the
literal absolute **CI** worktree dir it assigned
(`<REPO_ROOT>/.worktrees/babysit-ci-<number>`). The step numbers here are this
procedure's own; they are not the orchestrator's Steps 1–5.

**Each command block runs in a fresh shell.** Your tool calls do not share an
environment, so a variable assigned in one block is *empty* in the next — and an
empty `WORKTREE_DIR` turns `git -C "$WORKTREE_DIR" clean -fd` into a `clean` of
whatever directory you happen to be in. Every block below therefore re-assigns
`WORKTREE_DIR` (and `REPO_ROOT`, where the block needs it) on its first lines;
keep those lines when you run the block, with the literal paths substituted.

1. **Identify the failing checks.** Your prompt carries the fail-bucket JSON the
   orchestrator gathered at triage, with each check's `name` and `link`.

   **If the conflict procedure pushed for this PR, that triage evidence is stale** —
   it describes the pre-merge commit. Re-run the query before you act on it, or
   you'll spend a fix on a failure the merge already resolved (or miss one it
   introduced):

   ```bash
   gh pr checks <pr_number> -R <owner_repo> --json name,bucket,state,link \
     --jq '[.[] | select(.bucket == "fail")]'
   ```

   > `gh pr checks` exits **8** while checks are still pending, and non-zero when
   > checks are failing — that's its normal reporting channel, not a command error.
   > Read its output; don't abort on the exit code, and don't put it in an `&&`
   > chain.

   A fresh push re-queues CI, so the honest answer here is usually `pending`, not a
   new list of failures. Don't wait it out. Report the PR as *conflicts fixed, CI
   re-running* and let the next pass pick up the checks. Only remediate failures you
   observed on the **current** head, with no push in between.

2. **Get the failure detail**, routing on the `link` host:
   - **CircleCI** (`circleci.com` / `app.circleci.com`) → invoke the
     **`circleci-tests`** skill. It needs a **job** URL ending in
     `/jobs/<jobNumber>/tests`, but the check link is usually a *workflow* or *build*
     link (`app.circleci.com/workflow/<id>`, or the older
     `circleci.com/gh/<org>/<repo>/<build>`). Open the link and drill down to the
     failing job first, then hand that job URL to the skill.
   - **GitHub Actions** (`github.com/.../actions/runs/<run_id>/...`) → take the
     `<run_id>` from the link: `gh run view <run_id> -R <owner_repo> --log-failed`.
   - **Anything else** (security scanners, review bots, custom status contexts) →
     read what the `link` gives you. An empty `link` (common for `StatusContext`
     checks posted by bots) means there's nothing to fetch — report the check as
     failing-and-opaque.

3. **Decide with the confidence rule.** A clear cause — a test asserting on something
   you renamed, a lint/format failure, a missing import, a snapshot that needs
   updating — gets fixed. Anything else (genuine logic failure, suspected flake,
   infra/credentials error) is reported, not guessed at. For a suspected flake, say so
   and note the check name — don't re-run it blindly on every pass.

4. **Fix it in its own worktree.** Don't assume one already exists: a PR with no
   conflicts never had one, and the conflict procedure
   ([`conflict-procedure.md`](conflict-procedure.md)) removes the worktree it made in
   its own step 7 before this procedure runs. Make a fresh one from the current PR
   head — if the conflict procedure just pushed, fetch again rather than reusing a
   stale ref:

   ```bash
   REPO_ROOT="<your repo root>"
   WORKTREE_DIR="<your assigned CI worktree dir>"   # <REPO_ROOT>/.worktrees/babysit-ci-<number>
   HEAD_BRANCH=$(gh pr view <pr_number> -R <owner_repo> --json headRefName --jq .headRefName)
   git -C "$REPO_ROOT" fetch origin
   git -C "$REPO_ROOT" worktree add "$WORKTREE_DIR" "origin/$HEAD_BRANCH"
   ```

   `HEAD_BRANCH` is resolved from `gh` at execution time, never pasted from your
   prompt — step 5 explains why. Re-resolve it in every block that names the
   branch; blocks don't share shells.

   Same rules as the conflict procedure: follow the repo's own worktree skill if it
   has one, detached HEAD so no local branch can collide, `git -C "$WORKTREE_DIR" …`
   for every command inside the worktree (lifecycle commands scope to
   `git -C "$REPO_ROOT"` per the briefing), never touch the user's checkout,
   stop-and-report if you can't get a clean worktree.

5. **Verify, push, clean up.** Run the failing check's tests locally in the worktree
   and only push once they pass — a blind push spends another CI cycle to learn what
   you could have learned locally:

   ```bash
   set -euo pipefail   # a failed commit or push must stop the block *before* the cleanup lines
   REPO_ROOT="<your repo root>"
   WORKTREE_DIR="<your assigned CI worktree dir>"
   HEAD_BRANCH=$(gh pr view <pr_number> -R <owner_repo> --json headRefName --jq .headRefName)
   git -C "$WORKTREE_DIR" add -A   # not `commit -am`: that skips files the fix added
   git -C "$WORKTREE_DIR" commit -m "fix: <what you fixed>"
   git -C "$WORKTREE_DIR" show --stat HEAD   # every file you touched, or you pushed a half-fix
   git -C "$WORKTREE_DIR" push origin "HEAD:$HEAD_BRANCH"
   git -C "$WORKTREE_DIR" clean -fd   # test artifacts, or `worktree remove` refuses
   git -C "$REPO_ROOT" worktree remove "$WORKTREE_DIR"
   ```

   The `set -euo pipefail` is load-bearing: without it a failed `commit` or `push`
   falls straight through to the `clean`/`worktree remove` lines, which delete the
   fix you just made — and the report then claims a push that never happened. If
   this block exits non-zero partway, the worktree is left intact on purpose:
   report the failure (with the command's output), and match the report to where
   the block stopped. A failure at or before the `push` line means the remote
   never got the change — don't report it as pushed. A failure *after* the push
   (`clean` or `worktree remove`) means the fix is already on the remote — report
   the push as done and the cleanup failure separately, so the orchestrator knows
   there's a leftover worktree, not a missing fix. This fail-fast applies to
   *this* block; the `gh pr checks` query in step 1 keeps its own
   expected-non-zero handling.

   The branch name is **resolved at execution time** rather than pasted into the
   command, because pasting is unsafe *even quoted*: git accepts branch names
   containing `;`, `$(…)`, backticks and quotes, and inside double quotes the
   shell still evaluates command substitutions — a literal `"HEAD:feature$(…)"`
   in shell source runs whatever the name embeds. Expanded from `$HEAD_BRANCH`
   inside a quoted argument, it's data the shell never re-parses.

   `add -A` before the commit is what makes a fix that *creates* a file (a missing
   migration, a new snapshot or fixture) land: `-am` stages only tracked paths, so the
   push would carry an incomplete fix, CI would fail the same way, and the `clean` two
   lines later would delete the missing piece — leaving nothing to explain the miss.
   Check `show --stat` against what you actually edited before pushing. If `add -A`
   sweeps in a stray artifact, delete that file rather than falling back to `-am`.

   If the local run still fails, you misread the cause — don't push. Drop the fix and
   report the check. Note that `checkout .` only covers **tracked** files, so a fix
   that added a file needs the `clean` to disappear — and without it
   `git worktree remove` refuses and leaves the worktree behind:

   ```bash
   REPO_ROOT="<your repo root>"
   WORKTREE_DIR="<your assigned CI worktree dir>"
   git -C "$WORKTREE_DIR" checkout .   # revert edits to tracked files
   git -C "$WORKTREE_DIR" clean -fd    # …and remove any file the fix added
   git -C "$REPO_ROOT" worktree remove "$WORKTREE_DIR"
   ```

   Report the re-run as *pushed, CI pending*; don't wait for the new run to finish.
