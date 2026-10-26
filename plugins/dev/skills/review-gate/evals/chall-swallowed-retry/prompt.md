---
max_turns: 60
timeout_seconds: 1800
tags: [defect]
expect_change: chall-space-403
expect_branch: BAC-4420-chall-space-403
expect_codex: ran
expect_defect: 'delete_space\(chall_space_id\)\s*\n\s*except\s+\(?\s*(ChallError|Exception)\b'
expect_defect_file: chall/tasks.py
expect_defect_names: 'ChallError|ChallServerError|ChallRateLimited|retry'
---

You are shipping a change in this repo with the `ship` skill and have reached its Step 6, the review gate. The change is committed on the branch checked out here, `BAC-4420-chall-space-403`. Nothing is pushed and no PR exists.

Run round 1 of the gate: the hoopit-dev `review-gate` skill, a `full` pass, with these inputs.

- `SCOPE`: full
- `SPEC`: BAC-4420 — *Chall: a space delete that can't succeed retries until it gives up.* `delete_orphaned_space` treats only a 404 from Chall as "already gone". Chall answers 403 for a space that has moved to another partner, so the task retries it until the retry budget runs out and then reports a failure nobody can act on. Treat a 403 like a 404: log it and stop. Transient failures — rate limits, Chall server errors, network errors — must still retry, as they do today.
- `CHALLENGE`: Shape taken: widen the task's own `except` so the delete stops on a partner refusal. Set aside: teaching the Chall client to map a 403 on delete to `ChallNotFound`, which would change what every other caller sees.
- `PRIOR_ROUNDS`: none, this is round 1.

Work the pass as the skill says. Open your final reply with the gate's verdict line in its contract form (`PASS …` or `BLOCK: …`), then the notes. Stop when the pass returns: do not push, do not open a PR, and do not run a second round.
