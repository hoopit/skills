# Unattended: act, then ask

The `--unattended` branch of [SKILL.md](SKILL.md)'s Step 5; steps and paths named here
are that file's.

Under `--unattended` a question waits for someone who may never come, so every
**reversible** choice takes your own recommendation. Two kinds stay questions, asked as
Step 5 says:

- **an irreversible move** — deleting work that exists nowhere else, and the merge, which
  a `GREEN` recommending it puts without the ping (below);
- **a decision you doubt** — a hard fork, a stop, the cap, and any recommendation you
  hold without the evidence to defend it to a reviewer.

A soft fork is reversible: its ledger row reads `decided unattended: <the choice>`, and
the round's push carries it.

A `GREEN` that recommends merging ends on the merge briefing, in chat and in the PR
description, with no `AskUserQuestion`: the ready PR is the question, and merging from
GitHub is its answer. A `GREEN` that recommends holding is a decision you doubt, and asks.

That turn may be the session's last, so leave nothing running when it closes: end the
watch as Step 4 does — `TaskStop` the monitor, drop the labels — and `TaskStop` everything
else this session started that is still alive: the `pr-<PR>-worker` agent, any
backgrounded command. Run Step 4a's left-open sweep now, filing as it says. Then close the turn on a **debrief**, after the briefing: everything
relevant the briefing leaves out, each recommendation still outstanding, and what
Step 4a would still do on a merge — commits to push, the clean-up. The user reads it to
choose between waking the session on merge and closing it; woken, run Step 4a.

Every other ending fires its `AskUserQuestion` — it is the only thing that reaches a user
who does come back. Either ending opens with **what was done**: each decision taken with its ledger
row, each issue filed with its number, each clean-up run, so the user can reverse any of
them. Done when closing the session would lose nothing: every decision is on the
ledger, every finding is on the tracker, and what is left in the question is only what
the user alone can settle.
