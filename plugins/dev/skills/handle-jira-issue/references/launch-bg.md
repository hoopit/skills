# Launcher — background sessions

Starts each fan-out session as a `claude --bg` session. Read
[`fan-out.md`](fan-out.md) first: it holds the prompt and the session's directory, name,
agent and permissions.

One command per repo:

```bash
cd "<session dir>" && claude --bg -n "fix-<TARGET_KEY>" \
  [--agent "<SESSION_AGENT>"] [--permission-mode bypassPermissions] "<the prompt>"
```

It returns at once and prints `backgrounded · <id> · fix-<TARGET_KEY>`. The session's
handle is `<id>`: `claude attach <id>` opens it, `claude logs <id>` shows its output, and
`claude agents` lists every session.
