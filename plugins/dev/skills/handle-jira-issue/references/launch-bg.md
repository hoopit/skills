# Launcher — background sessions

Starts each fan-out session as a `claude --bg` session. Read
[`fan-out.md`](fan-out.md) first: it holds the prompt and the session's directory, name,
agent and permissions.

One command per repo:

```bash
cd "<TARGET_REPO>" && claude --bg -n "fix-<TARGET_KEY>" \
  [--add-dir "<your directory>" --agent "<SESSION_AGENT>"] \
  [--permission-mode bypassPermissions] "<the prompt>"
```

It returns at once and prints `backgrounded · <id> · fix-<TARGET_KEY>`. A `warning: no agent
named '<SESSION_AGENT>'` line comes from a pre-check that ignores `--add-dir`; the session
itself still runs as the agent.

The session's handle is `<id>`: `claude attach <id>` opens it, `claude logs <id>` shows its
output, and `claude agents` lists every session.
