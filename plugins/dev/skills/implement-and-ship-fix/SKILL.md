---
name: implement-and-ship-fix
description: Ship a fix for an already-identified bug end-to-end — worktree, minimal fix, regression test, review gate, push, PR. Origin-agnostic core the Jira/ITSM/Sentry entry skills call once they know the target repo and issue. Not a starting point on its own; a caller sets its inputs.
---

# Implement and ship a fix

The generic core shared by every fix workflow: given a **known target repo**, a
**known project issue**, and an understood bug, take it from a branch to a reviewed
PR. The origin-specific work — figuring out *which* repo and issue, reading the
report, creating/linking the tracker — happens in the **entry skill** that calls
this one (`fix-sentry-issue`, `handle-jira-issue`). This skill
starts at "we know what to fix and where" and ends at "the PR is open".

Run it **once per repo**. A fix that spans several repos calls this skill once for
each, each in that repo's own worktree with its own branch and PR.

## Inputs the caller provides

The caller resolves these from `CLAUDE.md` / the triage config and passes them in —
**never hardcode or guess them here**:

- `TARGET_REPO` — the repo whose worktree this fix lands in.
- `JIRA_KEY` — the project issue the fix is tracked under (e.g. `BAC-6934`); drives
  the branch name, commit subject, and PR `## Jira` link.
- `DETAILS_KEY` — the issue to read the report/symptoms/attachments from (the ITSM
  ticket when one exists, else `JIRA_KEY`, else the Sentry issue).
- `JIRA_BASE_URL`, `DEFAULT_BRANCH` — from `TARGET_REPO`'s `CLAUDE.md`.
- **Linkage vars (optional, at most drive extra PR sections):**
  - `ITSM_ISSUE_KEY` — set when a linked ITSM ticket exists → adds the
    `Refs <ITSM_ISSUE_KEY>` commit footer and a PR `## ITSM` section.
  - `SENTRY_ID` (+ `SENTRY_URL`) — set for a Sentry-originated fix → adds the
    `Fixes <SENTRY_ID>` commit footer and a PR `## Sentry` section linking
    `SENTRY_URL`.
  - Neither set → a project-only commit footer and PR body.

> **PR / Jira link hygiene:** load the `create-pull-request` skill and follow it for
> the branch name, commit messages, and PR. The only work items these surfaces may
> link are `JIRA_KEY` and — when set — `ITSM_ISSUE_KEY`; a Sentry short id (e.g.
> `BAC-QCB`, no digits after the dash) is safe. Keep every other Jira key out.

## Step 1 — Investigate against the code

You already have the report from the entry skill (`DETAILS_KEY` details + any
attachments it analysed). Now confirm it against `TARGET_REPO`:

- Locate the code the report and any HAR / stacktrace point at.
- Derive the **true root cause** from the code — do not trust the reported/suspected
  cause blindly.
- Decide the minimal, targeted change that addresses that root cause. If you cannot
  understand or reproduce the bug from the available information, stop and report
  back to the caller (the caller owns the request-info / escalate decision).

## Step 2 — Create the branch as a worktree

All work happens inside `TARGET_REPO`. Branch name: `<JIRA_KEY>/bug/<short-kebab-description>`
(e.g. `BAC-6934/bug/dintero-payment-data-double-serialized`).

Defer to the repo's own worktree conventions:

1. If `TARGET_REPO/.claude/skills/create-worktree/SKILL.md` exists, read and follow
   it — it owns venv / isolated test-DB / direnv / FVM setup.
2. Otherwise create a plain worktree off the default branch:

   ```bash
   cd "$TARGET_REPO"
   git fetch origin
   BRANCH="<JIRA_KEY>/bug/<short-description>"
   WORKTREE_DIR=".worktrees/$(echo "$BRANCH" | tr '/' '-')"
   git worktree add -b "$BRANCH" "$WORKTREE_DIR" "origin/$DEFAULT_BRANCH"
   ```

All later steps run from `$WORKTREE_DIR`.

## Step 3 — Implement the fix

- Edit the file(s) identified in Step 1.
- Apply the minimal, targeted fix; follow existing conventions. Read any relevant
  skills in `$TARGET_REPO/.claude/skills/` for the area you touch (e.g. `models`,
  `views`, `urls`, `migrations` in the api repo); skip skills that don't exist.
- Do not refactor unrelated code (simple cleanup of the code you touch is fine — see
  the caller's contract for the scope rule).

## Step 4 — Write a regression test

Defer to the repo's testing conventions: if `writing-tests` / `running-tests` skills
exist under `$TARGET_REPO/.claude/skills/`, read and follow them.

- Add at least **1 test** that reproduces the bug and verifies the fix; place it
  beside the code being fixed.
- Reference the issue in a docstring/comment (e.g. `Regression test for BAC-6934`).
- Prove it: fails before the fix, passes after. Run it and related tests.
- If the repo offers no realistic way to add an automated regression test for this
  kind of bug, say so explicitly in the PR description — never skip silently.

## Step 5 — Commit

From inside the worktree. Choose the footer by which linkage var is set:

```bash
cd "$WORKTREE_DIR"
git add -A
git commit -m "<JIRA_KEY>: <short description>

<Optional longer description of what changed and why.>

<footer>"
```

`<footer>` is:
- `Refs <ITSM_ISSUE_KEY>` when `ITSM_ISSUE_KEY` is set, else
- `Fixes <SENTRY_ID>` when `SENTRY_ID` is set, else
- omitted entirely (project issue with no ITSM/Sentry linkage).

## Step 6 — Review gate

From inside the worktree, run the **`review-gate`** skill against `$DEFAULT_BRANCH`.
It runs the independent reviewers (`mattpocock-skills:code-review` / cold
subagent / self-review, plus Codex when installed), de-dups findings,
fixes the valid ones, tracks the skipped ones, and returns:

- **`PASS`** → keep its notes block for the PR body; continue.
- **`BLOCK: <reason>`** → a disputed Critical/High (or a valid one unsafe to fix
  here). **Do not push, do not open a PR.** Return the block to the caller — the
  caller's contract owns the escalate/escape-hatch response.

## Step 7 — Push

```bash
cd "$WORKTREE_DIR"
git push -u origin <branch-name>
```

## Step 8 — Open the PR

Follow the **`create-pull-request`** skill for the `gh pr create` recipe, the
labels-at-creation rule, and link hygiene. Include the `## ITSM` section only when
`ITSM_ISSUE_KEY` is set, and the `## Sentry` section only when `SENTRY_ID` is set:

```
## Summary
<description of the fix>

## Jira
[<JIRA_KEY>](<JIRA_BASE_URL>/browse/<JIRA_KEY>)

## ITSM            ← only when ITSM_ISSUE_KEY is set
[<ITSM_ISSUE_KEY>](<JIRA_BASE_URL>/browse/<ITSM_ISSUE_KEY>)

## Sentry          ← only when SENTRY_ID is set
[<SENTRY_ID>](<SENTRY_URL>)

## Changes
- <bullet summary of changes>

## Testing
- <the test(s) added, or an explicit statement that no automated regression test was feasible and why>

## Code review (review-gate)
Reviewers run: <independent review (mattpocock-skills:code-review / subagent / self-review), Codex — note any skipped as unavailable/error>

### Findings addressed
- <reviewer> · <severity>: <finding> — <what was done>

### Findings not addressed
- <reviewer> · <severity>: <finding> — <reason for skipping>
```

Report the PR url back to the caller. The caller owns labelling, the review-comment
loop, worktree cleanup, and the final RESULT block.
