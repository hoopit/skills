---
max_turns: 60
timeout_seconds: 1800
tags: [scope]
expect_change: org-admin-clean org-admin-cached
expect_branch: BAC-4412-org-admin-check
expect_codex: ran
expect_codex_model: gpt-6-luna
expect_codex_effort: medium
expect_reviewers: 1
expect_challenge: 0
---

You are shipping a change in this repo with the `ship` skill and are in its Step 6, the review gate. The change is on the branch checked out here, `BAC-4412-org-admin-check`. Nothing is pushed and no PR exists.

Round 1 was a `full` pass. Its reviewers saw the first commit, `HEAD~1`. It returned `PASS` with one code fix commit, `HEAD`, which caches `_is_org_admin` per request after a Low finding from Codex. The challenge ran in round 1, at `HEAD~1`.

Run round 2 of the gate: the hoopit-dev `review-gate` skill, a `light` pass over that fix commit, with these inputs.

- `SCOPE`: light
- `REVIEWED_AT`: the sha of `HEAD~1`
- `CHALLENGE_AT`: the sha of `HEAD~1`
- `SPEC`: BAC-4412 — *Bank account list: one org-admin check.* `OrganizationBankAccountListView` decides whether the requester is an org (root) admin in two places: inline in `get_queryset`, which narrows a sub-group admin to the accounts connected to groups they manage, and in `_can_view_balance`, which gates the balance column and the export. Extract one helper both use, so the two can't drift. No behaviour change: a sub-group admin must still see only their connected accounts and no balances.
- `PRIOR_ROUNDS`: round 1: Low.

Work the pass as the skill says. Open your final reply with the gate's verdict line in its contract form (`PASS …` or `BLOCK: …`), then the notes. Stop when the pass returns: do not push, do not open a PR, and do not run another round.
