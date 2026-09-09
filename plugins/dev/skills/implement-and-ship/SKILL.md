---
name: implement-and-ship
description: Take one understood piece of work in one repo from a branch to a monitored PR — worktree, implementation, tests, review gate, PR, monitor-pr. Tracker-agnostic and project-agnostic. Use when the work to do and the repo are already known, whether a caller skill resolved them (fix-sentry-issue, handle-jira-issue) or you were handed them directly.
---

# Implement and ship

The shared spine of every shipping workflow: given a **known repo** and an
**understood piece of work**, take it from a branch to an open PR with a watch on it.
Bug, feature, chore; Jira, GitHub issue, Sentry, or nothing tracked at all — the shape
is the same, and each step defers its specifics to the repo's own conventions.

Origin-specific work — reading the report, resolving *which* repo, creating or linking
the tracker item — belongs to the caller, which sets the inputs below. Invoked directly,
you set them yourself from what the user gave you.

One invocation ships **one PR in one repo**. Work spanning several repos runs this skill
once per repo, independently.

## Inputs

- `TARGET_REPO` — the repo this work lands in.
- `BRIEF` — what to change and why, plus where to read fuller detail (the ticket, the
  stacktrace, the attachments, the conversation).
- `WORK_ITEM` *(optional)* — the tracked item this delivers: its key/id, canonical URL,
  and which tracker it lives in. Unset for ad-hoc work; the PR then says so.

Everything else is read at runtime from `TARGET_REPO` — `DEFAULT_BRANCH` and tracker
config from its `CLAUDE.md` *Workflow skills config*, conventions from the repo itself.
Never carry a project's facts into this skill.

## Step 1 — Investigate against the code

Confirm the brief in `TARGET_REPO` before changing anything: locate the code it points
at, and derive the **true** cause or the right design yourself rather than trusting the
reported one. Decide the minimal change that addresses it.

Done when you can name the change and defend why it is the right one. If the available
information cannot get you there, stop and report back — the caller (or the user) owns
the request-info / escalate decision.

## Step 2 — Create the branch as a worktree

Follow `$TARGET_REPO/.claude/skills/create-worktree` when it exists — it owns the repo's
venv / isolated test DB / direnv / FVM setup. Otherwise create a plain worktree off the
default branch:

```bash
cd "$TARGET_REPO" && git fetch origin
git worktree add -b "$BRANCH" ".worktrees/$(echo "$BRANCH" | tr '/' '-')" "origin/$DEFAULT_BRANCH"
```

Name the branch after the work item's source: mirror the shape the repo already uses
(`git branch -r`), and carry the item's key when its tracker uses keys — the key on the
branch is what a tracker integration scans to attach the PR. `create-pull-request` owns
which keys may appear on that surface.

Every later step runs from the worktree.

## Step 3 — Implement

Apply the minimal, targeted change. Follow the conventions of the code around you, and
read the skills in `$TARGET_REPO/.claude/skills/` covering the area you touch. Cleaning
up code you are already editing is fine; refactoring beyond the change is not.

## Step 4 — Test

Your judgement, against the repo's bar — follow its testing skills (`writing-tests` /
`running-tests`) and the conventions of the tests beside the code you touched.

A bug is not fixed until a test goes **red** on it: write the test first, watch it fail,
then confirm the fix turns it green. Other work earns whatever coverage the repo expects
of it. Run the new tests and the ones around them.

If the repo offers no realistic way to test this change automatically, say so explicitly
in the PR body — never silently.

## Step 5 — Commit

Follow the repo's commit conventions; `git log` is the source of truth for its subject
style and footers. Reference `WORK_ITEM` the way its tracker expects, and load
`create-pull-request` before writing the message — it owns which work-item keys are
allowed on a commit.

## Step 6 — Review gate

From inside the worktree, run the **`review-gate`** skill against `$DEFAULT_BRANCH`. It
returns exactly one verdict:

- **`PASS`** → keep its notes block for the PR body; continue.
- **`BLOCK: <reason>`** → **do not push, do not open a PR.** Return the block and its
  findings to the caller, which owns the escalate / escape-hatch response.

## Step 7 — Push and open the PR

```bash
git push -u origin "$BRANCH"
```

Follow the **`create-pull-request`** skill for the body, the labels-at-creation rule, and
link hygiene. Add to the body it specifies:

- the `WORK_ITEM` link section — or, unset, a line saying the change is untracked;
- a `## Testing` line covering the tests added, or why none was feasible;
- the review-gate notes: which reviewers ran, findings addressed, findings skipped and
  why;
- any extra sections the caller asked for.

## Step 8 — Monitor the PR

Start the **`monitor-pr`** skill on the new PR with `--subagent`, so its rounds run in
workers rather than this session.

Report the PR url and the watch back to the caller, which owns worktree cleanup (skill
`clean-up-worktree`, once the PR is merged) and the final result block.
