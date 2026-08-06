# CLAUDE.md

Guidance for Claude Code when working in this repo. This is a **distribution** of
agent skills, shipped as a Claude Code plugin marketplace (see [README.md](README.md)).
For the skill-authoring conventions, the project-local `create-hoopit-skill` skill
under `.claude/skills/` is the source of truth.

## Workflow

- **Commit most edits straight to `main`.** Routine skill/plugin changes go directly
  on `main` — no feature branch or PR. Skip the usual "branch first on the default
  branch" step here. Reserve a branch for large, risky, or explicitly-requested work.

## Skill scope — Hoopit-specific is fine, single-project is not

Skills here are distributed across **all** Hoopit projects (the `api` / backend,
`web-admin`, and `flutter-app`). So:

- **Hoopit org-level facts are allowed.** The Jira instance
  (`hoopit.atlassian.net`), the shared `AI:` custom-field / option ids, the `ITSM`
  triage project, and Sentry org `hoopit` are identical in every project — a skill
  may name them (or keep them in shared config).
- **Per-project facts must never be hardcoded to one project.** A skill must behave
  correctly whether it's installed into `api`, `web-admin`, or `flutter-app`.
  Anything that differs per project — GitHub repo slug, default branch, Jira project
  key (`BAC` / `WEB` / `FA`), Sentry project — is read at runtime from the installed
  repo's `CLAUDE.md` ("Workflow skills config"), never baked in.

This refines `create-hoopit-skill`'s Rule 1: the test is "true for one Hoopit
**project** but not another," not "mentions Hoopit at all."

## matt-picks: `/plugin` update silently no-ops

`hoopit-matt-picks` tracks `mattpocock/skills` at a moving `main` (no `ref` in
`marketplace.json`), but upstream's `.claude-plugin/plugin.json` pins a static
`"version"` that rarely changes — it read `1.2.0` while `package.json` said `1.1.0`
and the newest release was `v1.1.0`. Claude Code's update check compares **that
version string**, not the tree, so `/plugin` reports "already at the latest version"
and never re-downloads. The cache can sit months behind `main` (it froze at a June 30
commit, 161 behind, until Aug 4).

The symptom is `skills path not found` for picks that plainly exist on GitHub: the
frozen tree predates them. Don't "fix" it by editing the `skills[]` list to match
the stale cache — that's backwards, and it's how `to-tickets`/`to-spec` got reverted
in `78f4eb8`.

To force a real refresh:

```bash
rm -rf ~/.claude/plugins/cache/hoopit-skills/hoopit-matt-picks/*
rm -f  ~/.claude/plugins/plugin-catalog-cache.json
# then /plugin, then /reload-plugins
```

Verify the **content**, not the directory name — the refreshed tarball lands in a
directory still named after the old commit, and carries no `.git`. Compare a blob
against upstream instead:

```bash
git hash-object package.json   # must equal:
gh api "repos/mattpocock/skills/contents/package.json?ref=main" --jq .sha
```

Then run `scripts/gen-skills-readme.sh --refresh`, which 404-checks every pick
against upstream and exits 1 listing any that moved. Run it periodically regardless —
it is the only thing that catches upstream renames, since the version check never
will.

Related: `installed_plugins.json` records a plugin per `projectPath`. A plugin
enabled in a repo's `.claude/settings.local.json` but with no install record for that
path loads fine yet makes `/plugin` uninstall report "plugin doesn't exist."
