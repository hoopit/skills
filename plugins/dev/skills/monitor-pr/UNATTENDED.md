# Unattended: act, then ask

The `--unattended` branch of [SKILL.md](SKILL.md)'s Step 5; steps and paths named here
are that file's.

Under `--unattended` a question waits for someone who may never come, so every
**reversible** choice takes your own recommendation. A soft fork is reversible: its ledger
row reads `decided unattended: <the choice>`, and the round's push carries it. Two kinds
stay questions, asked as Step 5 says:

- **an irreversible move** — deleting work that exists nowhere else, a run owed before
  merge ([GREEN.md](GREEN.md)), and the merge, so every `GREEN` asks;
- **a decision you doubt** — a hard fork, a stop, a checkpoint that stops, and any
  recommendation you hold without the evidence to defend it to a reviewer.

## The ending

Every ending closes on its `AskUserQuestion`, exactly as attended: the alert is the only
thing that reaches a user who comes back. The chat above it opens with **what was done** —
each decision taken with its ledger row, each issue filed with its number, each clean-up
run — so the user can reverse any of them.

A `GREEN` first runs Step 4a's left-open sweep, filing as it says, and puts a **debrief**
after the briefing: everything relevant the briefing leaves out, each recommendation still
outstanding, and what Step 4a would still do on a merge — commits to push, the clean-up.

Done when closing the session would lose nothing: every decision is on the ledger, every
finding is on the tracker, and the question holds only what the user alone can settle.
