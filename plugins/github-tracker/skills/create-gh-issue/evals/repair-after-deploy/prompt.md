---
expect_issues: 1
expect_types: Ops
expect_gate: 19512
tags: split
---
My agent tracker is the GitHub project **LKs agent project** (<https://github.com/orgs/hoopit/projects/2>): `hoopit-board` for its mechanics, `create-gh-issue` for filing. Work items for agent work go there, assigned to me.

You are running unattended: nobody will answer a question before this run ends.

You are shipping hoopit/api#19509. Its PR, hoopit/api#19512 ("GH-19509: Book the fee of a partial refund on the refunded share only"), is open, green and reviewed, waiting for its merge. What it changes:

- A partial refund re-quotes `total_fee_paid` on the whole payment instead of the refunded share. The writer is fixed in this PR. Until the PR is in production it keeps writing bad rows, about four a day.
- The PR also adds `repair_partial_refund_fee_paid`, dry run by default, which rewrites `total_fee_paid` from the booked payout entries on every row `assert_user_payment_fee_matches_report_entries` (`payments/tasks/sanity_checks.py:261`) flags. Today that is 212 rows.

The PR's description says `closes #19509`, and #19509 closes when the PR merges.

Before the merge, use the create-gh-issue skill to file whatever this leaves to do. Stop once it is filed, and report what you filed.
