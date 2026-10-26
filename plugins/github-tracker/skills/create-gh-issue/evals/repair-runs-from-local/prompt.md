---
expect_issues: 1
expect_types: Bug,Task
expect_gate: none
tags: split
---
My agent tracker is the GitHub project **LKs agent project** (<https://github.com/orgs/hoopit/projects/2>): `hoopit-board` for its mechanics, `create-gh-issue` for filing. Work items for agent work go there, assigned to me.

You are running unattended: nobody will answer a question before this run ends.

Sentry issue API-5JQ fires every night from `assert_fully_refunded_charges_should_have_zero_amount_paid` (`payments/tasks/sanity_checks.py:442`): "Found 31 refunded Charge where amount paid is not zero". I measured it against prod (read-only) this morning:

- All 31 charges were fully refunded between 2024-03-04 and 2025-01-14. The refund path that left `gross_amount_paid` and `net_amount_paid` standing on their UserPayments was fixed long ago: no charge refunded since 2025-01-14 is flagged, and the count has been 31 for a year.
- No live writer is involved, so nothing new will appear.

The fix: a new management command in `payments/management/commands/`, dry run by default, that zeroes the paid accumulators on exactly the flagged rows and prints each row's old and new values. Then a `--commit` run of it against prod, and API-5JQ resolved. The command needs no migration, Celery task or settings change. None of the existing repair commands covers these rows.

Use the create-gh-issue skill to file the work this needs. Do not write the command. Stop once it is filed, and report what you filed.
