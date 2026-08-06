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

Workers don't inherit this skill's text, so resolve the paths they'll read it from:

```bash
SKILL_FILE=$(find ~/.claude/plugins -path '*babysit-prs/SKILL.md' 2>/dev/null | head -1)
# Fallback when the skill runs from a source checkout rather than an installed plugin:
[ -n "$SKILL_FILE" ] || SKILL_FILE="$(git rev-parse --show-toplevel)/$(git ls-files '*babysit-prs/SKILL.md' | head -1)"
SKILL_DIR=$(dirname "$SKILL_FILE")   # its references/ dir sits here
```

The two long per-PR procedures live in `$SKILL_DIR/references/` — one file per axis:

| Axis | Procedure file |
|---|---|
| Merge conflict | `$SKILL_DIR/references/conflict-procedure.md` |
| Failing checks | `$SKILL_DIR/references/ci-procedure.md` |

**Don't read either one here.** Orchestrating needs neither: you pass their absolute
paths into the worker prompts (Step 4), and each worker reads only the file for the
axes it was flagged on. Keeping ~300 lines of git surgery and CI archaeology out of
the orchestrating context is the point — under `/loop` it would otherwise be re-read
into a session that never uses it. The inline fallback in Step 4 is the one path that
reads them, one axis at a time, as it reaches it.

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
re-reading this file and the one or two axis procedures it was actually flagged on,
and buys the thing this design exists for: the CI logs, diffs, and merge churn land
in the worker's context, not the orchestrator's. Under `/loop` the orchestrator's session accumulates pass after pass,
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

Flagged axes — handle only these, in this order (conflicts → CI → comments). Each
one's full procedure is in its own file: read that file when you reach the axis, and
do not read the file for an axis flagged "no" / "none" / "0".
- Merge conflict: <yes (mergeable=…, mergeStateStatus=…) | no>
  Procedure: <SKILL_DIR — literal absolute path>/references/conflict-procedure.md
- Failing checks: <the fail-bucket JSON from triage | none>
  Procedure: <SKILL_DIR — literal absolute path>/references/ci-procedure.md
- Unresolved review threads: <count | 0>
  Procedure: invoke the `review-github-comments` skill with the PR URL above

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
sequentially, under the same *Per-PR procedures* contract below and the same report
contract, and fully finishing one PR — including worktree removal — before starting
the next. This is the one path where you read the procedure files yourself: read each
flagged axis's file as you reach that axis, not upfront.

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
values from its prompt plus what it reads here and in the procedure files this
section routes to. When the pass runs inline (no Agent tool), the orchestrator
follows these same procedures itself, one PR at a time.

Work the flagged axes **in order: conflicts → CI → review comments** — a conflicted
branch can't be meaningfully tested, and the comment pass pushes its own commits on
top. Skip axes your prompt didn't flag.

Each axis's procedure is a separate file. **Read only the ones your prompt flagged,
and read each as you reach its axis** — your prompt gives their absolute paths; the
relative paths below are the same files:

| Flagged axis | Procedure |
|---|---|
| Merge conflict | [`references/conflict-procedure.md`](references/conflict-procedure.md) |
| Failing checks | [`references/ci-procedure.md`](references/ci-procedure.md) |
| Unresolved review threads | invoke the **`review-github-comments`** skill with the PR URL |

Both files assume this section and *Safety* below: they carry the commands and the
reasoning behind them, and repeat neither the confidence rule nor the safety rails.
Each keeps its **own** step numbering (1–7 for conflicts, 1–5 for CI), which is not
the orchestrator's Steps 1–5 above.

## The confidence rule

Applies to every fix in this skill:

- **Fix it** when the change is mechanical and the correct result is unambiguous —
  non-overlapping edits in the same file, both sides adding imports/exports, a
  regenerated lockfile, an obviously-stale reference to something you renamed.
- **Leave it and report it** when judgment is needed — both sides changed the same
  logic with different intent, a failing test whose cause you can't pin down, a
  check failing for infrastructure reasons. Flagging is a success, not a failure.

When in doubt, report. An unattended pass must never guess at semantics.

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
