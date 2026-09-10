---
name: ship
description: Take one understood piece of work in one repo from a branch to a monitored PR. Use when asked to implement, fix, ship or handle an issue.
argument-hint: "<the work, or the item tracking it> [--rounds <N>]"
---

# Ship

The shared spine of every shipping workflow: given a **known repo** and an
**understood piece of work**, take it from a branch to an open PR with a watch on it.
Bug, feature, chore; Jira, GitHub issue, Sentry, or nothing tracked at all — the shape
is the same, and each step defers its specifics to the repo's own conventions.

Origin-specific work — reading the report, resolving *which* repo, creating or linking
the tracker item — belongs to the caller, which sets the inputs below. Invoked directly,
you set them yourself from what the user gave you.

One invocation ships **one PR in one repo**. Work spanning several repos runs this skill
once per repo, independently.

Flags:

- `--rounds <N>` — the review-gate round budget (Step 6). Default 5.

## Inputs

- `TARGET_REPO` — the repo this work lands in.
- `BRIEF` — what to change and why, plus where to read fuller detail (the ticket, the
  stacktrace, the attachments, the conversation).
- `WORK_ITEM` *(optional)* — the tracked item this delivers: its key/id, canonical URL,
  and which tracker it lives in. Unset for ad-hoc work; the PR then says so.

Every other fact this skill needs is read at runtime from `TARGET_REPO` —
`DEFAULT_BRANCH` and tracker config from its `CLAUDE.md` *Workflow skills config*,
conventions from the repo itself.

## Step 1 — Investigate against the code

Confirm the brief in `TARGET_REPO` before changing anything: locate the code it points
at, and derive the **true** cause or the right design yourself rather than trusting the
reported one. Decide the minimal change that addresses it.

Done when you can name the change and defend why it is the right one. If the available
information cannot get you there, stop and report back — the caller (or the user) owns
the request-info / escalate decision.

## Step 2 — Create the branch as a worktree

Name the branch after the work item's source: mirror the shape the repo already uses
(`git branch -r`), and carry the item's key when its tracker uses keys — the key on the
branch is what a tracker integration scans to attach the PR (`create-pull-request` owns
which keys are allowed there).

Follow `$TARGET_REPO/.claude/skills/create-worktree` when it exists — it owns the repo's
venv / isolated test DB / direnv / FVM setup. Otherwise create a plain worktree off the
default branch:

```bash
cd "$TARGET_REPO" && git fetch origin
git worktree add -b "$BRANCH" ".worktrees/$(echo "$BRANCH" | tr '/' '-')" "origin/$DEFAULT_BRANCH"
```

Every later step runs from the worktree.

## Step 3 — Implement

A bug's test comes first: go to Step 4, write the test that reproduces it, and watch it
go **red** before you write the fix. The fix is what turns it green.

Apply the minimal, targeted change. Follow the conventions of the code around you, and
read the skills in `$TARGET_REPO/.claude/skills/` covering the area you touch. Cleaning
up code you are already editing is fine; refactoring beyond the change is not.

Done when the change stands on its own: you can say which behaviour it alters and every
edit in the worktree serves it.

## Step 4 — Test

Your judgement, against the repo's bar — follow its testing skills (`writing-tests` /
`running-tests`) and the conventions of the tests beside the code you touched.

A bug is not fixed until a test has gone **red** on it. Write that test before the fix.
With the fix already in place, stash it (`git stash`), watch the test fail, restore it
(`git stash pop`) and watch it pass — an unproven regression test is one that may be
asserting nothing. Other work earns whatever coverage the repo expects of it. Run the new
tests and the ones around them.

If the repo offers no realistic way to test this change automatically, say so explicitly
in the PR body — never silently.

## Step 5 — Commit

Follow the repo's commit conventions; `git log` is the source of truth for its subject
style and footers. Reference `WORK_ITEM` the way its tracker expects, and load
`create-pull-request` before writing the message — it owns which work-item keys are
allowed on a commit.

## Step 6 — Review gate

A **round** is one run of the **`review-gate`** skill from inside the worktree, plus the
fix commits that run makes. Work rounds until the gate comes back clean, on a budget of
`--rounds`.

