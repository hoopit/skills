# Launcher — Herdr panes

Starts each fan-out session as a Claude agent in a Herdr pane. Read
[`fan-out.md`](fan-out.md) first: it holds the prompt and the session's directory, name,
agent and permissions.

Load the **`herdr`** skill first. The installed binary is the authority on its CLI; the
commands below are the shape of the procedure, and flags are worth confirming against
`herdr workspace`, `herdr tab`, `herdr pane`, and `herdr agent` before you rely on them.

## Layout — one tab per issue, one pane per repo

The tab is labelled with the issue key — `ITSM_ISSUE_KEY` when set, else `TARGET_KEY`.
Place it in the workspace for the repo the sessions start in:

- **Under `--session-agent`** — every session starts in your directory, so the tab goes in
  that repo's workspace (`herdr workspace list`, matched by label). Create it when none
  fits: `herdr workspace create --cwd "<session dir>" --label "<repo>" --no-focus`.
- **Otherwise** — the sessions start in different repos, so no single repo's workspace
  fits the batch: use the current workspace.

```bash
# First repo: a new tab.
herdr tab create --workspace <workspace_id> --label "<issue key>" --cwd "<session dir>" --no-focus

# Each remaining repo: a pane beside it.
herdr pane split <pane_id> --direction right --cwd "<session dir>" --no-focus
```

Read each id out of the command's JSON rather than predicting it. Hoopit has three project
repos, so this tops out at three panes.

## Start an agent per pane

```bash
herdr agent start "<agent-name>" --kind claude --pane <pane_id> \
  -- -n "fix-<TARGET_KEY>" [--agent "<SESSION_AGENT>"] [--permission-mode bypassPermissions]
```

`<agent-name>` is `fix-<TARGET_KEY>` in lower case — it must match `[a-z][a-z0-9_-]{0,31}`
and be unique among live agents. `agent start` returns once Herdr sees the agent ready; on
`agent_not_ready` the name is still usable — wait for idle before prompting. Then send each
agent its prompt, without `--wait`:

```bash
herdr agent prompt "<agent-name>" "<the prompt>"
```

The session's handle is `<agent-name>`: `herdr agent focus <agent-name>` brings it up.
