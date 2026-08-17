---
name: handle-jira-issue
description: Handle any Jira issue end-to-end — an ITSM ticket or a project issue (BAC/WEB/FA). Fetch details (from the linked ITSM ticket when one exists), link or create a project issue only when needed, then ship the fix (branch, fix, test, review, PR) via implement-and-ship-fix. Use whenever the user links to or names a Jira issue to fix.
---

# Handle Jira Issue Workflow

Triggered when the user says something like "fix this issue" and provides any Jira issue key or link — either an ITSM ticket (e.g. `ITSM-1234`) or a project issue (e.g. `BAC-6934`, `WEB-1234`, `FA-987`), or a full Jira URL (e.g. `https://hoopit.atlassian.net/browse/ITSM-1234`).

This skill owns the Jira-specific work — classify the input, read the report, resolve or create the project issue — then hands off to the **`implement-and-ship-fix`** skill for the generic branch → fix → test → review → PR flow.

## Configuration — read from CLAUDE.md, never hardcode

This skill is project-agnostic. Every Hoopit-specific identifier (Jira keys, the
Jira base URL, the ITSM project key, repo names) comes from the
**`## Agent skills` → `### Workflow skills config`** block in each repo's
`CLAUDE.md`. **Do not hardcode or guess these** — read them from CLAUDE.md. If a
value you need is missing from the relevant repo's CLAUDE.md, **stop and ask the
user to add it** rather than assuming a default.

The repos are sibling directories under a common parent (`HOOPIT_ROOT`); derive
it from the repo this skill is invoked in:

```bash
HOOPIT_ROOT="$(dirname "$(git rev-parse --show-toplevel)")"
```

### Build the Jira-key → repo map dynamically

Do **not** assume a fixed `BAC/WEB/FA` map. For each sibling repo under
`$HOOPIT_ROOT` that has a `CLAUDE.md`, read its declared **Jira project key** from
the Workflow skills config block. That yields the current `Jira key → repo`
mapping, so new projects work without editing this skill:

```bash
# Prints "KEY<TAB>/path/to/repo" for every sibling repo that declares a Jira key.
for repo in "$HOOPIT_ROOT"/*/; do
  cm="$repo/CLAUDE.md"; [ -f "$cm" ] || continue
  key="$(grep -iE '^\s*[-*]\s*\*\*Jira project key:\*\*' "$cm" | grep -oE '`[A-Z][A-Z0-9]+`' | tr -d '`' | head -1)"
  [ -n "$key" ] && printf '%s\t%s\n' "$key" "${repo%/}"
done
```

Call the resulting set of keys the **project keys**; every "is this a project issue?"
test below means "is its prefix one of them?". Wherever the steps show `BAC` / `WEB` /
`FA`, they are examples of that set, never the set itself.

Once you know `TARGET_REPO`, read the rest of its Workflow skills config —
**Jira base URL**, **ITSM project key**, **Default branch** — from that repo's
CLAUDE.md and use them in place of the literals below.

Variables used throughout this skill:
- `TARGET_PROJECT` — the Jira project key the fix is tracked under.
- `TARGET_REPO` — the repo whose CLAUDE.md declares `TARGET_PROJECT`.
- `TARGET_KEY` — the project issue key in `TARGET_PROJECT` (e.g. `BAC-6934`). Becomes the working `JIRA_KEY`.
- `JIRA_BASE_URL` — the Jira base URL from `TARGET_REPO`'s CLAUDE.md (e.g. `https://hoopit.atlassian.net`).
- `ITSM_PROJECT` — the ITSM project key from CLAUDE.md (e.g. `ITSM`); ITSM keys look like `<ITSM_PROJECT>-1234`.
- `DEFAULT_BRANCH` — `TARGET_REPO`'s default branch from CLAUDE.md (e.g. `master`).
- `ITSM_ISSUE_KEY` — the linked ITSM ticket, **if one exists**. May be unset.
- `DETAILS_KEY` — the issue you read the bug report / symptoms / attachments from: the **ITSM ticket when one exists**, otherwise the project issue itself.

