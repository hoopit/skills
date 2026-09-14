# Fan out — one session per affected repo

Reached from Step 3. Each affected repo gets its own primary Claude session running `ship`
on that repo's dispatch brief. You dispatch them and return — you do not wait, and you do
not ship any repo yourself.

Step 3's table picks the lane: **background sessions** or **Herdr panes**. Both send the
same prompt and end on the same record.

## The prompt

The prompt names `ship` directly. It must **not** name this skill: a fresh session running
`handle-jira-issue` would re-resolve the affected repos and fan out again. Under
`--unattended`, write `ship --unattended` where it says `ship`.

> Ship `<TARGET_KEY>` in `<TARGET_REPO>` with the **`ship`** skill. That repo is yours
> alone — the other repos this ticket affects have their own sessions; don't touch them,
> and don't run `handle-jira-issue`.
>
> - **WORK_ITEM:** `<TARGET_KEY>` — `<JIRA_BASE_URL>/browse/<TARGET_KEY>`, tracked in Jira.
> - **BRIEF:** `<the symptoms, in a paragraph>`. Read the full report on `<DETAILS_KEY>` —
>   `<JIRA_BASE_URL>/browse/<DETAILS_KEY>`; its attachments showed `<what you found in
>   Step 1, or "nothing that narrows this further">`.
> - Commit footer `Refs <ITSM_ISSUE_KEY>`, and an `## ITSM` PR section linking that ticket.
>   *(Only when `ITSM_ISSUE_KEY` is set.)*

Carry over what Step 1 cost you to learn — the HAR's failing request, the screenshot's
screen — so each session doesn't re-download the attachments. Leave the code investigation
to it: that is `ship`'s Step 1, in the repo it owns.

## Lane: background sessions

One `claude --bg` per repo:

```bash
cd "<session dir>" && claude --bg -n "fix-<TARGET_KEY>" \
  [--agent "<SESSION_AGENT>"] [--permission-mode bypassPermissions] "<the prompt>"
```

- `<session dir>` — the directory you run from under `--session-agent`, where that agent is
  defined; otherwise `<TARGET_REPO>`.
- `--agent` — only under `--session-agent`.
- `--permission-mode bypassPermissions` — only under `--unattended`, so the run never
  stalls on a prompt nobody will answer. Interactively, leave it off: the session takes
  your default mode, and a prompt waits until the user runs `claude attach`.

The command returns at once and prints `backgrounded · <id> · <name>`. Keep `<id>` — it is
what `claude attach`, `claude logs` and `claude stop` take.

## Lane: Herdr panes

Load the **`herdr`** skill first. The installed binary is the authority on its CLI; the
commands below are the shape of the procedure, and flags are worth confirming against
`herdr tab`, `herdr pane`, and `herdr agent` before you rely on them.

The tab is labelled with the issue key and lives in the **current workspace**: the batch
spans repos, so no single repo's workspace fits it. Your own pane stays where it is.

```bash
# First repo: a new tab, already sitting in that repo.
herdr tab create --label "$ITSM_ISSUE_KEY" --cwd "$TARGET_REPO_1" --no-focus

# Each remaining repo: a pane beside it, in that repo.
herdr pane split <pane_id> --direction right --cwd "$TARGET_REPO_N" --no-focus
```

Read the pane id out of each command's JSON rather than predicting it. Hoopit has three
project repos, so this tops out at three panes. Start an agent per pane:

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
still usable — wait for idle before prompting. Then send each agent its prompt, without
`--wait`:

```bash
herdr agent prompt "<agent-name>" "<the prompt>"
```

## Record the dispatch, then return

When `ITSM_ISSUE_KEY` is set, comment on it — the sessions outlive this one, and the
comment outlives the sessions:

```bash
acli jira workitem comment create --key "$ITSM_ISSUE_KEY" --body '🤖 Dispatched one session per affected repo:

- <TARGET_KEY> — <repo>
- <TARGET_KEY2> — <repo2>'
```

Then report, and stop: repo → session (`<id>` and name, or agent name and pane). Each
session arms its own `monitor-pr` watch when its PR opens, so nothing here needs waiting
on. A repo whose session failed to start is **handed back**, not shipped from this
session — say so in the report alongside the ones that went out.
