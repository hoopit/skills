# Rounds in a worker

The `--subagent` branch of [SKILL.md](SKILL.md)'s Step 3. `<GATE_SCRIPT>` and
`<SKILL_DIR>` are the paths its Step 1 resolved.

`--subagent`: rounds go to a named worker that is reused while it stays under 100k
tokens. First round (and first round after each rotation):

```
Agent(
  subagent_type: "hoopit-dev:monitor-pr-worker",
  model: "<--subagent's model, else opus>",
  name: "pr-<PR>-worker",
  description: "round PR #<PR>",
  prompt: "PR_URL=<PR_URL> OWNER_REPO=<OWNER_REPO> PR=<PR> REPO_ROOT=<REPO_ROOT> LEDGER=<SKILL_DIR>/LEDGER.md PR_STATE=<SKILL_DIR>/scripts/pr-state.sh PR_LABELS=<SKILL_DIR>/scripts/pr-labels.sh GH_PR_API=<SKILL_DIR>/scripts/gh-pr-api.sh GATE_SCRIPT=<GATE_SCRIPT>\nROUND: <the ROUND line verbatim>\nANSWERED: <every fork the user has settled, and the choice>\nGUIDANCE: <this session's scope and facts for the round> | none",
)
```

`ANSWERED` goes on **both** prompts. A fresh worker knows nothing the last one was told,
so a re-arm after a hard fork, or a rotation, would otherwise drop the very answer that
unblocked the watch. Carry every answer the PR has collected, not only the newest. A
re-arm from a fresh session recovers them from the ledger's `answered:` rows.

`GUIDANCE` is this session's own direction for the round, kept apart from `ANSWERED` so
the worker can tell a user's decision from a session's opinion. It carries scope — apply
minimally, no migration, file rather than fold — facts the worker cannot see, and a
demand for a step back on a mechanism the ledger shows patched before. A choice between
two remedies a reviewer offered travels the other way: the worker's design check probes
it and this session answers it, below.

Each completion notification reports `subagent_tokens`; keep a running total per worker.
Next round while the total is under 100k:

```
SendMessage(to: "pr-<PR>-worker", message: "ROUND: <the ROUND line verbatim>\nANSWERED: <each fork the user settled since the last round, and the choice>\nGUIDANCE: <this round's direction> | none")
```

The worker already holds the earlier answers, so this one carries only what is new.

**A design check.** A worker turn ending in `DESIGN CHECK` is a round paused before its
push, not a report: a fix tripped the worker briefing's step back, and the worker has
probed the shapes and put them to Codex's adversarial review. Answer it yourself, at
once, with the brief and the ledger in hand — the decision is this session's, not the
user's, and nothing waits on it:

```
SendMessage(to: "pr-<PR>-worker", message: "DESIGN: push | reshape to <n> — <why>")
```

Choose among the shapes the worker probed; a shape nobody probed is one more probe to ask
for, not an answer. A `Challenge: unavailable` line means the pick was never argued with,
only probed — weigh it as the thinner evidence it is, and reshape on your own read rather
than reading `push` out of a challenge that raised nothing.

The worker's worktree is the worker's: verify its work by reading it — an edit of yours
between its commits is a change it did not make and cannot explain.

At 100k or above, rotate: spawn a fresh worker with the full prompt (use a new name,
e.g. `pr-<PR>-worker-2`) and start its total at zero.
