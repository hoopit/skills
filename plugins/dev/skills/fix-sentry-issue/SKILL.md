---
name: fix-sentry-issue
description: Fix a Sentry issue end-to-end — fetch details, create or link a Jira ticket (with a native bidirectional Sentry↔Jira link), then ship the fix (branch, fix, test, review, PR) via implement-and-ship-fix. Use when the user links to a sentry issue.
---

# Fix Sentry Issue Workflow

Triggered when the user says something like "fix this sentry issue" and provides a Sentry URL or issue ID (e.g. `BAC-QCB` or `https://hoopit.sentry.io/issues/...`).

This skill owns the Sentry-specific work — fetch the issue, create or link a Jira ticket with a native two-way link — then hands off to the **`implement-and-ship-fix`** skill for the generic branch → fix → test → review → PR flow.

## Configuration — read from CLAUDE.md, never hardcode

This skill is project-agnostic. Run it from inside the affected repo, then read
its **`## Agent skills` → `### Workflow skills config`** block in `CLAUDE.md` and
use those values throughout — **do not hardcode or guess them**. If a value you
need is missing (or marked TODO), **stop and ask the user to add it** to CLAUDE.md.

- `JIRA_PROJECT` — the repo's **Jira project key** (e.g. `BAC`).
- `JIRA_BASE_URL` — the **Jira base URL** (e.g. `https://hoopit.atlassian.net`).
- `SENTRY_ORG` — the **Sentry org** (e.g. `hoopit`).
- `SENTRY_PROJECT` — the **Sentry project** slug.
- `DEFAULT_BRANCH` — the repo's **default branch** (e.g. `master`).
- `SENTRY_JIRA_INTEGRATION_ID` — the numeric id of the Sentry↔Jira integration, used to create the native two-way issue link (e.g. `12493`). If it's missing from CLAUDE.md, derive it once with the command in Step 2c and add it.

Wherever the steps below show `BAC`, `hoopit`, `https://hoopit.atlassian.net`, or
`master`, substitute `$JIRA_PROJECT`, `$SENTRY_ORG`, `$JIRA_BASE_URL`, and
`$DEFAULT_BRANCH`. Resolve the repo from where you are invoked (cwd) and its
CLAUDE.md — not from the Sentry ID prefix.

## Step 1 — Fetch Sentry issue details

Load the `sentry-cli` skill for full guidance on the `sentry` CLI before running any commands.

Use the `sentry` CLI to get full issue details. If a full Sentry URL is provided, extract the short issue ID from it (e.g. `BAC-QCB` from `https://hoopit.sentry.io/issues/BAC-QCB/...`).

```bash
sentry issue view <SENTRY_ID> --json
```

If the CLI cannot auto-detect the org, prefix the issue ID with the org slug (`$SENTRY_ORG` from CLAUDE.md):

```bash
sentry issue view $SENTRY_ORG/<SENTRY_ID> --json
```

For a recent event with stacktrace and request context, also fetch one event:

```bash
sentry issue events <SENTRY_ID> --limit 1 --json
sentry event view <EVENT_ID> --json   # if more detail is needed
```

Optionally, get an AI root-cause analysis to seed the fix:

```bash
sentry issue explain <SENTRY_ID>
```

Extract and note:
- **Sentry Issue ID** (e.g. `BAC-QCB`) — used in the commit footer
- **Numeric Sentry group ID** — the `id` field in the JSON (e.g. `7271613592`); required for the native Jira link in Step 2c. This is **not** the short ID.
- **Error type and message**
- **Most relevant stack frame** — file, line number
- **Full stacktrace**
- **HTTP request context** (method, URL, payload)
- **Occurrence count and user impact**

If the issue cannot be understood or reproduced from the available information, stop and ask the user for clarification.

## Step 2 — Identify or create a Jira issue

### 2a — Check for an existing linked Jira issue

> **Note:** The `sentry` CLI does **not** expose Jira-linked issues — even if a Jira link is visible in the Sentry UI, it won't appear in `sentry issue view` output. Instead, search Jira directly using the Sentry issue ID as a text match (it will appear in issue descriptions or comments that were linked via the workflow):

