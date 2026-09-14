# Launcher — Herdr panes

Starts each fan-out session as a Claude agent in a Herdr pane. Read
[`fan-out.md`](fan-out.md) first: it holds the prompt and the session's directory, name,
agent and permissions.

Load the **`herdr`** skill first. The installed binary is the authority on its CLI; the
commands below are the shape of the procedure, and flags are worth confirming against
`herdr workspace`, `herdr tab`, `herdr pane`, and `herdr agent` before you rely on them.

## Layout — each repo's workspace, one tab per issue

Workspaces mirror repos, so each session goes in the workspace for its `<TARGET_REPO>`:
match it by label (the repo's directory name) in `herdr workspace list`, and create it when
none fits — `herdr workspace create --cwd "<TARGET_REPO>" --label "<repo>" --no-focus`.

In that workspace, give the issue its own tab, labelled with the issue key —
`ITSM_ISSUE_KEY` when set, else `TARGET_KEY`:

```bash
herdr tab create --workspace <workspace_id> --label "<issue key>" --cwd "<TARGET_REPO>" --no-focus
```

A tab cannot span workspaces, so a ticket affecting three repos gets one tab, labelled
alike, in each of their three workspaces. Read each id out of the command's JSON rather
than predicting it.

## Start an agent per pane

```bash
herdr agent start "<agent-name>" --kind claude --pane <pane_id> \
  -- -n "fix-<TARGET_KEY>" [--add-dir "<your directory>" --agent "<SESSION_AGENT>"] \
  [--permission-mode bypassPermissions]
```

`<agent-name>` is `fix-<TARGET_KEY>` in lower case — it must match `[a-z][a-z0-9_-]{0,31}`
and be unique among live agents. `agent start` returns once Herdr sees the agent ready; on
`agent_not_ready` the name is still usable — wait for idle before prompting. Then send each
agent its prompt, without `--wait`:

```bash
herdr agent prompt "<agent-name>" "<the prompt>"
```

The session's handle is `<agent-name>`: `herdr agent focus <agent-name>` brings it up.
