---
name: atlassian-cli
description: Use when working with Jira or Confluence from command line, including authentication, searching issues with JQL, bulk operations, sprint reports, or creating/updating work items using acli
---

# Atlassian CLI (acli)

Command-line access to Jira and Confluence. Check auth first, use the modern command
structure, and reach for batch operations over loops.

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

## Bulk creation

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
