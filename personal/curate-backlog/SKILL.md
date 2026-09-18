---
name: curate-backlog
description: Clean up LKs agent project — duplicates, merges, stale and invalid issues, missing triage.
disable-model-invocation: true
---

# Curate the backlog

Board: **LKs agent project** — <https://github.com/orgs/hoopit/projects/2>.

Every open item leaves this run **settled** — closed, absorbed, retriaged — or
**surfaced** as a doubt. Act on the evidence in front of you; reserve the doubt
list for the calls that genuinely turn on judgement. A backlog curated into a
second backlog of approvals has moved the work, not done it. Done items get a
sweep of their own at the end.

Items that are **In progress**, **AI review** or **Human review** are never closed or absorbed
here — an agent may be inside one right now. They can be retriaged, and
anything that looks abandoned goes on the doubt list. An item started by
`start-backlog-daemon` or `gh-triage` carries a comment naming its agent; that is how you
tell abandoned from busy, and a later `Handed back to the backlog` comment
cancels it — an assessment gave that slot up, and the item is ordinary again.

## 1. Scan the board

```bash
hoopit-board scan
```

`hoopit-board` is the board's mechanical half; `--help` lists it. It lives in
the `create-gh-issue` skill, at `scripts/hoopit-board`, and reaches `PATH`
through a symlink. `scan` prints every open item with the signals that nominate it, then
the pairs whose titles share enough vocabulary to be worth reading as
duplicates.

Bodies stay out of it deliberately — they run to thousands of tokens each. Pull
them a cluster at a time, for the pairs and the flagged items only:

```bash
gh api repos/<repo>/issues/<n> --jq '{number, title, state, body}'
```

`gh issue view` reads the same thing over GraphQL, and a cluster of twenty is
twenty calls against a bucket the `gh project` writes later in this run have no
REST alternative for. Add `/comments` to the path when a thread matters.

## 2. Nominate a bucket for every open item

Every open item gets a nomination here and a final bucket after step 3. The
run is done when each one sits in exactly one, and the report names which.

| Bucket | The evidence that puts it there |
|---|---|
| **Shipped** | A linked PR is merged, or another merged PR closes it. |
| **Duplicate** | Another open issue covers the same change. |
| **Absorbed** | Two issues are one piece of work — same file, same fix, one PR. |
| **Invalid** | The premise is false against today's code. |
| **Stale** | The code it describes is gone or rewritten past recognition. |
| **Live** | Keep it. Triaged, or retriaged here. |
| **Not an issue** | A `PullRequest` item on the board — its issue already tracks it. |
| **Doubt** | Anything above that you cannot show. |

`scan`'s signals nominate most of these on their own. Duplicate and Absorbed
are the two it can only suggest: those are yours to judge, off the bodies.

## 3. Verify the flagged ones against the code

Cheap signals nominate Shipped, Invalid and Stale; only the code confirms them.
Dispatch one Sonnet subagent per flagged item, in parallel, read-only, each
given the issue body, the repo, and one question: **does this still describe
the code as it is?**

Send the signal that flagged it too — "the linked PR looks merged", "the path
it names is gone" — as a lead, not a finding. The verdict it owes you is on the
issue, not on your signal, so ask for the falsifier with it: what would show
this issue is still live, and is that there in the code? A subagent asked to
confirm a signal confirms it.

A subagent that comes back uncertain has found a doubt, not a close.

## 4. Settle what you can show

```bash
gh issue close <n> --repo <repo> --reason completed --comment 'Shipped in #<pr>.'
gh issue close <n> --repo <repo> --duplicate-of <m>
gh issue close <n> --repo <repo> --reason 'not planned' --comment '<the evidence>'
hoopit-board drop <repo> <n> --apply                       # a PullRequest item
```

Closing an issue carries its board item to Done on its own.

**Absorbing** is two moves: edit the survivor's body so it covers the whole
scope — `gh issue edit <survivor> --repo <repo> --body-file <path>` — then
close the other with `--duplicate-of <survivor>` and a comment naming what
moved. The survivor is the one with the better write-up, not the lower number.

**Retriage** every Live item `scan` marked `untriaged`, with
`hoopit-board triage <repo> <n> --priority P2 --effort M --autonomy Unattended`.
The rubrics are in the `create-gh-issue` skill; use those rather than inventing
a second scale.

Sweeping more than a handful, pipe them into `hoopit-board batch` instead —
`<repo>#<n>` and tab-separated `Field=Value` a line — which spends a few
GraphQL points on the lot rather than two an item.

Autonomy is the axis this run backfills — most of the backlog predates the
field, and a blank one keeps an item out of every `--unattended` run however
well it is ranked. Read it off the body like the other two. An item you would
have to ask about to judge is `Needs decision` by that fact, and it belongs on
the doubt list with the decision named.

## 5. Sweep the Done items

Done items idle past 7 days are history, and they are most of the board.

```bash
hoopit-board archive-done          # lists what it would take
hoopit-board archive-done --apply  # takes it
```

## 6. Report

One table of what changed — item, bucket, action — then the doubts, each with
the specific question you want answered. Close with the board's open count
before and after.
