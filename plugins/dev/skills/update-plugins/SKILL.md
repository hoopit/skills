---
name: update-plugins
description: Update hoopit-dev in every local Hoopit repo.
disable-model-invocation: true
---

# Update hoopit-dev everywhere

hoopit-dev installs per project, so each Hoopit product checkout (`api`, `web-admin`,
`flutter-app`, `public-calendar`) pins its own version and drifts on its own. This run
brings every checkout on the machine to the marketplace's latest.

## 1. Run the updater

```bash
bash "${CLAUDE_PLUGIN_ROOT}/skills/update-plugins/scripts/update-plugins.sh" [checkout-dir ...]
```

It refreshes the `hoopit-skills` marketplace, finds the checkouts, and updates hoopit-dev
in each one — installing it at project scope where the checkout has no install record. The
script's header says how it finds checkouts and what each output line means. Pass a
checkout's directory as an argument when the user names one the search would miss.

Done when the script has exited and printed a `RESULT` line per checkout found.

## 2. Report

One line per repo: its checkout, and `old -> new` or `already current`. A `MISSING <repo>`
line means the machine has no checkout of that repo, which is normal; list it as not
checked out. A `failed` line carries the CLI's own output beneath it; report it verbatim
with the checkout it belongs to.

A `stale` line means the CLI reported success but wrote some other record, so one of the
checkout's own records is still old. The old records are listed beneath it. Back up
`installed_plugins.json`, then:

- If an old record differs from the current one only in the case of its path, it is a
  duplicate: delete it.
- Otherwise the CLI updated a nested worktree's record (`<dir>/.claude/worktrees/...`).
  Delete that worktree's record and rerun the script. If the worktree still exists, run
  `claude plugin install hoopit-dev@hoopit-skills --scope project` inside it.

End with the reminder that a plugin update applies only to sessions started after it, so
any open Claude Code session in an updated checkout needs a restart.
