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

The pass runs as a thin **orchestrator**: it sweeps and triages every PR with cheap
`gh` JSON calls, then hands each PR that actually needs work to its **own worker
subagent**, which does all the log-reading and git surgery in its own context and
returns a one-line verdict. Healthy PRs never spawn a worker. This keeps per-PR state
(worktree paths, head SHAs, refnames) unmixable by construction and keeps CI logs and
diffs out of the orchestrating context.

## Prerequisites

- The `gh` CLI must be authenticated (`gh auth status`).
- Run from the project repository (or a worktree of it).

## Step 1 — Resolve repo context

Never hardcode the repo or its default branch — read them from the checkout:

```bash
gh repo view --json nameWithOwner,defaultBranchRef \
  --jq '"OWNER_REPO=\(.nameWithOwner)\nDEFAULT_BRANCH=\(.defaultBranchRef.name)"'
git rev-parse --show-toplevel   # REPO_ROOT — absolute; worker prompts need it
```

Use `OWNER_REPO` (as `<owner>/<repo>`) and `DEFAULT_BRANCH` throughout. For anything
else project-specific — the test command, worktree setup, CI provider — consult the
current repo's `CLAUDE.md` (see its *Workflow skills config* section if it has one).

Workers don't inherit this skill's text, so resolve the path they'll read it from:

