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

## Third-party skills

Skills our skills reference but don't ship — Matt Pocock's, for instance — are
installed from their own marketplace (`mattpocock-skills@claude-plugins-official`,
enabled for this repo in `.claude/settings.json`), never re-packaged into a plugin
here. Reference them by namespaced name (`mattpocock-skills:code-review`).

## Comments and docs describe the present

Write what is true now. A comment must never narrate what an earlier version of
itself said, what was removed, or when something changed — `git log`, the commit
message and the pull request description carry that. A comment that reports a
change is stale the moment someone reads it without that change in mind, and it
costs the next reader time working out whether the "now" it describes is still
now.

- ✅ `Callers must hold the lock before entering.`
- ❌ `The lock used to be taken by the caller; moved in here on 2026-05-02.`
- ✅ `This token must exist only as a secret of the automation environment.`
- ❌ `The org-level copy is now deleted, so this is finally a real boundary.`

This binds code comments, workflow and config comments, doc comments, `CLAUDE.md`
/ `AGENTS.md` and everything under `docs/` alike. The one exception is a document
whose genre *is* the historical record — an ADR's Context and Decision, or a
changelog — where the dated narrative is the point.

When the text you are replacing carried a warning, keep the warning as a rule
that still binds and drop only the status report wrapped around it.

## `/plugin` uninstall says "plugin doesn't exist"

`installed_plugins.json` records a plugin per `projectPath`. A plugin enabled in a
repo's `.claude/settings.local.json` but with no install record for that path loads
fine yet makes `/plugin` uninstall report "plugin doesn't exist."
