---
name: triage-sweep
description: Triage new board issues unattended. Use when a loop or the user asks to sweep new issues.
---

# Sweep the board's new issues

Board: the board in your `hoopit-board` config — `hoopit-board config` prints it.

Nobody is present, so every call here is yours or stays open on the issue. The sweep sets
fields, names footprints, links dependencies, retires false decisions and stamps. Status
moves only for a startable bug (step 2), and grilling stays with `gh-triage`, which runs
these same steps as its first part.

## 1. List

```bash
hoopit-board triage-due
```

Exit 1 means nothing is due: end the run. Otherwise take the first 20 entries, highest
ranked first, and leave the rest for the next run. Each entry's `reason` is `new`, `changed`
or `expired`; an `expired` item takes step 5 and the stamp alone.

Read code on the default branch, fetched first, in the checkout `hoopit-board config`
prints.

**Done when** the batch is chosen.

## 2. Fields

Where the issue lacks Priority, Effort or Autonomy, set them from the rubrics in
`create-gh-issue`, and state each value with a one-clause reason:

```bash
hoopit-board triage <repo> <n> --priority P2 --effort M --autonomy Unattended
```

An item already in Ready becomes startable the moment it reads `Unattended`, so hold that
value to the rubric's test: decided and reachable. Where a dispatcher runs with a dispatch
ladder configured, Effort also picks the model; either way the rubric prices the hunt along
with the fix, and this is the one pass that reads the issue closely enough to see the hunt.

Where a value you set makes the item a **startable bug** (`create-gh-issue`, Status), add
`--ready`. An item whose fields you leave as they are keeps its Status.

The three non-`Unattended` values owe the body a section:

- `Needs decision` — a `## The decision` heading naming the question and the shapes it
  could take, so clearing it costs a sentence. Write it now where it is missing; an
  unnamed decision costs a re-read before anyone can answer it, and those pile up under
  `hoopit-board decisions --unnamed`.
- `Waiting` — a `## Waiting on` section naming the party, what was asked, and when they
  were last chased.
- `Manual` — what it needs that no checkout has. Where part of it *is* reachable, file that
  part as its own `Unattended` issue. A command to write and run stays one issue
  (`create-gh-issue`, step 3).

The body also owes whoever starts it a **lead** — a file, a symbol, a log line worth starting
from. A lead points; the agent draws the conclusion.

**Done when** the item carries all three, with the section its Autonomy owes.

## 3. Footprint

Skip this step where a backticked path in the body resolves in the checkout. Otherwise read
the code and add the files the fix will edit, as backticked paths, each confirmed in the
checkout. A file the issue only cites stays out: `hoopit-board next` treats every resolved
path as a claim, so a wrong one blocks real work. Where the cause is still unknown, name no
file, and leave the app or the lead you found in prose. An issue naming no path reads as
collision-free, and a migration the judgement cannot place in an app (`MIGRATION-GRAPH:*`)
collides with every migration in flight and starves, so the app is the least to name.

Re-read the body right before writing it, then:

```bash
gh api -X PATCH repos/<repo>/issues/<n> -F body=@<file>
```

**Done when** the body names each file you are sure of, and only those.

## 4. Dependencies

A dependency is an order the work forces: until another open issue closes, this issue's
acceptance cannot pass, or its diff would be wasted. A `blockedBy` link holds it out of
`startable` until the blocker closes.

Read the open board once, for the whole batch; `blocked-by:` in a row's signals is a link
already set:

```bash
hoopit-board scan --no-judge
```

Test each item in both directions, what it waits on and what waits on it, across repos. The
evidence is one of:

- The body names the order: "after", "depends on", "needs", a `follows` whose issue is still
  open, a `Start only when` naming an issue.
- It needs an endpoint, field, symbol or decision another open issue creates. A client half
  waits on its backend half.
- Another open issue rewrites or removes what this one changes.

Every other relation has its own home:

| Relation | Home |
| --- | --- |
| Shares files | The footprint: `next` holds the collision by itself |
| Waits on a pull request or a deploy | `Gate: deployed` |
| A piece of a whole | Sub-issue |
| Same area, no forced order | A cross-reference in the body |

Link only what you can state in one clause. A wrong link starves the item silently, while a
missed one costs an agent a handback, so an unsure pair stays a cross-reference. Autonomy is
judged as if the blocker had closed.

```bash
hoopit-board blocked-by <repo> <n> <ref>...            # #12 or org/repo#12; refuses a cycle
gh api -X POST repos/<repo>/issues/<n>/comments -f body="Blocked by <ref>: <the clause>"
hoopit-board blocked-by <repo> <n> <ref> --remove      # a link whose reason has gone
```

**Done when** every item is tested in both directions, and each link added carries its clause
in a comment.

## 5. Collapse

Run this step over the batch's `Needs decision` items together. Your contract is
`## The collapse` in `${CLAUDE_PLUGIN_ROOT}/skills/gh-triage/SKILL.md`, fan-out, production and
Sentry reads, and closing the sessions included. With nobody present, three things differ:

- Start each repo's session with `--permission-mode bypassPermissions`, so a read never
  waits on a prompt. The contract's prompt keeps it read-only on GitHub and the repo.
- Give the sessions 30 minutes. A repo with no `summary.txt` by then is untested: its
  session stays open and its items stay unstamped, so the next run takes them.
- Where a production or Sentry read fails, the item survives, and its comment names the
  measurement an attended run owes.

**Done when** each item has its comment and is either `Unattended` or names its decision, or
sits in a repo named untested.

## 6. Stamp

Stamp last, so a run that dies leaves the item due:

```bash
hoopit-board triage <repo> <n> --tested
```

**Done when** every item in the batch is stamped, or named in the report with what stopped it.

## 7. Report

One line per item: its values, any move to Ready, the paths added, the links set, its verdict.
Then what stays due.