> Wherever the steps below show `https://hoopit.atlassian.net`, `ITSM`, or
> `master`, substitute `$JIRA_BASE_URL`, `$ITSM_PROJECT`, and `$DEFAULT_BRANCH`
> from CLAUDE.md.

## Determine the scenario

Before anything else, classify the input issue. If a full Jira URL was provided, extract the issue key from it first, then look at the key's prefix:

### Input is an ITSM ticket (`ITSM-…`) — *ITSM-originated*

- `ITSM_ISSUE_KEY` = the input key.
- `DETAILS_KEY` = `ITSM_ISSUE_KEY`.
- `TARGET_PROJECT` / `TARGET_KEY` are resolved in **Step 2** (an existing linked project issue, or a new one you create).

### Input is a project issue (`BAC-…`, `WEB-…`, `FA-…`) — *project-originated*

- `TARGET_KEY` = the input key; `TARGET_PROJECT` = its prefix; `TARGET_REPO` = the matching repo. **No new project issue will ever be created** — the input issue *is* the target.
- Check whether it links to an ITSM ticket by fetching the `issuelinks` field (see the parsing note in Step 2a — inspect both `inwardIssue.key` and `outwardIssue.key`):

  ```bash
  acli jira workitem view <TARGET_KEY> --fields 'issuelinks' --json
  ```

  - **Linked `ITSM-…` issue found** → set `ITSM_ISSUE_KEY` to it; `DETAILS_KEY` = `ITSM_ISSUE_KEY`. (Read details from the ITSM ticket, not the project issue.)
  - **No ITSM link** → leave `ITSM_ISSUE_KEY` unset; `DETAILS_KEY` = `TARGET_KEY`. (Read details from the project issue itself.)

### How to determine `TARGET_PROJECT` (ITSM-originated only)

For project-originated issues the project is already known from the key prefix. For ITSM-originated issues, resolve the target project as follows:

1. **Existing link wins.** After fetching the ITSM issue, if it already links to an issue whose key prefix is one of the project keys, that is `TARGET_PROJECT` — no question needed.
2. **Fall back to cwd.** Otherwise, default to whichever repo the current working directory sits inside, and read **that** repo's `Jira project key` from its CLAUDE.md Workflow skills config — that is `TARGET_PROJECT`.
3. **Ask if ambiguous.** If neither rule resolves (e.g. cwd is outside all three repos, or the ITSM issue clearly describes a different layer than the cwd suggests), ask the user which project to target before doing anything else.

## Step 1 — Fetch issue details

Always read the bug report and context from `DETAILS_KEY` — i.e. the linked ITSM ticket when one exists, otherwise the project issue itself. When an ITSM ticket is linked, it is the source of truth for the reported symptoms, repro steps, and attachments; do **not** rely on the project issue for those details.

```bash
acli jira workitem view <DETAILS_KEY> --fields '*all'
```

Extract and note:
- **Summary / title**
- **Description and reported symptoms**
- **Affected component or service** (for ITSM-originated issues, often hints which `TARGET_PROJECT` is appropriate)
- **Priority and impact**
- **Reporter and any additional context**
- **Attachments** — note any attached files, especially HAR (`.har`) files, screenshots, or logs

### Review attachments (HAR files, screenshots, logs)

If `DETAILS_KEY` has attachments, **download and analyze them yourself using the
`review-jira-attachments` skill** — don't ask the reporter to describe them. HAR files capture the full
browser network activity at the time of the bug and often reveal the exact request URLs, bodies, and
error responses that reproduce the problem; screenshots pin the affected screen/state.

`acli` cannot download attachments, so that skill uses the Jira REST API (needs `JIRA_API_TOKEN` +
`JIRA_EMAIL`, e.g. `set -a; . ~/.config/hoopit/jira.env; set +a`, with `$JIRA_BASE_URL` from CLAUDE.md).
Pass it `DETAILS_KEY`. Key reminder it enforces: HARs are 5–15 MB — never read one whole; extract just
the failing requests (status `0` or `>= 400`) and inspect those.

Focus on:
- **Failing requests** (non-2xx responses, or responses whose body contains error messages matching the reported symptom)
- **Request URL, method, headers, and body** — especially the payload shape and any serialization quirks
- **Response body** — the error message or unexpected data returned
- **Timing and sequence** — which request fired immediately before the failure

