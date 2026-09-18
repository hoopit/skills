# CLAUDE.md

Guidance for Claude Code when working in this repo. This is a **distribution** of
agent skills, shipped as a Claude Code plugin marketplace (see [README.md](README.md)).
For the skill-authoring conventions, the project-local `create-hoopit-skill` skill
under `.claude/skills/` is the source of truth — including how `${CLAUDE_PLUGIN_ROOT}`
must be written wherever a skill reaches a bundled script.

## Writing skills
Keep the frontmatter short. For regular skills, descriptions should consist of two sentences: "<what>" and "Use when...". The <what> part should be succinct, state the high-level goal, < 50 chars, no details. The "Use when" should generally not exceed ~100 chars.
For user-invokable-only skills, the "Use when ..."  should be removed.
Never expand existing frontmatter descriptions without approval.

## Workflow

- **Commit straight to `main`.** Every skill/plugin change goes directly on `main` — no
  feature branch, no PR. Skip the usual "branch first on the default branch" step here.
- **Edit skills in a working clone, e.g. `~/Dev/Hoopit/skills`.** Everything under
  `~/.claude/plugins/` is an install: `marketplaces/hoopit-skills` is Claude Code's own
  checkout of this repo, reset to `origin/main` by auto-update, and `cache/` is built from
  it. A commit made there exists only until the next refresh, while every install already
  points at it. A skill is loaded from that path, so a fix prompted by running one starts by
  switching to the working clone. When `git rev-parse --show-toplevel` answers with a path
  under `~/.claude/plugins/`, stop and make the change in the working clone instead.

## Skill scope — Hoopit-specific is fine, single-project is not

Skills here are distributed across **all** Hoopit projects (the `api` / backend,
`web-admin`, and `flutter-app`). So:

- **Hoopit org-level facts are allowed.** The Jira instance
  (`hoopit.atlassian.net`), the shared `AI:` custom-field / option ids, the `ITSM`
  triage project, Sentry org `hoopit`, and the `codex-review-manual.yml` workflow are
  identical in every project — a skill may name them (or keep them in shared config).
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
