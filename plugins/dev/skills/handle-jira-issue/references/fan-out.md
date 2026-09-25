# Fan out — one session per affected repo

Reached from Step 3. Each affected repo gets its own primary Claude session running `ship`
on that repo's dispatch brief. You dispatch them and return — you do not wait, and you do
not ship any repo yourself. Each session arms its own `monitor-pr` watch when its PR opens
and stays with it to the merge.

Write the prompt below once per repo, start each session with the launcher Step 3 picked,
then record the dispatch.

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

## Where each session starts

- **Directory** — `<TARGET_REPO>`, the repo the session ships in, so it picks up that repo's
  `AGENTS.md`, settings and skills.
- **Name** — `fix-<TARGET_KEY>`.
- **Agent** — only under `--session-agent`: `--add-dir "<your directory>" --agent
  <SESSION_AGENT>`. The agent is defined in your directory, and `--add-dir` is what lets a
  session started elsewhere find it.
- **Permissions** — `--permission-mode bypassPermissions` under `--unattended`, so the run
  never stalls on a prompt nobody will answer. Interactively, leave it off unless the user
  asks for it: a prompt then waits for them.

## Record the dispatch, then return

When `ITSM_ISSUE_KEY` is set, comment on it — the sessions outlive this one, and the
comment outlives the sessions:

```bash
acli jira workitem comment create --key "$ITSM_ISSUE_KEY" --body '🤖 Dispatched one session per affected repo:

- <TARGET_KEY> — <repo>
- <TARGET_KEY2> — <repo2>'
```

Then report, and stop: repo → session, with the handle the launcher gave you. A repo whose
session failed to start is **handed back**, not shipped from this session — say so in the
report alongside the ones that went out.