Use the findings to narrow down which endpoint, view, component, or screen is involved before starting the investigation.

If the issue cannot be understood or reproduced from the available information, stop and ask the user for clarification.

## Step 2 — Identify or create the target project issue

How this resolves depends on the scenario from *Determine the scenario*:

- **Project-originated** (input was a `BAC`/`WEB`/`FA` issue): `TARGET_KEY` is the input issue itself. **Do not create or link anything** — skip straight to **Step 3**. (Any linked ITSM ticket was already recorded as `ITSM_ISSUE_KEY`.)
- **ITSM-originated** (input was an `ITSM-…` ticket): follow 2a/2b below.

### 2a — Check for an existing linked target issue

**Do NOT use `acli jira workitem link list`** — it only returns `outwardIssueKey` and silently drops `inwardIssue` data. Target issues are typically linked as inward issues ("ITSM ticket is caused by BAC/WEB/FA bug"), so they will appear missing even when they exist.

Instead, fetch the `issuelinks` field directly and parse the JSON:

```bash
acli jira workitem view <ITSM_ISSUE_KEY> --fields 'issuelinks' --json
```

Inspect **both** `inwardIssue.key` and `outwardIssue.key` across all entries in the `fields.issuelinks` array. Look for any linked issue whose key prefix is one of the project keys.

If such a link exists:
- Set `TARGET_PROJECT` from its prefix and `TARGET_KEY` to that key.
- Skip to **Step 3**.

### 2b — Create a new target issue if none exists

Resolve `TARGET_PROJECT` using the rules in *How to determine `TARGET_PROJECT`* above. Then map the ITSM request type to the destination issue type. The mapping is the same across all three projects:

| ITSM request type | Issue type in `TARGET_PROJECT` |
|-------------------|--------------------------------|
| Problem           | **Bug**                        |
| Feature request   | **Story**                      |
| Anything else     | **Task**                       |

```bash
acli jira workitem create \
  --project "$TARGET_PROJECT" \
  --type '<Bug | Story | Task>' \
  --summary '<concise title>' \
  --description '## Summary
<1-2 sentence description>

## Root cause / background
<technical explanation or context>

## References
- ITSM: [<ITSM_ISSUE_KEY>]($JIRA_BASE_URL/browse/<ITSM_ISSUE_KEY>)'
```

Note the new `TARGET_KEY` printed by the command (e.g. `BAC-6934`, `WEB-1234`, `FA-987`).

Create a **"Problem/Incident"** link from the ITSM ticket to the new issue (i.e. the ITSM issue *is caused by* the target bug).

```bash
acli jira workitem link create \
  --out '<ITSM_ISSUE_KEY>' \
  --in '<TARGET_KEY>' \
  --type 'Problem/Incident' \
  --yes
```

> **Note:** The direction matters — `--out` is the outward issue (the effect: ITSM ticket) and `--in` is the inward issue (the cause: target bug).

`TARGET_KEY` is the `JIRA_KEY` used for the fix.

## Step 3 — Ship the fix

Hand off to the **`implement-and-ship-fix`** skill, which owns the generic
branch → fix → regression test → review gate → push → PR flow (including branch
naming, commit footer, and PR link hygiene). Pass it:

- `TARGET_REPO` — the repo whose CLAUDE.md declares `TARGET_PROJECT`.
- `JIRA_KEY` = `TARGET_KEY`.
- `DETAILS_KEY` — the ITSM ticket when linked, else `TARGET_KEY` (Step 1's source).
- `ITSM_ISSUE_KEY` — set **only when a linked ITSM ticket exists** (drives the
  `Refs <ITSM_ISSUE_KEY>` commit footer and the PR `## ITSM` section); leave unset
  for a project issue with no ITSM link.
- `JIRA_BASE_URL`, `DEFAULT_BRANCH` — from `TARGET_REPO`'s CLAUDE.md.

You've done the Jira-specific work (read the report + attachments in Step 1, resolved
or created `TARGET_KEY` in Step 2); `implement-and-ship-fix` takes it from the branch
through the open PR.
