# Fan out — one session per affected repo

Reached from Step 3 when **two or more** repos are affected and you are running inside
Herdr (`HERDR_ENV=1`). Each affected repo gets its own primary Claude session, sitting in
that repo, running `ship` on that repo's dispatch brief. You dispatch them and return —
you do not wait, and you do not ship any repo yourself.

Load the **`herdr`** skill first. The installed binary is the authority on its CLI; the
commands below are the shape of the procedure, and flags are worth confirming against
`herdr tab`, `herdr pane`, and `herdr agent` before you rely on them.

## Layout — one tab per issue, one pane per repo

The tab is labelled with the issue key and lives in the **current workspace**: the batch
spans repos, so no single repo's workspace fits it. Your own pane stays where it is.

```bash
# First repo: a new tab, already sitting in that repo.
herdr tab create --label "$ITSM_ISSUE_KEY" --cwd "$TARGET_REPO_1" --no-focus

# Each remaining repo: a pane beside it, in that repo.
herdr pane split <pane_id> --direction right --cwd "$TARGET_REPO_N" --no-focus
```

Read the pane id out of each command's JSON rather than predicting it. Hoopit has three
project repos, so this tops out at three panes.

## Start an agent per pane

```bash
herdr agent start "<agent-name>" --kind claude --pane <pane_id> \
  -- -n "<display>" --permission-mode bypassPermissions
```

- `<agent-name>` matches `[a-z][a-z0-9_-]{0,31}` and is unique among live agents —
  `itsm-1234-api`, `itsm-1234-web-admin`.
- `<display>` pins the terminal title to something you can find: `ITSM-1234 api`.
- `bypassPermissions` keeps a run from stalling on a prompt at a pane nobody is watching.
  Drop it when the human wants to approve each outward action instead.

`agent start` returns once Herdr sees the agent ready. On `agent_not_ready` the name is
still usable — wait for idle before prompting.

## Prompt each agent with its dispatch brief

One prompt per agent, sent without `--wait`:

```bash
herdr agent prompt "<agent-name>" "<the prompt below>"
```

The prompt names `ship` directly. It must **not** name this skill: a fresh session running
`handle-jira-issue` would re-resolve the affected repos and fan out again.

> Ship `<TARGET_KEY>` in this repo with the **`ship`** skill. This repo is yours alone —
> the other repos this ticket affects have their own sessions; don't touch them, and don't
> run `handle-jira-issue`.
>
> - **WORK_ITEM:** `<TARGET_KEY>` — `<JIRA_BASE_URL>/browse/<TARGET_KEY>`, tracked in Jira.
> - **BRIEF:** `<the symptoms, in a paragraph>`. Read the full report on `<DETAILS_KEY>` —
>   `<JIRA_BASE_URL>/browse/<DETAILS_KEY>`; its attachments showed `<what you found in
>   Step 1, or "nothing that narrows this further">`.
> - Commit footer `Refs <ITSM_ISSUE_KEY>`, and an `## ITSM` PR section linking that ticket.

Carry over what Step 1 cost you to learn — the HAR's failing request, the screenshot's
screen — so each session doesn't re-download the attachments. Leave the code investigation
to it: that is `ship`'s Step 1, in the repo it owns.

## Record the dispatch, then return

The tabs outlive this session; a comment on the ticket outlives the tabs.

```bash
acli jira workitem comment create --key "$ITSM_ISSUE_KEY" --body '🤖 Dispatched one session per affected repo:

- <TARGET_KEY> — <repo>
- <TARGET_KEY2> — <repo2>'
```

Then report, and stop: repo → agent name → pane. Each session arms its own `monitor-pr`
watch when its PR opens, so nothing here needs waiting on. A repo whose pane or agent
failed to start is **handed back**, not shipped from this session — say so in the report
alongside the ones that went out.
