---
name: babysit-prs
description: Babysit your open PRs — sweep for merge conflicts, failing checks, and unresolved review comments; fix what's safe, report the rest. Designed for one pass per invocation, e.g. `/loop 15m /babysit-prs`.
---

# Babysit open PRs

Your open PRs rot while you work on something else: the default branch moves and they
conflict, a flaky-looking check goes red, a reviewer leaves a thread you never saw.
This skill does **one sweep** over your open PRs, fixes what is safe to fix, and
reports everything else for a human.

**One invocation = one pass.** Do not loop inside the skill — finish the pass and
report. Scheduling repeats is the caller's job (`/loop 15m /babysit-prs`).

## Prerequisites

- The `gh` CLI must be authenticated (`gh auth status`).
- Run from the project repository (or a worktree of it).

## Step 1 — Resolve repo context

Never hardcode the repo or its default branch — read them from the checkout:

```bash
gh repo view --json nameWithOwner,defaultBranchRef \
  --jq '"OWNER_REPO=\(.nameWithOwner)\nDEFAULT_BRANCH=\(.defaultBranchRef.name)"'
```

Use `OWNER_REPO` (as `<owner>/<repo>`) and `DEFAULT_BRANCH` throughout. For anything
else project-specific — the test command, worktree setup, CI provider — consult the
current repo's `CLAUDE.md` (see its *Workflow skills config* section if it has one).

## Step 2 — Sweep the open PRs

```bash
gh pr list --author "@me" --state open --limit 100 \
  --json number,title,headRefName,isCrossRepository,isDraft,mergeable,mergeStateStatus,url
```

`--limit` is required: `gh pr list` defaults to **30** and silently truncates at
whatever limit you give it. If the result count comes back *equal* to the limit,
you can't tell a full sweep from a truncated one — raise the limit and re-run.

- **`mergeable: "UNKNOWN"`** means GitHub is still computing the merge — it is *not*
  a conflict. Set that PR aside, handle the others first, then re-check it once at
  the end of the pass:

  ```bash
  gh pr view <pr_number> --json mergeable,mergeStateStatus
  ```

  - Still `UNKNOWN` → report it as *undetermined* and move on; the next pass will
    pick it up. Don't block the pass waiting on it.
  - Now `CONFLICTING` or `MERGEABLE` → it's a normal PR again. Run the **full Step 3
    triage** on it (all three axes), or, if you're out of pass budget, report it
    explicitly as *deferred to the next pass* — never as handled.
- **`isCrossRepository: true`** (the head branch lives in a fork) → report it and
  move on. Every fix here fetches and pushes `origin`, which is the *base* repo:
  `origin/<headRefName>` either doesn't exist or points at an unrelated branch of
  the same name, and the push would target a repo the PR author may not own.
  Fork-backed PRs are out of scope for this skill.
- Draft PRs still get conflicts fixed, but don't chase their CI — note them as draft.
- No open PRs → say so and end the pass.

## Step 3 — Triage each PR

For each PR, check all three axes (a PR can need more than one):

