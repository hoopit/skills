---
name: atlassian-cli
description: Use when working with Jira or Confluence from command line, including authentication, searching issues with JQL, bulk operations, sprint reports, or creating/updating work items using acli
---

# Atlassian CLI (acli)

Command-line access to Jira and Confluence. Check auth first, use the modern command
structure, and reach for batch operations over loops.

## Creating a work item needs the human's go-ahead

Jira is the team's tracker: a work item there is planned, prioritised and reported on,
and someone other than its author carries it. So an agent creates or bulk-creates one
only when the human has said to, in this conversation — a standing preference for
filing elsewhere is not that permission, and neither is a finding that plainly deserves
tracking. Say what you would file and let them answer.

This binds every project (`BAC`, `WEB`, `FA`) and every driver. It is not a per-person
setting: the cost lands on the team either way. Reading, searching and viewing are
free — the gate is on writes that create work.

Agent-driven work items — follow-ups, findings, the tickets cut from a spec — belong in
the driving developer's own tracker instead, which the installed repo's `CLAUDE.md`
describes. Where a GitHub issue carries out a Jira one, it names the `<KEY>-<n>` in its
body rather than a second Jira item.

## A description or comment points only at what its reader can open

A Jira description, a comment or a Confluence page is read by people who do not have this
machine. Never cite a file that lives only here: a note in a gitignored working directory, a
PRD or plan the agent wrote, an absolute path. When the text needs such a file, stop and ask
the user to publish it first (inline in the description, committed to the repo, or a shared
page) and link the published copy.

## Authentication — always the first step

```bash
acli auth status      # before any acli operation
acli auth login       # if it reports not authenticated
```

## Command structure

`acli <product> <entity> <action> [flags]` — products are `auth`, `jira`,
`confluence`, `admin`.

```bash
acli jira workitem search --jql "..."       # ✅ modern syntax
acli jira --action getIssueList --jql "..." # ❌ --action was removed; fails
```

Verify flags against `acli <product> <entity> <action> --help` rather than recalling
them — the `--help` output is the source of truth for a given version.

### Jira entities & actions

| Entity | Common actions | Example |
|--------|---------------|---------|
| `workitem` | search, create, create-bulk, edit, view, transition, assign, delete | `acli jira workitem search --jql "project = TEAM"` |
| `project` | list, view, create, update, delete, archive | `acli jira project list` |
| `sprint` | create, update, view, delete, list-workitems | `acli jira sprint view 123` |
| `board` | search, get, create, delete, list-sprints | `acli jira board list-sprints --board 42` |
| `workitem comment` | create, list, update, delete | `acli jira workitem comment create --key KEY-1 --comment "text"` |

Confluence exposes `space` (list, view, create, update, archive, restore):
`acli confluence space list`.

## Batch operations

Operate on many items in one call — `--jql`, `--filter` (saved-search id), or
`--key` (comma-separated). Add `--yes` to skip confirmation and `--ignore-errors`
to continue past individual failures.

```bash
acli jira workitem edit --jql "project = MOBILE AND status = 'In Review'" --assignee "user@example.com" --yes
acli jira workitem transition --jql "assignee = currentUser() AND status = 'To Do'" --status "In Progress" --yes
acli jira workitem assign --key "KEY-1,KEY-2,KEY-3" --assignee "@me"
```

Verify the target set with `--count` before a bulk `edit`/`transition` — the same
JQL, run read-only first, tells you how many items the write will touch.

## Closing a work item — the status name is not the category

**What closes an item is its `resolution`.** A workflow can name a status "Rejected",
"Won't Fix" or "Cancelled" and still map it to the *In Progress* category with
`resolution = None` — Jira's built-in `Reopened` is exactly this. An item parked there
reads as closed to a human while every query and every release automation counts it as
open assigned work, so nothing ever sweeps it up.

A close that owns its resolution goes over REST: `acli jira workitem transition` takes no
resolution field. `acli`'s own secret lives in the OS keyring and cannot be reused, so each
REST block below opens by sourcing `~/.config/hoopit/jira.env` (`review-jira-attachments` sets it up) and
naming the org's own instance as the host — the one place the token is ever sent.

Read the status's real shape and the transitions off the item itself. **Every one of
these is per-project** — ids, resolution names, which transitions even offer the field —
so read them per item and carry none of it to another project:

