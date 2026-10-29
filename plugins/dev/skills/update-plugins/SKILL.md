---
name: update-plugins
description: Update the Hoopit plugins in every local Hoopit repo.
disable-model-invocation: true
---

# Update the plugins everywhere

hoopit-dev and `mattpocock-skills`, which its skills lean on, install per project, so each
checkout that has them pins its own version and drifts on its own. This run brings every
such checkout on the machine to the marketplace's latest, and installs them in Hoopit
product checkouts (`api`, `web-admin`, `flutter-app`, `public-calendar`) that lack them.
A user-scope record of either is updated too, but they are never installed at user scope.
github-tracker and hoopit-product are updated too, but only where they are already
installed — at user scope, or at project or local scope in a checkout — since not every
developer uses them.

## 1. Run the updater

```bash
bash "${CLAUDE_PLUGIN_ROOT}/skills/update-plugins/scripts/update-plugins.sh" [checkout-dir ...]
```

It refreshes the plugins' marketplaces, updates every checkout with a hoopit-dev or
`mattpocock-skills` install record, and installs them at project scope in Hoopit product
checkouts that have none. The script's header says how it finds checkouts and what each
output line means. Pass a checkout's directory as an argument when the user names one the
search would miss; it is installed or updated whatever its remote.

Done when the script has exited and printed a `RESULT` line per plugin and checkout found,
one per user-scope record, and one per github-tracker or hoopit-product install record.

## 2. Report

One line per checkout and plugin: its name and directory, and `old -> new` or `already
current`. A line at user scope names `user` in place of a repo. A `failed`
line carries the CLI's own output beneath it; report it verbatim
with the checkout it belongs to.

A `stale` line means the CLI reported success but the checkout's own record does not show
the new version. The records at fault are listed beneath it. Back up
`installed_plugins.json`, then match what you find there:

- The checkout has another record at the new version, differing only in path case: the
  old one is a duplicate. Delete it.
- A record under `<dir>/.claude/worktrees/` is at the new version: the CLI updated that
  worktree instead. Delete the worktree's record and rerun the script. If the worktree
  still exists, run `claude plugin install <plugin> --scope project` inside it.
- `(no record)`, or neither case above: delete nothing. Report the line and the
  checkout's records verbatim.

End with the reminder that a plugin update applies only to sessions started after it, so
any open Claude Code session in an updated checkout needs a restart.
