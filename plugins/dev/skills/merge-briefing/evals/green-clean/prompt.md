---
max_turns: 50
timeout_seconds: 1200
expect_change: org-admin-clean
expect_branch: BAC-4412-org-admin-check
expect_pr: 90951
tags: [briefed]
expect_codex: ran
expect_outcome: briefed
expect_challenge: ran
expect_marker: ran
expect_recommend: merge
expect_risk: 'moderate|high|very high'
expect_lane: human
expect_line: 'CHALLENGE: ran weighed=0 held=0 marker=ran'
---

You are the hoopit-dev `monitor-pr` skill's GREEN path on https://github.com/hoopit/api/pull/90951, and you own its rounds. The watch has fired `GREEN` on the head checked out here, branch `BAC-4412-org-admin-check`. Brief the PR: invoke the hoopit-dev `merge-briefing` skill from this checkout, as the owner of the PR's rounds, and write the briefing into the description. Hand it:

- **Issues:** the PR closes no GitHub issue; it delivers BAC-4412 — *Bank account list: one org-admin check.* `OrganizationBankAccountListView` decides whether the requester is an org (root) admin in two places; extract one helper both use, so the two can't drift. No behaviour change: a sub-group admin must still see only their connected accounts and no balances.
- **Judgement rows** from the ledger:
  - Round 1 declined a mixin shared with the detail view: only this view asks the question today.
  - Round 2 declined CodeRabbit's rename of `_is_org_admin` to `_is_root_admin`: "org admin" is the domain term across payments.
- **Recommendation:** merge — every check is green bar the `merge-briefing` status this briefing passes, no review thread is open, no reviewer is owed on this head, and the description has no `## Run before merge` box.

This session runs in print mode: nobody can answer a question. Stop when the skill returns, and end your reply with what it returns to its caller — the `CHALLENGE:` line, and `HELD:` with its findings if it held. Do not push, mark the PR ready, merge it or answer review threads: the rest of the GREEN path is not yours here.