Hand the gate `WORK_ITEM` and `BRIEF` as its `SPEC` — without them its Spec axis
self-skips and half the review silently disappears. The spec is all it gets: keep your
investigation and your fix's reasoning to yourself, because cold eyes are what the gate
is for.

**Scope each round.** The two-axis independent review is what the gate spends; aim it at
code no reviewer has seen. Before each round record `REVIEWED_AT` — the commit `HEAD`
stands at as that round's reviewers start.

- **Round 1 runs `full`**: the whole branch against `$DEFAULT_BRANCH`, both axes. A
  `full` pass challenges the approach as well as the code; hand it the shape you took and
  the ones you set aside as `CHALLENGE`, so the focus is yours rather than derived, and
  the approach is questioned while changing it is still cheap.
- A later round runs **`full`** when the commits since `REVIEWED_AT` are substantial —
  they touch a file no reviewer has seen, they exceed ~50 changed lines, or one of them
  fixed a Critical/High finding. `git diff --stat "$REVIEWED_AT"..HEAD` settles the first
  two; the third you already know from the round that made them.
- Every other round runs **`light`** — pass `SCOPE=light` and `REVIEWED_AT`, and the gate
  reviews those commits alone, on the Standards axis.

Each round returns one verdict:

- **`PASS`, no fixes made** — clean. Keep the gate's notes block for the PR body and go
  to Step 7.
- **`PASS` after fixes** — the reviewers never saw the fixed code, and a fix is where the
  next round's findings come from. Run another round: clean means nothing left, not
  nothing new.
- **`BLOCK: <reason>`** — **do not push, do not open a PR.** Ask.

At the budget with the gate still unclean, stop and ask. Whether the rounds are
converging is the substance of that question: fewer findings each round argues for
another budget, the same finding surviving every round argues for the user.

Both paths reach the user the same way. Put the substance in chat first — the blocking
or surviving findings, your reasoning, what you would do about each — then fire
`AskUserQuestion` headed `Review gate` to carry the attention:

| Path | Options |
| --- | --- |
| `BLOCK` | **Answer in chat** (recommended) · **Take all your recommendations** · **Open the PR anyway, with the block in its body** |
| Budget spent | **Another `--rounds` rounds** · **Open the PR anyway, with the findings in its body** · **Answer in chat** |

An answer settles the findings it covers and rounds resume with the budget left intact;
*Open the PR anyway* carries the standing findings into the PR body (Step 7).

Running unattended under a caller, hand the verdict back to it instead — a question
asked with nobody there stops the work and reaches no one.

## Step 7 — Push and open the PR

The head you push is one the gate has passed. A commit made after the last round's
reviewers ran — a docstring, a measurement, a line a peer suggested — is code no cold eye
has seen, and it is where a PR's first review threads come from. Run a `light` round over
it first, or leave it out.

```bash
git push -u origin "$BRANCH"
```

Follow the **`create-pull-request`** skill for the body, the labels-at-creation rule, and
link hygiene. Add to the body it specifies:

- the `WORK_ITEM` link section — or, unset, a line saying the change is untracked;
- a `## Testing` line covering the tests added, or why none was feasible;
- the review-gate notes across every round: the scope it ran at, which reviewers ran,
  findings addressed, findings skipped and why — and, when the user chose to open past a
  block or a spent budget, the findings still standing and that they chose to ship over
  them;
- any extra sections the caller asked for.

## Step 8 — Hand the PR on

Someone has to work the PR's review rounds to the merge. Who, depends on whether a human
is there:

- **A human is there** — start the **`monitor-pr`** skill on the new PR with `--subagent`,
  so its rounds run in workers rather than this session. It works rounds on its own budget
  and comes back to the user when that budget is spent, when a decision only they can
  settle turns up, or when the PR merges — and on the merge it cleans up the worktree
  itself.
- **Running unattended under a caller** — arm nothing. A watch that runs to the merge
  outlives a one-shot run. Hand the PR back; the caller's contract owns everything after
  it opens.

Either way this skill's work ends here. Report the PR url — and the watch, if you armed
one — back to the caller, which owns the final result block.
