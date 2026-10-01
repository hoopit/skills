---
name: gh-followup
description: Work the board's Manual and Waiting buckets — re-test each blocker, convert what the board can hold itself, walk what only you can do, and summarise what the rest waits for.
argument-hint: "[repo#n] — start with this item, instead of the top of the bucket"
disable-model-invocation: true
---

# Work the Manual and Waiting buckets

Board: the board in your `hoopit-board` config — `hoopit-board config` prints it.

`Manual` and `Waiting` label a **blocker**, and a blocker is a condition in the world — a
promotion that has not happened, a date that has not fallen, a person who has not replied.
The label is static and the condition is not, so the buckets fill with items whose blocker
has already **lifted** and items whose blocker has a proper home on the board that nobody
gave it.

So this run has three products, in this order of value:

1. **Conversions** — items the board can hold and release by itself, which stop needing a
   human to remember them.
2. **A ranked shortlist of what is doable now**, walked one at a time.
3. **One line per item still waiting**, naming its blocker and who owns it.

## 1. Read the bucket

```bash
hoopit-board decisions --manual --waiting
```

Every item, not a sample: the bucket's whole failure mode is an item nobody re-read.

## 2. Re-test every blocker

For each item, name what it actually waits for, then check whether that is still true
today. The kinds, and the test for each:

| Waits for | Test | Where it belongs once tested |
|---|---|---|
| A **deploy** | the repo's rollout-status skill, where it has one, on the PR that ships it | `Gate: deployed #<pr>` + `Unattended` — the board releases it on promotion |
| A **date** | the date against today | `--not-before YYYY-MM-DD` + `Unattended` |
| **Another party** — NIF, a payment processor, a partner | when they were last chased, and by whom | `Waiting`, with a `## Waiting on` section; the next action is a chase, and it is the user's |
| A **dashboard, credential or app-store step** | nothing — this is the genuine article | `Manual`; §4 walks it |
| A **release** in a repo with no production branch | the store version, or the bundle live on the site | `--not-before` at the earliest landing, a `Start only when` section, and `Unattended` |
| An **access gap** — a permission the agent role lacks | whether the role has it now | the grant filed as its own issue, this one `blockedBy` it and `Unattended` |
| A **decision or approval** of yours | nothing — it is a question | `Needs decision`, with `## The decision` |
| **Another repo's code** | whether a checkout reaches it (the repos in your config are all checked out under the configured checkouts directory) | `Unattended` in that repo, unless it needs a device or a store submission |
| A **prod write** — a backfill, a repair, a one-off script | whether it reads or writes | reads convert; writes stay `Manual` |

**The read/write line is the one to get right.** Production is *readable* through
the repo's production-read skill where it has one, so a post-rollout verification —
"confirm the constraint is valid", "confirm this Sentry issue stops", "count the rows
that are still wrong" — is reachable work an agent does, and belongs on the board as
`Unattended` with a deploy gate. A
backfill, a repair, a row edit or anything that writes stays the user's — unless its
command is still to write: then it converts to one `Unattended` issue whose PR asks the
user for the run before it merges (`create-gh-issue`). An item that
verifies *and then repairs* splits: the verification converts, the repair waits on its
result.

State each item's blocker and verdict as you go. An item whose blocker you cannot name is
the finding: say so rather than leaving it labelled.

**Done when** every item in the bucket has a named blocker and a verdict of lifted,
convertible, or waiting.

## 3. Convert

Every item whose blocker has a home moves there, and says in its body what it is waiting
for — the field carries no reason:

```bash
hoopit-board triage <repo> <n> --autonomy Unattended            # a checkout reaches it now
hoopit-board triage <repo> <n> --autonomy Unattended --not-before 2026-10-25
# plus, for a deploy gate, a `Gate: deployed #<pr>` line in the body
```

A conversion is the durable win here: it is one item a human never has to remember again,
and it survives this run whether or not anything else in it does. Report the count.

## 4. Walk what is doable now

What is left that the user's own hands can do, ranked by Priority, and offer the top of
it. One item at a time.

For a single action — a dashboard flip, an SSM delete, a key revoke — give the exact
steps, then confirm the result together and record it on the issue.

For anything multi-step, or anything that has to be got right in one pass against
production, generate the walkthrough with `mattpocock-skills:wizard` rather than a list
of instructions in chat. A wizard holds its place when the user stops halfway, which a
chat message does not.

Either way, the issue gets a comment saying what was done, what it returned, and what is
left. Close it only where the user says the work is finished.

An item that turns out to have a reachable part and a `Manual` part splits: file the
reachable part through `create-gh-issue` as `Unattended`, and leave the remainder here
with the split named. A command to write and its run stay one item (`create-gh-issue`).

## 5. Summarise the waiting

One line per item still in the bucket: the item, its blocker, who owns lifting it, and —
where it is another party — how long it has been waiting. Longest wait first, because
that is the one most likely to have been dropped rather than deferred.

An item waiting on a party who has never been chased is not waiting, it is stalled. Call
those out separately; they are the cheapest thing in this run to fix.

## 6. Report

- Conversions, with the home each one moved to. The headline number.
- What was done this run, and what it returned.
- The doable shortlist not yet started, ranked.
- The waiting list, longest first, with the stalled ones marked.
- Items whose blocker could not be named.