```bash
# what the status actually is: category is "new" | "indeterminate" | "done".
# --fields is required: resolution is not in acli's default set, so it reads null without it
acli jira workitem view <KEY> --json --fields status,resolution \
  | jq '.fields | {status: .status.name, category: .status.statusCategory.key, resolution: .resolution.name}'

# the transitions available from here, each with the fields its screen accepts
set -a; . ~/.config/hoopit/jira.env; set +a; JIRA_BASE_URL=https://hoopit.atlassian.net
curl -s -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
  "$JIRA_BASE_URL/rest/api/3/issue/<KEY>/transitions?expand=transitions.fields" \
  | jq '.transitions[] | {id, name, to: .to.name, category: .to.statusCategory.key,
                          resolutions: (.fields.resolution.allowedValues // [] | map(.name))}'
```

Close with a transition whose `to.category` is `done`, and pick the resolution from the
`resolutions` that transition actually offers — matching the **outcome**, so completed
work does not land as declined. A transition listing no `resolution` field takes none in
the request — passing it is what returns 400 — so send the transition alone.

```bash
set -a; . ~/.config/hoopit/jira.env; set +a; JIRA_BASE_URL=https://hoopit.atlassian.net
curl -s --fail-with-body -u "$JIRA_EMAIL:$JIRA_API_TOKEN" -H 'Content-Type: application/json' \
  -X POST "$JIRA_BASE_URL/rest/api/3/issue/<KEY>/transitions" \
  -d '{"transition":{"id":"<close-id>"},"fields":{"resolution":{"name":"<one it offered>"}}}'
```

The close is done when the `view` above reads back category `done` **and** a non-null
`resolution` — the only proof a transition sent without the field was resolved by the
workflow.

## Repairing a status nobody set by hand

A tracker integration moves items on its own. GitHub-for-Jira transitions **every** key it
finds on a pull request — the branch, the commits, the title, the body — not only the one
the PR delivers, and it attributes the move to the **PR author**, so the changelog shows a
human. A merely-mentioned follow-up therefore reads as delivered, and lands somewhere the
release automation's own sweep sits *past*, where it parks indefinitely.

Correlate the changelog timestamps against the PRs that name the key, on **every surface the
integration reads**. Issue search covers the title and body — `--state all`, because the event
that makes a ticket look delivered is the **merge**, and the default listing shows only open
PRs; `--limit`, because the default 30 can drop the one that moved it. Commits and branch names
need their own lookups:

```bash
# title, body
gh pr list --state all --limit 200 --search "<KEY>" --json number,createdAt,mergedAt,headRefName,title
# commit messages → the PRs carrying those commits
gh search commits "<KEY>" --repo <OWNER_REPO> --json sha --jq '.[].sha' \
  | xargs -I{} gh api repos/<OWNER_REPO>/commits/{}/pulls --jq '.[] | "\(.number) \(.head.ref) \(.merged_at)"'
# branch names — page back only as far as the transition's timestamp
gh api "repos/<OWNER_REPO>/pulls?state=all&per_page=100&page=1" \
  --jq '.[] | select(.head.ref | test("<KEY>"; "i")) | "\(.number) \(.head.ref) \(.merged_at)"'
```

A transition within about a minute of a PR event, on a key only *mentioned* rather than
carried on the branch or title, is the integration's. Restore the last **human** status —
which for an investigation ticket may be a rejected state rather than the open one.

Confirm the cause on the PR's surfaces first, because the wrong one costs a second repair:
a transition on a key that appears on **no** surface of the PR is something else, usually
an over-broad bulk `transition --jql`. `create-pull-request` carries the prevention.

## Bulk creation

Bulk is where the gate above matters most: `create-bulk` turns one wrong call into a
queue the team has to clear by hand. Confirm the list, not just the intent.

```bash
acli jira workitem create --generate-json > template.json   # JSON template
acli jira workitem create --from-json workitem.json         # create from JSON
acli jira workitem create-bulk                              # many at once
acli jira workitem create --summary "Bug title" --project API --type Bug --from-file description.txt
```

Reach for `create-bulk` / `--from-json` instead of a bash loop of `create` calls.

## Output formats

```bash
acli jira workitem search --jql "sprint = 42" --csv    # spreadsheets
acli jira workitem search --jql "project = API" --json # scripts
acli jira workitem view KEY-123 --web                  # browser
acli jira workitem search --jql "..." --fields "key,summary,assignee,priority"
```

`--csv` (not `--outputFormat`), `--fields` (not `--columns`), plus `--count` for a
count-only result and `--paginate` to fetch every page.

## Common JQL patterns

```bash
--jql "assignee = currentUser()"
--jql "project = TEAM AND status = 'In Progress'"
--jql "project = API AND type = Bug AND status != Done"
--jql "project = TEAM AND sprint = 42"
--jql "project = WEBAPP AND updated >= -7d"
```
