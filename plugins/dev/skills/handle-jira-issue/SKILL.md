---
name: handle-jira-issue
description: Handle any Jira issue end-to-end — an ITSM ticket (single- or multi-project) or a project issue (BAC/WEB/FA). Fetch details (from the linked ITSM ticket when one exists), resolve or create the platform issue in each affected repo, then ship one PR per affected repo via implement-and-ship-fix. Use whenever the user or an automation names a Jira issue to fix.
---

# Handle Jira Issue Workflow

Triggered when the user says something like "fix this issue" and provides any Jira issue key or link — either an ITSM ticket (e.g. `ITSM-1234`) or a project issue (e.g. `BAC-6934`, `WEB-1234`, `FA-987`), or a full Jira URL (e.g. `https://hoopit.atlassian.net/browse/ITSM-1234`).

This skill owns the Jira-specific work — classify the input, read the report, resolve the affected repos, resolve or create each repo's platform issue — then hands off to the **`implement-and-ship-fix`** skill for the generic branch → fix → test → review → PR flow, **once per affected repo**. A project issue targets exactly one repo; an ITSM ticket may be implemented by platform issues in **one or several** projects, which live in separate git repos, and ships one PR per affected repo, each linked back to the same ITSM ticket.

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

For each affected repo, read the rest of its Workflow skills config —
**Jira base URL**, **ITSM project key**, **Default branch** — from that repo's
CLAUDE.md and use them in place of the literals below.

Variables used throughout this skill:
- `ITSM_ISSUE_KEY` — the ITSM ticket, **if one exists**. May be unset.
- `DETAILS_KEY` — the issue you read the bug report / symptoms / attachments from: the **ITSM ticket when one exists**, otherwise the project issue itself.
- `JIRA_BASE_URL` — the Jira base URL from CLAUDE.md (e.g. `https://hoopit.atlassian.net`).
- `ITSM_PROJECT` — the ITSM project key from CLAUDE.md (e.g. `ITSM`); ITSM keys look like `<ITSM_PROJECT>-1234`.
- Per affected repo:
  - `TARGET_PROJECT` — the Jira project key the fix is tracked under.
  - `TARGET_REPO` — the repo whose CLAUDE.md declares `TARGET_PROJECT`.
  - `TARGET_KEY` — the platform issue key in `TARGET_PROJECT` (e.g. `BAC-6934`). Becomes that repo's working `JIRA_KEY`.
  - `DEFAULT_BRANCH` — `TARGET_REPO`'s default branch from CLAUDE.md (e.g. `master`).

> Wherever the steps below show `https://hoopit.atlassian.net`, `ITSM`, or
> `master`, substitute `$JIRA_BASE_URL`, `$ITSM_PROJECT`, and `$DEFAULT_BRANCH`
> from CLAUDE.md.

### Implementation links

An ITSM ticket is *implemented by* the platform issues linked via an
**implementation link**: `Problem/Incident` ("is caused by", for bugs) or
`Handle Service/Change request` ("handles", for change requests). These link-type
names are org-level Jira facts, identical in every project. Merely-associated links
(`relates to`, `duplicates`, `blocks`) do **not** count as implementation links.

### Reading `issuelinks` — the `acli` gotcha

**Do NOT use `acli jira workitem link list`** — it only returns `outwardIssueKey` and
silently drops `inwardIssue` data. Platform issues are typically linked as inward
issues ("ITSM ticket is caused by BAC/WEB/FA bug"), so they will appear missing even
when they exist. Instead, fetch the `issuelinks` field directly and parse the JSON:

```bash
acli jira workitem view <KEY> --fields 'issuelinks' --json
```

Inspect **both** `inwardIssue.key` and `outwardIssue.key` across all entries in the
`fields.issuelinks` array.

## Determine the scenario

Before anything else, classify the input issue. If a full Jira URL was provided, extract the issue key from it first, then look at the key's prefix:

### Input is an ITSM ticket (`ITSM-…`) — *ITSM-originated*

- `ITSM_ISSUE_KEY` = the input key.
- `DETAILS_KEY` = `ITSM_ISSUE_KEY`.
- The affected repos and their `TARGET_KEY`s are resolved in **Step 2** — possibly several (existing linked platform issues, or new ones you create).

### Input is a project issue (`BAC-…`, `WEB-…`, `FA-…`) — *project-originated*

- Exactly one target: `TARGET_KEY` = the input key; `TARGET_PROJECT` = its prefix; `TARGET_REPO` = the matching repo. **No new platform issue will ever be created** — the input issue *is* the target.
- Check whether it links to an ITSM ticket by fetching its `issuelinks` (see *Reading `issuelinks`* above):
  - **Linked `ITSM-…` issue found** → set `ITSM_ISSUE_KEY` to it; `DETAILS_KEY` = `ITSM_ISSUE_KEY`. (Read details from the ITSM ticket, not the project issue.)
  - **No ITSM link** → leave `ITSM_ISSUE_KEY` unset; `DETAILS_KEY` = `TARGET_KEY`. (Read details from the project issue itself.)

