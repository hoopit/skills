# Unattended: act, then ask

The `--unattended` branch of [SKILL.md](SKILL.md)'s Step 5; steps and paths named here
are that file's.

Under `--unattended` a question waits for someone who may never come, so every
**reversible** choice takes your own recommendation. Two kinds stay questions, asked as
Step 5 says:

- **an irreversible move** — deleting work that exists nowhere else, a run owed before
  merge ([GREEN.md](GREEN.md)), and the merge;
- **a decision you doubt** — a hard fork, a stop, a checkpoint that stops, and any recommendation you
  hold without the evidence to defend it to a reviewer.

A soft fork is reversible: its ledger row reads `decided unattended: <the choice>`, and
the round's push carries it.

A `GREEN` asks the Green question whichever way it recommends: the merge is irreversible,
and the question is what raises the alert for a user who comes back. Run Step 4a's
left-open sweep first, filing as it says, and put a **debrief** in the chat after the
briefing, before the question: everything relevant the briefing leaves out, each
recommendation still outstanding, and what Step 4a would still do on a merge — commits to
push, the clean-up.

Every ending fires its `AskUserQuestion` — it is the only thing that reaches a user who
does come back — and opens with **what was done**: each decision taken with its ledger
row, each issue filed with its number, each clean-up run, so the user can reverse any of
them. Done when closing the session would lose nothing: every decision is on the
ledger, every finding is on the tracker, and what is left in the question is only what
the user alone can settle.
