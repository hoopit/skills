---
name: triage-sweep
description: Triage new board issues unattended. Use when a loop or the user asks to sweep new issues.
---

# Sweep the board's new issues

Board: the board in your `hoopit-board` config — `hoopit-board config` prints it.

Nobody is present, so every call here is yours or stays open on the issue. The sweep sets
fields, names footprints, retires false decisions and stamps. Status stays as it is, and
grilling stays with `gh-triage`.

## 1. List

```bash
hoopit-board triage-due
```

Exit 1 means nothing is due: end the run. Otherwise take the first 20 entries, highest
ranked first, and leave the rest for the next run. Each entry's `reason` is `new`, `changed`
or `expired`; an `expired` item takes step 4 and the stamp alone.

Read code on the default branch, fetched first, in the checkout `hoopit-board config`
prints.

**Done when** the batch is chosen.

## 2. Fields

Where the issue lacks Priority, Effort or Autonomy, set them from the rubrics in
`create-gh-issue`, with the section each non-`Unattended` value owes the body (`gh-triage`,
step 2). An item already in Ready becomes startable the moment it reads `Unattended`, so
hold that value to the rubric's test: decided and reachable.

**Done when** the item carries all three.

## 3. Footprint

Skip this step where a backticked path in the body resolves in the checkout. Otherwise read
the code and add the files the fix will edit, as backticked paths, each confirmed in the
checkout. A file the issue only cites stays out: `hoopit-board next` treats every resolved
path as a claim, so a wrong one blocks real work. Where the cause is still unknown, name no
file, and leave the app or the lead you found in prose.

Re-read the body right before writing it, then:

```bash
gh api -X PATCH repos/<repo>/issues/<n> -F body=@<file>
```

**Done when** the body names each file you are sure of, and only those.

## 4. Collapse

Run this step over the batch's `Needs decision` items together. Your contract is
`## 3. Collapse` in `${CLAUDE_PLUGIN_ROOT}/skills/gh-triage/SKILL.md`, fan-out, production and
Sentry reads, and closing the sessions included. With nobody present, three things differ:

- Start each repo's session with `--permission-mode bypassPermissions`, so a read never
  waits on a prompt. The contract's prompt keeps it read-only on GitHub and the repo.
- Give the sessions 30 minutes. A repo with no `summary.txt` by then is untested: its
  session stays open and its items stay unstamped, so the next run takes them.
- Where a production or Sentry read fails, the item survives, and its comment names the
  measurement an attended run owes.

**Done when** each item has its comment and is either `Unattended` or names its decision, or
sits in a repo named untested.

## 5. Stamp

Stamp last, so a run that dies leaves the item due:

```bash
hoopit-board triage <repo> <n> --tested
```

**Done when** every item in the batch is stamped, or named in the report with what stopped it.

## 6. Report

One line per item: its values, the paths added, its verdict. Then what stays due.