```bash
SKILL_FILE=$(find ~/.claude/plugins -path '*babysit-prs/SKILL.md' 2>/dev/null | head -1)
# Fallback when the skill runs from a source checkout rather than an installed plugin:
[ -n "$SKILL_FILE" ] || SKILL_FILE="$(git rev-parse --show-toplevel)/$(git ls-files '*babysit-prs/SKILL.md' | head -1)"
```

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
    triage** on it (and dispatch a worker if it's flagged), or, if you're out of pass
    budget, report it explicitly as *deferred to the next pass* — never as handled.

  This recheck is one cheap `gh pr view`, and it stays orchestrator-side — never
  spawn a worker "just to look" at an `UNKNOWN` PR.
- **`isCrossRepository: true`** (the head branch lives in a fork) → report it and
  move on. Every fix here fetches and pushes `origin`, which is the *base* repo:
  `origin/<headRefName>` either doesn't exist or points at an unrelated branch of
  the same name, and the push would target a repo the PR author may not own.
  Fork-backed PRs are out of scope for this skill.
- Draft PRs still get conflicts fixed, but don't chase their CI — note them as draft.
- No open PRs → say so and end the pass.

## Step 3 — Triage each PR

For each PR, check all three axes with cheap `gh` JSON calls — a PR can be flagged
on more than one:

| Axis | Flag it when |
|---|---|
| Merge conflict | `mergeable == "CONFLICTING"` (or `mergeStateStatus == "DIRTY"`) |
| Failing checks | any check with `bucket == "fail"` — but not on drafts (note those as draft instead) |
| Unresolved review comments | any review thread with `isResolved: false` |

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
  --jq '[.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved == false)] | length' \
  | awk '{ total += $1 } END { print total + 0 }'
```

`reviewThreads` is paginated, so a bare `first: 50` can miss unresolved threads on a
busy PR — every unresolved one could sit past the first page. `--paginate` needs the
`$endCursor` variable and the `pageInfo` block to walk the pages. `--jq` then runs
**once per page** and prints one count per page, so the `awk` sum is what turns that
into a single total — without it, reading the first line alone undercounts.

**Zero flagged axes → the PR is healthy.** Write its one report line (`healthy ✅`,
or *checks pending, next pass* / *draft* as applicable) and move on — **no worker**.
On a good day the whole pass is a handful of `gh` calls and zero subagents.

**One or more flagged axes → Step 4.** Keep the evidence you just gathered (the
failing-checks JSON, the unresolved-thread count) — it goes into the worker prompt
so the worker doesn't re-triage from scratch.

## Step 4 — Dispatch one worker per flagged PR

Spawn one **`general-purpose` subagent per flagged PR**, and spawn them **one at a
time, in PR order** — workers share the repo's single `.git`, and concurrent
`worktree add`/`fetch` contend on its locks. Wait for each worker's RESULT before
starting the next.

This holds even when only **one** PR is flagged. Workers are sequential, so there is
no parallel fan-out whose overhead needs amortising — a worker costs one spawn plus
re-reading this file in its own context, and buys the thing this design exists for:
the CI logs, diffs, and merge churn land in the worker's context, not the
orchestrator's. Under `/loop` the orchestrator's session accumulates pass after pass,
so that hygiene pays at any count. The inline path below is a capability fallback
(no Agent tool), not a count threshold.

Fill the prompt template below with **literal values only — never `$VAR`**. The
worker runs in its own context with its own shell: your variables don't exist there,
and an unexpanded `$DEFAULT_BRANCH` in the prompt becomes an empty string in the
worker's commands. Replace every `<...>` placeholder with the actual value — except
inside the final `RESULT`/`DETAIL` block, whose placeholders the worker fills.

```text
You are babysitting exactly one pull request as part of a babysit-prs pass.

First read <SKILL_FILE — literal absolute path> and follow its "Per-PR procedures"
and "Safety" sections exactly. The orchestrator steps (1–5) are not your job — do
not sweep or touch any other PR.

Repo: <OWNER_REPO>              Default branch: <DEFAULT_BRANCH>
Repo root: <absolute REPO_ROOT>
PR: #<number> — <title>
URL: <url>
Head branch: <headRefName>      Draft: <true|false>
Worktree dir (conflicts): <REPO_ROOT>/.worktrees/babysit-<number>
Worktree dir (CI): <REPO_ROOT>/.worktrees/babysit-ci-<number>

Flagged axes — handle only these, in this order (conflicts → CI → comments):
- Merge conflict: <yes (mergeable=…, mergeStateStatus=…) | no>
- Failing checks: <the fail-bucket JSON from triage | none>
- Unresolved review threads: <count | 0>

Safety rails — non-negotiable, restated from the skill's Safety section:
- Never push to the default branch. Every push is
  `git push origin HEAD:<headRefName>` — that head branch, nothing else.
- Never force-push and never rebase.
- Only ever `git clean` inside the two worktree dirs named above, always via
  `git -C "<worktree dir>"`, never with `-x`, never in the main checkout.
- Confidence rule: fix only what is mechanical and unambiguous. Anything needing
  judgment → restore, report, move on. When in doubt, report.
- Remove every worktree you created before finishing, even when you failed.

Return ONLY this block — no logs, no diffs, no extra prose:

RESULT #<number>: <FIXED|NEEDS-HUMAN|PARTIAL|DEFERRED|FAILED> — <one line: found → did → remaining>
DETAIL: <≤2 lines, only for NEEDS-HUMAN or FAILED>
```

Take each worker's `RESULT` line into the Step 5 report as that PR's line. A worker
that errors out, stalls, or returns anything other than a `RESULT` block is reported
as `FAILED` for its PR — never silently dropped. Its leftover worktree, if any, is at
the two dirs named in its prompt; remove them if the worker didn't.

**No Agent/Task tool available?** Process each flagged PR inline yourself instead:
sequentially, following the same *Per-PR procedures* below and the same report
contract, and fully finishing one PR — including worktree removal — before starting
the next.

## Step 5 — Report

One line per PR: what you found, what you did, what a human still needs to do.
Healthy PRs get their line from Step 3; flagged PRs get theirs from the worker's
`RESULT`.

```text
#412 Fix payment webhook retries — CONFLICTING → merged default branch, 3 mechanical conflicts resolved, tests pass, pushed ✅
#418 Add coach dashboard filters — CI failing (circleci: 2 tests) → fixed stale assertion, pushed ✅
#421 Refactor booking serializer — CONFLICTING → ⚠️ needs a human: both sides rewrote `BookingSerializer.validate`
#425 Bump deps — 2 unresolved review threads → ran review-github-comments, 1 left open for discussion
#430 Spike: new calendar — draft, mergeable UNKNOWN → undetermined, will recheck next pass
#433 Tighten rate limits — CONFLICTING + CI failing → conflicts fixed and pushed, CI re-running on the new head, checks deferred to next pass
```

Finish with a one-line count (e.g. `5 PRs: 2 fixed, 1 needs a human, 1 partially
handled, 1 undetermined`). Then **end the pass** — don't start another sweep.

---

# Per-PR procedures

Everything below is the **worker side**: it handles exactly one PR, using only the
values from its prompt plus what it reads here. When the pass runs inline (no Agent
tool), the orchestrator follows these same procedures itself, one PR at a time.

Work the flagged axes **in order: conflicts → CI → review comments** — a conflicted
branch can't be meaningfully tested, and the comment pass pushes its own commits on
top. Skip axes your prompt didn't flag. `WORKTREE_DIR` below always means the
literal absolute dir assigned in your prompt — and shell variables don't survive
between your tool calls, so re-set it (or restate the literal path) in every command
block.

- Merge conflict flagged → [Conflict procedure](#conflict-procedure)
- Failing checks flagged → [CI procedure](#ci-procedure)
- Unresolved review threads flagged → invoke the **`review-github-comments`** skill
  with the PR URL

## The confidence rule

Applies to every fix in this skill:

- **Fix it** when the change is mechanical and the correct result is unambiguous —
  non-overlapping edits in the same file, both sides adding imports/exports, a
  regenerated lockfile, an obviously-stale reference to something you renamed.
- **Leave it and report it** when judgment is needed — both sides changed the same
  logic with different intent, a failing test whose cause you can't pin down, a
  check failing for infrastructure reasons. Flagging is a success, not a failure.

When in doubt, report. An unattended pass must never guess at semantics.

## Conflict procedure

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
   5). Drive every later command with `git -C "$WORKTREE_DIR" …` rather than `cd`, so
   the procedure can't lose track of which tree it's in.

   If the main checkout is in a state where you can't make a worktree, stop and
   report why. Don't stash the user's work.

2. **Merge the default branch in** — merge, **never rebase**. The branch is already
   pushed; rebasing it would require a force-push. **Save the PR head first**: every
   later "back it out" step needs a SHA to return to, and a detached HEAD leaves you
   no branch name to fall back on.

   ```bash
   PR_HEAD_SHA=$(git -C "$WORKTREE_DIR" rev-parse HEAD)
   git -C "$WORKTREE_DIR" merge "origin/<DEFAULT_BRANCH>"
   ```

3. **Resolve the conflicts.** Use the `mattpocock-skills:resolving-merge-conflicts`
   skill when it's installed; otherwise resolve them directly. Apply the confidence
   rule per conflict. If **any** conflict in the PR needs judgment, abandon the whole
   resolution rather than pushing a half-merge — and **back out on the merge's actual
   state, not on the assumption that it's still in progress.** `git merge --abort`
   only works while `MERGE_HEAD` exists; a resolution skill (or a merge that turned
   out to be clean) may already have committed, which removes `MERGE_HEAD` and makes
   `--abort` fail with *"There is no merge to abort"*:

   ```bash
   # restore the PR head, whether or not the merge is still in progress
   if git -C "$WORKTREE_DIR" rev-parse -q --verify MERGE_HEAD >/dev/null; then
     git -C "$WORKTREE_DIR" merge --abort
   else
     git -C "$WORKTREE_DIR" reset --hard "$PR_HEAD_SHA"
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
   git -C "$WORKTREE_DIR" stash list   # expect empty; the merge is committed or in progress
   # back to the PR head, un-merged — same restore as step 3, because by now the
   # merge may well be committed and `merge --abort` would fail
   if git -C "$WORKTREE_DIR" rev-parse -q --verify MERGE_HEAD >/dev/null; then
     git -C "$WORKTREE_DIR" merge --abort
   else
     git -C "$WORKTREE_DIR" reset --hard "$PR_HEAD_SHA"
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
   git -C "$WORKTREE_DIR" merge "origin/<DEFAULT_BRANCH>"   # conflicts again, the same ones
   # …re-apply the same resolution, then commit it:
   git -C "$WORKTREE_DIR" commit --no-edit
   ```

   Skipping it is the one mistake this procedure can't feel: a restored
   `$PR_HEAD_SHA` is exactly what the remote already has, so pushing it succeeds as a
   **no-op** and the pass reports a conflict "fixed" having changed nothing. Step 5
   asserts against that rather than trusting this step to have happened.

   - **Fails the same way without the merge** → pre-existing on the PR head, or an
     infrastructure failure (no network, no test DB, missing credentials); either way
     the resolution isn't implicated. Redo the merge, push it, and report the red tests
     separately as pre-existing/infra so nobody reads the ✅ as "tests green".
   - **Only fails with the merge applied** → **two** causes fit and the rerun above
     can't separate them: your resolution, or commits the default branch brought in.
     Measure the incoming side before blaming yourself — check out the merge's other
     parent, re-run there, then come back to the PR head:

     ```bash
     git -C "$WORKTREE_DIR" clean -fd   # the rerun's droppings, before switching trees
     git -C "$WORKTREE_DIR" checkout --detach "origin/<DEFAULT_BRANCH>"
     # …re-run the same tests here…
     git -C "$WORKTREE_DIR" clean -fd
     git -C "$WORKTREE_DIR" checkout --detach "$PR_HEAD_SHA"
     ```

     Red on the default branch too → it's already broken; treat it like the first
     bullet (redo the merge, push, report the failure as inherited, not yours). Green
     there → the resolution really is wrong: restore and report, naming the failing
     tests. A baseline you **can't** run — no network, a tree the default branch can't
     even build — leaves the cause **indeterminate**: restore and report it as that,
     never as a bad resolution you didn't demonstrate.
   - **Can't tell** → restore and report. That's the confidence rule; don't push a
     merge you couldn't verify.

5. **Commit and push.** Because the worktree is on a detached HEAD, a bare
   `git push` **fails** (`git push origin HEAD:<name-of-remote-branch>`) — push the
   explicit refspec instead. Never `--force`.

   ```bash
   git -C "$WORKTREE_DIR" commit --no-edit   # if the merge didn't auto-commit
   # Assert you're pushing the resolved merge, not a head some restore rewound.
   # Step 4's baseline paths all end on a bare $PR_HEAD_SHA; if one of them ran, the
   # merge has to have been redone since, or this push is a silent no-op.
   if ! git -C "$WORKTREE_DIR" merge-base --is-ancestor "origin/<DEFAULT_BRANCH>" HEAD; then
     echo "STOP: the default branch is not in HEAD — the merge was never redone. Redo it or report; do not push."
   elif git -C "$WORKTREE_DIR" grep -nI -e '^<<<<<<< ' -e '^>>>>>>> ' HEAD; then
     echo "STOP: committed conflict markers — fix the resolution before pushing."
   else
     git -C "$WORKTREE_DIR" push origin HEAD:<headRefName>
   fi
   ```

   Both checks are about the same failure mode from opposite ends: the first catches a
   merge that never happened, the second a merge that was "resolved" by committing the
   markers. Neither is hypothetical once step 4 has rewound the tree — and a push is
   the one action in this procedure that a later pass can't quietly undo.

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
   git -C "$WORKTREE_DIR" clean -fd   # the success path never ran a restore
   git worktree remove "$WORKTREE_DIR"
   ```

   The `clean` is here for the path where **nothing went wrong**: a merge that
   resolved cleanly, passed its tests and pushed never hits a restore step, so the
   artifacts the test run left behind are still sitting there — and `git worktree
   remove` refuses on untracked files exactly as it does on modified ones.

   With that out of the way, a refusal means what it should: *tracked* state you
   didn't finish dealing with. Investigate and report it; don't reach for `--force`
   to make the error go away.

## CI procedure

1. **Identify the failing checks.** Your prompt carries the fail-bucket JSON the
   orchestrator gathered at triage, with each check's `name` and `link`.

   **If the conflict procedure pushed for this PR, that triage evidence is stale** —
   it describes the pre-merge commit. Re-run the query before you act on it, or
   you'll spend a fix on a failure the merge already resolved (or miss one it
   introduced):

   ```bash
   gh pr checks <pr_number> --json name,bucket,state,link \
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
   if the conflict procedure just pushed, fetch again rather than reusing a stale
   ref:

   ```bash
   git fetch origin
   WORKTREE_DIR="<your assigned CI worktree dir>"   # <REPO_ROOT>/.worktrees/babysit-ci-<number>
   git worktree add "$WORKTREE_DIR" "origin/<headRefName>"
   ```

   Same rules as the conflict procedure: follow the repo's own worktree skill if it
   has one, detached HEAD so no local branch can collide, `git -C "$WORKTREE_DIR" …`
   for every command, never touch the user's checkout, stop-and-report if you can't
   get a clean worktree.

5. **Verify, push, clean up.** Run the failing check's tests locally in the worktree
   and only push once they pass — a blind push spends another CI cycle to learn what
   you could have learned locally:

   ```bash
   git -C "$WORKTREE_DIR" add -A   # not `commit -am`: that skips files the fix added
   git -C "$WORKTREE_DIR" commit -m "fix: <what you fixed>"
   git -C "$WORKTREE_DIR" show --stat HEAD   # every file you touched, or you pushed a half-fix
   git -C "$WORKTREE_DIR" push origin HEAD:<headRefName>
   git -C "$WORKTREE_DIR" clean -fd   # test artifacts, or `worktree remove` refuses
   git worktree remove "$WORKTREE_DIR"
   ```

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
   git -C "$WORKTREE_DIR" checkout .   # revert edits to tracked files
   git -C "$WORKTREE_DIR" clean -fd    # …and remove any file the fix added
   git worktree remove "$WORKTREE_DIR"
   ```

   Report the re-run as *pushed, CI pending*; don't wait for the new run to finish.

## Safety

- **Never push to the default branch.** Every push in this skill targets a PR's own
  head branch.
- **Never force-push and never rebase** a branch that's already on the remote — a
  reviewer's in-progress comments and the PR's review history depend on its history
  staying put.
- **Never resolve a conflict by taking one side wholesale** (`--ours` / `--theirs`
  over a whole file) unless the file is a generated artifact you then regenerate.
- **Only ever `git clean` inside a worktree this procedure created.** It's safe there
  because that worktree started empty of untracked files, so there's nothing to
  destroy that this pass didn't make. In the user's checkout that guarantee is gone
  and `clean -fd` deletes unsaved work — always target it with
  `git -C "$WORKTREE_DIR"`, never a bare `git clean`, and never with `-x`.
- **Never resolve a review thread you didn't act on** — that's
  `review-github-comments`' rule, and it holds here.
- **Don't touch PRs you don't own.** The sweep is `--author "@me"` on purpose.
- **Don't merge PRs.** Babysitting keeps them healthy and mergeable; a human decides
  when they land.