## Step 1 — Fetch issue details

Always read the bug report and context from `DETAILS_KEY` — i.e. the linked ITSM ticket when one exists, otherwise the project issue itself. When an ITSM ticket is linked, it is the source of truth for the reported symptoms, repro steps, and attachments; do **not** rely on the project issue for those details.

```bash
acli jira workitem view <DETAILS_KEY> --fields '*all'
```

Extract and note:
- **Summary / title**
- **Description and reported symptoms**
- **Affected component or service** (for ITSM-originated issues, often hints which repos are affected)
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

Use the findings to narrow down which endpoint, view, component, or screen — and therefore which repo(s) — is involved before starting the investigation.

If the issue cannot be understood or reproduced from the available information, stop and return to whoever invoked you: ask the user when working interactively, or report back per the caller's contract when dispatched by an automation (the caller owns the request-info / escalate decision).

## Step 2 — Resolve the affected repos and their platform issues

How this resolves depends on the scenario from *Determine the scenario*:

- **Project-originated**: the single target is already known — one pair, (`TARGET_REPO`, `TARGET_KEY`). **Do not create or link anything** — skip straight to **Step 3**. (Any linked ITSM ticket was already recorded as `ITSM_ISSUE_KEY`.)
- **ITSM-originated**: follow 2a–2c below.

### 2a — Collect the already-linked platform issues

Fetch the ITSM ticket's `issuelinks` (see *Reading `issuelinks`* above). Keep every
entry whose `type.name` is an **implementation link** and whose linked key (either end)
starts with one of the project keys. Each such key's prefix identifies an **affected
repo** and its existing `TARGET_KEY`.

### 2b — Determine any additional affected repos from investigation

The links may be incomplete: a ticket can affect a repo that has no platform issue
yet. Using Step 1 plus a read-only look at the candidate repos, decide the full set of
repos that genuinely need a code change. If exactly one repo is affected and it
already has a linked platform issue, that's your single target. Do **not** invent
work in a repo just because it's linked — an affected repo is one you will actually
change.

If no repo can be determined from the links or the investigation, default to whichever
repo the current working directory sits inside; if the cwd is outside all project repos
too (or clearly describes a different layer than the ticket suggests), stop and return
to whoever invoked you, as in Step 1.

### 2c — Ensure each affected repo has a platform issue

For every affected repo that has **no** linked platform issue, create one and link it
to the ITSM ticket. Map the ITSM request type to the issue type (same across repos):

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

Create a **"Problem/Incident"** link from the ITSM ticket to the new issue (i.e. the ITSM issue *is caused by* the platform bug).

```bash
acli jira workitem link create \
  --out '<ITSM_ISSUE_KEY>' \
  --in '<TARGET_KEY>' \
  --type 'Problem/Incident' \
  --yes
```

> **Note:** The direction matters — `--out` is the outward issue (the effect: ITSM ticket) and `--in` is the inward issue (the cause: platform bug).

After 2a–2c you have a list of **(`TARGET_REPO`, `TARGET_KEY`)** pairs — one per affected repo.

## Step 3 — Ship one fix per affected repo

For **each** (`TARGET_REPO`, `TARGET_KEY`) pair, hand off to the
**`implement-and-ship-fix`** skill, which owns the generic
branch → fix → regression test → review gate → push → PR flow (including branch
naming, commit footer, and PR link hygiene). Pass it:

- `TARGET_REPO` — that repo's sibling directory.
- `JIRA_KEY` = `TARGET_KEY`.
- `DETAILS_KEY` — the ITSM ticket when linked, else `TARGET_KEY` (Step 1's source).
- `ITSM_ISSUE_KEY` — set **only when a linked ITSM ticket exists** (drives the
  `Refs <ITSM_ISSUE_KEY>` commit footer and the PR `## ITSM` section); leave unset
  for a project issue with no ITSM link.
- `JIRA_BASE_URL`, `DEFAULT_BRANCH` — from `TARGET_REPO`'s CLAUDE.md.

Each call produces its own worktree, branch, and PR. When several repos are affected,
handle them **independently and best-effort**: if one repo's fix must stop (per Step 1's
return-to-caller rule), that repo's platform issue is escalated and the others still
ship. Report every repo's outcome (PR url / blocked) back to whoever invoked you.

You've done the Jira-specific work (read the report + attachments in Step 1, resolved
the affected repos and their `TARGET_KEY`s in Step 2); `implement-and-ship-fix` takes
each repo from the branch through the open PR.
