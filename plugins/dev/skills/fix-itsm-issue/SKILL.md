---
name: fix-itsm-issue
description: Fix an ITSM ticket end-to-end across every project it affects — read the ticket + attachments, resolve or create the linked platform issue in each affected repo, then ship one PR per repo via implement-and-ship-fix. Use when given an ITSM ticket key to fix (single- or multi-project).
---

# Fix ITSM Issue Workflow

Triggered by an ITSM ticket key (e.g. `ITSM-1234`) — the reporter-facing service-desk
ticket. An ITSM ticket may be implemented by platform issues in **one or several**
projects (BAC / WEB / FA), which live in **separate git repos**. This skill reads the
ticket, works out which repos it affects, and ships **one PR per affected repo** — each
in its own worktree, each linked back to the same ITSM ticket. The generic
branch→fix→test→review→PR mechanics for each repo live in `implement-and-ship-fix`;
this skill owns only the ITSM-specific parts (steps 1–2) and the per-repo fan-out.

## Configuration — read from config / CLAUDE.md, never hardcode

Every identifier comes from the central triage config
(`<triage-repo>/.claude/triage-config.json`) and each repo's `CLAUDE.md` — do not
hardcode or guess. Values used here:

- `ITSM_ISSUE_KEY` — the input ticket. `DETAILS_KEY` = `ITSM_ISSUE_KEY` throughout
  (the ITSM ticket is the source of truth for symptoms, repro, attachments).
- `implementation_link_types`, `projects.*.jira_project`, `jira_base_url` — from the
  triage config.
- Per repo: `JIRA_BASE_URL`, `DEFAULT_BRANCH` — from that repo's `CLAUDE.md`.

The repos are siblings under a common parent:
`HOOPIT_ROOT="$(dirname "$(git rev-parse --show-toplevel)")"`, and each project key
in the config (`api` / `web-admin` / `flutter-app`) is the sibling directory name.

## Step 1 — Read the ITSM ticket

```bash
acli jira workitem view <ITSM_ISSUE_KEY> --fields '*all'
```

Extract summary, description/symptoms, affected component/service, priority, reporter,
and any attachments. If attachments exist (HAR, screenshots, logs), **download and
analyse them yourself** with the `review-jira-attachments` skill — don't ask the
reporter to describe them. HARs are 5–15 MB; never read one whole — extract the
failing requests (status `0` or `>= 400`) and inspect those. Use the findings to
narrow which endpoint / screen / component (and therefore which repo) is involved.

If the ticket cannot be understood or reproduced from what's available, stop and hand
back to the caller (the implementer contract owns request-info / escalate).

## Step 2 — Resolve the affected repos and their platform issues

An ITSM ticket is implemented by the platform issues linked via an
`implementation_link_types` link — `Problem/Incident` ("is caused by", for bugs) or
`Handle Service/Change request` ("handles", for change requests). Merely-associated
links (`relates to`, `duplicates`, `blocks`) do **not** count.

### 2a — Collect the already-linked platform issues

**Do NOT use `acli jira workitem link list`** — it drops inward issues. Fetch the raw
links and parse both ends:

```bash
acli jira workitem view <ITSM_ISSUE_KEY> --fields 'issuelinks' --json
```

From `fields.issuelinks`, keep every entry whose `type.name` is an
`implementation_link_types` value and whose linked key (`inwardIssue.key` **or**
`outwardIssue.key`) starts with a configured platform project key (`BAC` / `WEB` /
`FA`). This is exactly what `_triage_common/jira_links.py`'s
`implementation_links_from_issuelinks(issuelinks, config)` computes — use it if
running from Python. Each such key's prefix identifies an **affected repo**.

### 2b — Determine any additional affected repos from investigation

The links may be incomplete: a ticket can affect a repo that has no platform issue
yet. Using Step 1 plus a read-only look at the candidate repos, decide the full set of
repos that genuinely need a code change. If exactly one repo is affected and it
already has a linked platform issue, that's your single target. Do **not** invent
work in a repo just because it's linked — an affected repo is one you will actually
change.

### 2c — Ensure each affected repo has a platform issue

For every affected repo that has **no** linked platform issue, create one and link it
to the ITSM ticket. Map the ITSM request type to the issue type (same across repos):

| ITSM request type | Issue type    |
|-------------------|---------------|
| Problem           | **Bug**       |
| Feature request   | **Story**     |
| Anything else     | **Task**      |

```bash
acli jira workitem create \
  --project "<that repo's jira_project>" \
  --type '<Bug | Story | Task>' \
  --summary '<concise title>' \
  --description '## Summary
<1-2 sentence description>

## Root cause / background
<technical explanation>

## References
- ITSM: [<ITSM_ISSUE_KEY>](<JIRA_BASE_URL>/browse/<ITSM_ISSUE_KEY>)'

# Link it: ITSM ticket *is caused by* the platform issue (--out = effect, --in = cause)
acli jira workitem link create \
  --out '<ITSM_ISSUE_KEY>' --in '<NEW_TARGET_KEY>' --type 'Problem/Incident' --yes
```

After 2a–2c you have a list of **(repo, TARGET_KEY)** pairs — one per affected repo.

## Step 3 — Ship one fix per affected repo

For **each** (repo, `TARGET_KEY`) pair, invoke `implement-and-ship-fix` with:

- `TARGET_REPO` = that repo's sibling directory,
- `JIRA_KEY` = `TARGET_KEY`,
- `DETAILS_KEY` = `ITSM_ISSUE_KEY`,
- `ITSM_ISSUE_KEY` = `ITSM_ISSUE_KEY` (drives the `Refs` footer + PR `## ITSM` section),
- `JIRA_BASE_URL` / `DEFAULT_BRANCH` from that repo's `CLAUDE.md`.

Each call produces its own worktree, branch, and PR. Handle the repos **independently
and best-effort**: if one repo's fix must escalate (per the caller's contract), that
repo's platform issue is escalated and the others still ship. Report every repo's
outcome (PR url / blocked / archived) back to the caller for the aggregated RESULT.
