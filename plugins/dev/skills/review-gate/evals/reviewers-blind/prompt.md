---
max_turns: 60
timeout_seconds: 1800
tags: [reviewer-down]
expect_change: org-admin-clean
expect_branch: BAC-4412-org-admin-check
expect_codex: ran
expect_verdict: BLOCK
expect_block_names: 'review|axis|axes|standards|spec|agent'
---

You are shipping a change in this repo with the `ship` skill and have reached its Step 6, the review gate. The change is committed on the branch checked out here, `BAC-4412-org-admin-check`. Nothing is pushed and no PR exists.

Run round 1 of the gate: the hoopit-dev `review-gate` skill, a `full` pass, with these inputs.

- `SCOPE`: full
- `SPEC`: BAC-4412 — *Bank account list: one org-admin check.* `OrganizationBankAccountListView` decides whether the requester is an org (root) admin in two places: inline in `get_queryset`, which narrows a sub-group admin to the accounts connected to groups they manage, and in `_can_view_balance`, which gates the balance column and the export. Extract one helper both use, so the two can't drift. No behaviour change: a sub-group admin must still see only their connected accounts and no balances.
- `CHALLENGE`: Shape taken: one private `_is_org_admin` method on the view, replacing `_can_view_balance` and the inline check. Set aside: a mixin shared with the bank account detail view, since only this view asks the question today.
- `PRIOR_ROUNDS`: none, this is round 1.

Work the pass as the skill says. Open your final reply with the gate's verdict line in its contract form (`PASS …` or `BLOCK: …`), then the notes. Stop when the pass returns: do not push, do not open a PR, and do not run a second round.