| Signal | Condition | Go to |
|---|---|---|
| Merge conflict | `mergeable == "CONFLICTING"` (or `mergeStateStatus == "DIRTY"`) | [Conflict procedure](#conflict-procedure) |
| Failing checks | any check with `bucket == "fail"` | [CI procedure](#ci-procedure) |
| Unresolved review comments | any review thread with `isResolved: false` | invoke the **`review-github-comments`** skill with the PR URL |

Detect failing checks with `gh pr checks` rather than reading `statusCheckRollup`
yourself — the rollup mixes two node shapes (`CheckRun` carries `name`/`conclusion`,
`StatusContext` carries `context`/`state`, each with the other's fields null), while
`gh pr checks` normalises both into `name`/`state`/`link` plus a `bucket` field
(`pass`/`fail`/`pending`/`skipping`/`cancel`):

```bash
gh pr checks <pr_number> --json name,bucket,state,link \
  --jq '[.[] | select(.bucket == "fail")]'
```

> `gh pr checks` exits **8** while checks are still pending, and non-zero when checks
> are failing — that's its normal reporting channel, not a command error. Read its
> output; don't abort the pass on the exit code, and don't put it in an `&&` chain.

Checks still `pending` are not a failure — leave that PR for the next pass.

Detect unresolved threads with the same GraphQL query `review-github-comments` uses:

```bash
gh api graphql --paginate \
  -f query='
query($owner: String!, $repo: String!, $pr: Int!, $endCursor: String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      reviewThreads(first: 100, after: $endCursor) {
        pageInfo { hasNextPage endCursor }
        nodes { isResolved }
      }
    }
  }
}' -F owner=<owner> -F repo=<repo> -F pr=<pr_number> \
  --jq '[.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved == false)] | length'
```

`reviewThreads` is paginated, so a bare `first: 50` can miss unresolved threads on a
busy PR — every unresolved one could sit past the first page. `--paginate` needs the
`$endCursor` variable and the `pageInfo` block to walk the pages; it then emits one
result per page, so sum the counts rather than reading only the first line.

Order matters: **resolve conflicts first**, then CI, then review comments — a
conflicted branch can't be meaningfully tested, and the comment pass pushes its own
commits on top.

### The confidence rule

Applies to every fix in this skill:

- **Fix it** when the change is mechanical and the correct result is unambiguous —
  non-overlapping edits in the same file, both sides adding imports/exports, a
  regenerated lockfile, an obviously-stale reference to something you renamed.
- **Leave it and report it** when judgment is needed — both sides changed the same
  logic with different intent, a failing test whose cause you can't pin down, a
  check failing for infrastructure reasons. Flagging is a success, not a failure.

When in doubt, report. An unattended pass must never guess at semantics.

### Conflict procedure

1. **Check the branch out in isolation** — never disturb the user's working tree. If
   the repo defines its own worktree skill (e.g.
   `.claude/skills/create-worktree/SKILL.md`), read and follow it — it owns venv /
   test-DB / direnv / toolchain setup. Otherwise:

   ```bash
   git fetch origin
   WORKTREE_DIR=".worktrees/babysit-<pr_number>"
   git worktree add "$WORKTREE_DIR" "origin/<headRefName>"
   ```

   This lands on a **detached HEAD** at the remote tip — deliberately, so it can't
   collide with a stale local branch of the same name. It changes how you push (step
   5). Drive every later command with `git -C "$WORKTREE_DIR" …` rather than `cd`, so
   the pass can't lose track of which tree it's in.

   If the working tree is dirty and you can't make a worktree, skip the PR and
   report why. Don't stash the user's work.

2. **Merge the default branch in** — merge, **never rebase**. The branch is already
   pushed; rebasing it would require a force-push.

   ```bash
   git -C "$WORKTREE_DIR" merge "origin/$DEFAULT_BRANCH"
   ```

3. **Resolve the conflicts.** Use the `mattpocock-skills:resolving-merge-conflicts`
   skill when it's installed; otherwise resolve them directly. Apply the confidence
   rule per conflict. If **any** conflict in the PR needs judgment, abandon the whole
   resolution rather than pushing a half-merge:

   ```bash
   git -C "$WORKTREE_DIR" merge --abort
   ```

   and report the PR as needing a human, naming the files and what the two sides
   disagree about.

4. **Verify** — run the tests covering the conflicted files, per the repo's
   `CLAUDE.md` / its `running-tests` skill. If they fail, **classify the failure
   before reacting** — a red test is not automatically proof your resolution is
   wrong. Re-run the same tests on the pre-merge tip to find out:

   ```bash
   git -C "$WORKTREE_DIR" stash list   # expect empty; the merge is committed or in progress
   git -C "$WORKTREE_DIR" merge --abort    # back to the PR head, un-merged
   # …re-run the same tests here, then redo the merge if you need to
   ```

   - **Fails the same way without the merge** (pre-existing on the PR head or on
     `origin/$DEFAULT_BRANCH`), or fails for infrastructure reasons (no network, no
     test DB, missing credentials) → the resolution isn't implicated. Redo the merge,
     push it, and report the red tests separately as pre-existing/infra so nobody
     reads the ✅ as "tests green".
   - **Only fails with the merge applied** → the resolution is wrong:
     `git -C "$WORKTREE_DIR" merge --abort` and report, naming the failing tests.
   - **Can't tell** → abort and report. That's the confidence rule; don't push a
     merge you couldn't verify.

5. **Commit and push.** Because the worktree is on a detached HEAD, a bare
   `git push` **fails** (`git push origin HEAD:<name-of-remote-branch>`) — push the
   explicit refspec instead. Never `--force`.

   ```bash
   git -C "$WORKTREE_DIR" commit --no-edit   # if the merge didn't auto-commit
   git -C "$WORKTREE_DIR" push origin HEAD:<headRefName>
   ```

6. **Confirm** it took. GitHub recomputes mergeability asynchronously, so poll rather
   than checking once — but **bound the poll**, or one stuck PR hangs the whole pass:

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
   mergeability as *undetermined*, and move to the next PR. Never keep polling.

7. **Clean up** the worktree you created (leave repo-skill-managed worktrees to that
   skill's own convention):

   ```bash
   git worktree remove "$WORKTREE_DIR"
   ```

   This refuses if the tree still has changes — which means something didn't finish.
   Investigate and report it; don't reach for `--force` to make the error go away.

### CI procedure

1. **Identify the failing checks** with the `bucket == "fail"` query from Step 3,
   keeping each one's `name` and `link`.

2. **Get the failure detail**, routing on the `link` host:
   - **CircleCI** (`circleci.com` / `app.circleci.com`) → invoke the
     **`circleci-tests`** skill. It needs a **job** URL ending in
     `/jobs/<jobNumber>/tests`, but the check link is usually a *workflow* or *build*
     link (`app.circleci.com/workflow/<id>`, or the older
     `circleci.com/gh/<org>/<repo>/<build>`). Open the link and drill down to the
     failing job first, then hand that job URL to the skill.
   - **GitHub Actions** (`github.com/.../actions/runs/<run_id>/...`) → take the
     `<run_id>` from the link: `gh run view <run_id> --log-failed`.
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
   conflicts never had one, and the conflict procedure removes the worktree it made
   (step 7) before this procedure runs. Make a fresh one from the current PR head —
   the conflict procedure just pushed to it, so fetch again rather than reusing a
   stale ref:

   ```bash
   git fetch origin
   WORKTREE_DIR=".worktrees/babysit-ci-<pr_number>"
   git worktree add "$WORKTREE_DIR" "origin/<headRefName>"
   ```

   Same rules as the conflict procedure: follow the repo's own worktree skill if it
   has one, detached HEAD so no local branch can collide, `git -C "$WORKTREE_DIR" …`
   for every command, never touch the user's checkout, skip-and-report if you can't
   get a clean worktree.

5. **Verify, push, clean up.** Run the failing check's tests locally in the worktree
   and only push once they pass — a blind push spends another CI cycle to learn what
   you could have learned locally:

   ```bash
   git -C "$WORKTREE_DIR" commit -am "fix: <what you fixed>"
   git -C "$WORKTREE_DIR" push origin HEAD:<headRefName>
   git worktree remove "$WORKTREE_DIR"
   ```

   If the local run still fails, you misread the cause — don't push. Drop the fix
   (`git -C "$WORKTREE_DIR" checkout .`), remove the worktree, and report the check.
   Report the re-run as *pushed, CI pending*; don't wait for the new run to finish.

## Step 4 — Report

One line per PR: what you found, what you did, what a human still needs to do.

```text
#412 Fix payment webhook retries — CONFLICTING → merged default branch, 3 mechanical conflicts resolved, tests pass, pushed ✅
#418 Add coach dashboard filters — CI failing (circleci: 2 tests) → fixed stale assertion, pushed ✅
#421 Refactor booking serializer — CONFLICTING → ⚠️ needs a human: both sides rewrote `BookingSerializer.validate`
#425 Bump deps — 2 unresolved review threads → ran review-github-comments, 1 left open for discussion
#430 Spike: new calendar — draft, mergeable UNKNOWN → undetermined, will recheck next pass
```

Finish with a one-line count (e.g. `5 PRs: 2 fixed, 1 needs a human, 1 partially
handled, 1 undetermined`). Then **end the pass** — don't start another sweep.

## Safety

- **Never push to the default branch.** Every push in this skill targets a PR's own
  head branch.
- **Never force-push and never rebase** a branch that's already on the remote — a
  reviewer's in-progress comments and the PR's review history depend on its history
  staying put.
- **Never resolve a conflict by taking one side wholesale** (`--ours` / `--theirs`
  over a whole file) unless the file is a generated artifact you then regenerate.
- **Never resolve a review thread you didn't act on** — that's
  `review-github-comments`' rule, and it holds here.
- **Don't touch PRs you don't own.** The sweep is `--author "@me"` on purpose.
- **Don't merge PRs.** Babysitting keeps them healthy and mergeable; a human decides
  when they land.
