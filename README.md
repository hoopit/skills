# Hoopit — `skills`

Hoopit's **agent skills**, distributed as a
[Claude Code plugin marketplace](https://code.claude.com/docs/en/plugin-marketplaces).
Each plugin lives under [`plugins/<group>/`](plugins/) and bundles its skills.

## Install

Everything below runs from your shell — no need to open Claude Code first. Add the
marketplace once, then install the plugin(s) you want:

```bash
claude plugin marketplace add hoopit/skills
```

For regular dev work you just need `hoopit-dev`. Install it **in-project**
(`--scope project` commits it to the repo's `.claude/settings.json`, so everyone on
the project gets it):

```bash
claude plugin install hoopit-dev@hoopit-skills --scope project
```

To manually pull the latest, update the marketplace and then the plugin:

```bash
claude plugin marketplace update hoopit-skills
claude plugin update hoopit-dev@hoopit-skills
```

> These are also available inside Claude Code as the `/plugin` slash commands
> (e.g. `/plugin install hoopit-dev@hoopit-skills`).
>
> Need one of the other plugins (see the table below)? Same commands with that
> plugin's name.

### Plugins

| Plugin | What's in it |
|--------|--------------|
| `hoopit-onboarding` | Take a fresh machine to a working `hoopit/api` or `hoopit/flutter-app` checkout, plus the supporting CLIs |
| `hoopit-dev` | Day-to-day dev workflows and CLIs: Jira/Sentry issues, PR review, Atlassian, CircleCI |
| `hoopit-misc` | Odds and ends: status line |
| `hoopit-product` | Product work: stress-test plans and ideas against the domain model, sharpen terminology, and produce a PRD |

### Skills by plugin

_Generated from each `SKILL.md` frontmatter and `marketplace.json` by [`scripts/gen-skills-readme.sh`](scripts/gen-skills-readme.sh) — don't edit between the markers by hand._

<!-- BEGIN generated skills: scripts/gen-skills-readme.sh — do not edit between these markers -->
#### `hoopit-onboarding`

Take a fresh machine to a working hoopit/api or hoopit/flutter-app checkout, plus the supporting CLIs.

| Skill | Invoke | Description |
|-------|--------|-------------|
| `install-coderabbit-cli` | Auto | Install the CodeRabbit CLI, authenticate it, and wire up its Claude Code plugin (the `/coderabbit:review` slash command). |
| `install-sentry-cli` | Auto | Install the Sentry CLI (the `sentry` binary from cli.sentry.dev) and authenticate it. |
| `setup-api` | Auto | Set up a brand-new machine for the Hoopit Django API — install tooling (gh, mise/Python 3.14, uv, Docker, pre-commit, Sentry CLI, acli, AWS CLI), clone hoopit/api as a sibling of the skills repo, bootstrap deps + supporting services (Postgres/Redis/stripe-mock), migrate, run the server, and run tests. |
| `setup-flutter-app` | Auto | Set up a brand-new machine for the Hoopit flutter-app — install tooling (gh, mise/Python, FVM, DCM, Sentry CLIs, acli), clone hoopit/flutter-app as a sibling of the skills repo, bootstrap deps/codegen/l10n/pre-commit, wire up Figma MCP, and run the app. |

#### `hoopit-dev`

Day-to-day dev workflows and CLIs: Jira/Sentry issues, PR review, Atlassian, CircleCI.

| Skill | Invoke | Description |
|-------|--------|-------------|
| `atlassian-cli` | Auto | Use when working with Jira or Confluence from command line, including authentication, searching issues with JQL, bulk operations, sprint reports, or creating/updating work items using acli |
| `circleci-tests` | Auto | Fetch failing tests from a CircleCI job URL. |
| `clean-up-worktree` | Auto | Delete the branch and worktree this conversation worked in. |
| `create-pull-request` | Auto | Create GitHub PRs. |
| `curate-memory` | Manual | Curate agent memory as a short-lived working set. |
| `fix-sentry-issue` | Auto | Fix a Sentry issue end-to-end. |
| `handle-jira-issue` | Auto | Handle any Jira issue end-to-end. |
| `monitor-pr` | Auto | Monitor a single pull request. |
| `review-gate` | Auto | Run independent code reviewers. |
| `review-github-comments` | Auto | Handle all review comments on a GitHub PR. |
| `review-jira-attachments` | Auto | Download and analyze the files attached to a Jira issue. |
| `ship` | Auto | Take one understood piece of work in one repo from a branch to a monitored PR. |

#### `hoopit-misc`

Odds and ends: status line.

| Skill | Invoke | Description |
|-------|--------|-------------|
| `setup-statusline` | Auto | Install the team's custom Claude Code status line (directory, git status, model, effort, exact context usage, session token totals). |

#### `hoopit-product`

Product work: stress-test plans and ideas against the domain model, sharpen terminology, and produce a PRD.

| Skill | Invoke | Description |
|-------|--------|-------------|
| `grill-my-idea` | Auto | Grilling session that challenges your plan against the existing domain model and sharpens terminology. |
<!-- END generated skills -->

The onboarding skills clone their project repo as a **sibling** of wherever you run
them (e.g. `../api`, `../flutter-app`).

Some of these skills prefer a third-party skill when it's present — `review-gate`, for
instance, reaches for `mattpocock-skills:code-review`. Those aren't re-packaged here;
install them from their own marketplace so they update straight from upstream:

```bash
claude plugin install mattpocock-skills@claude-plugins-official --scope project
```

Every skill that leans on one falls back gracefully when it isn't installed.

## How it works

The marketplace is declared in
[`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json). Each Hoopit
plugin is a self-contained directory under `plugins/<group>/` with its own
`.claude-plugin/plugin.json` and a `skills/` folder; the marketplace entry just
points `source` at that directory. Skills are auto-discovered from the plugin's
own `skills/` folder, so a plugin exposes **only** its own skills — this is why
each group gets its own directory rather than a shared top-level `skills/` (a
single shared folder would leak every skill into every plugin).

Every plugin here is a local directory — third-party skills are installed from their
own marketplace, as above, rather than re-packaged into a plugin here.

> **Adding or removing a Hoopit skill?** When working in this repo, Claude has a
> project-local `create-hoopit-skill` skill (under `.claude/skills/`) that
> documents the procedure and the files to keep in sync.