```bash
acli jira workitem search \
  --jql "project = $JIRA_PROJECT AND text ~ \"<SENTRY_ID>\" ORDER BY created DESC" \
  --limit 5 \
  --fields 'key,summary,status'
```

If that returns nothing, also try a summary keyword search:

```bash
acli jira workitem search \
  --jql "project = $JIRA_PROJECT AND summary ~ \"<short error description>\" AND resolution = Unresolved ORDER BY created DESC" \
  --limit 5 \
  --fields 'key,summary,status'
```

If a matching unresolved issue already exists, use it — note its key (e.g. `BAC-6932`).

### 2b — Create a new Jira issue if none exists

The issue type must be **Bug**.

```bash
acli jira workitem create \
  --project "$JIRA_PROJECT" \
  --type Bug \
  --summary '<concise bug title>' \
  --description '## Summary
<1-2 sentence description of the bug>

## Root cause
<technical explanation>

## References
- Sentry: [<SENTRY_ID>](<SENTRY_URL>)
- First seen: <date>, Occurrences: <N>, Users impacted: <N>'
```

Note the new Jira issue key printed by the command (e.g. `BAC-6934`).

### 2c — Create the bidirectional Sentry↔Jira link

Create the **native** two-way integration link — the same one as the Sentry UI's "Link Jira Issue", not a
plain text reference. With Sentry's Jira integration `issue-sync` enabled this is bidirectional: the Sentry
issue shows the linked Jira issue and the Jira issue shows the Sentry one, and status/assignee sync across.
Use the **numeric group ID** from Step 1 (not the short ID) and `SENTRY_JIRA_INTEGRATION_ID` from CLAUDE.md:

```bash
sentry api groups/<NUMERIC_ID>/integrations/$SENTRY_JIRA_INTEGRATION_ID/ -X PUT -d '{"externalIssue":"<JIRA_KEY>"}'
```

The response echoes the linked issue (key + url) on success. (Preview the resolved request without sending
it with `-n`/`--dry-run`.) This works the same whether `<JIRA_KEY>` was just created (2b) or an existing
issue found in 2a.

If `SENTRY_JIRA_INTEGRATION_ID` is not yet in CLAUDE.md, derive it once (then add it to the config block):

```bash
sentry api "organizations/$SENTRY_ORG/integrations/?provider_key=jira"   # use the integration "id" field
```

**Fallback:** a plain text reference does **not** create the native link — only the `groups/.../integrations/...`
PUT does. If that call fails (wrong integration id, missing scope, etc.), don't lose the trail — add a
cross-reference comment instead and tell the user the native link degraded:

```bash
acli jira workitem comment create \
  --key '<JIRA_KEY>' \
  --body '🔗 **Sentry Issue:** [<SENTRY_ID>](<SENTRY_URL>)

- **Occurrences:** N
- **Users impacted:** N'
```

## Step 3 — Ship the fix

Hand off to the **`implement-and-ship-fix`** skill, which owns the generic
branch → fix → regression test → review gate → push → PR flow (including branch
naming, commit footer, and PR link hygiene). Pass it:

- `TARGET_REPO` — the repo you were invoked in (resolved from cwd + its CLAUDE.md).
- `JIRA_KEY` — the Jira issue from Step 2.
- `DETAILS_KEY` — the Sentry issue (Step 1's source of the error, stacktrace, and event context).
- `SENTRY_ID` — the short id (e.g. `BAC-QCB`), and `SENTRY_URL` — its Sentry issue URL.
  These drive the `Fixes <SENTRY_ID>` commit footer and the PR `## Sentry` section.
- `JIRA_BASE_URL`, `DEFAULT_BRANCH` — from `TARGET_REPO`'s CLAUDE.md.

You've done the Sentry-specific work (fetched the issue + event in Step 1, created or
linked the Jira issue and its native Sentry↔Jira link in Step 2);
`implement-and-ship-fix` takes it from the branch through the open PR.
