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
| `babysit-prs` | Auto | Babysit your open PRs — sweep for merge conflicts, failing checks, and unresolved review comments; fix what's safe, report the rest. |
| `circleci-tests` | Auto | Fetch failing tests from a CircleCI job URL. |
| `create-pull-request` | Auto | Create GitHub PRs that always link the work item they implement (Jira/Sentry/etc.) and keep Jira links clean — emit only the keys this PR delivers so GitHub-for-Jira doesn't attach it to unrelated tickets. |
| `curate-memory` | Manual | Review, prune, and promote Claude Code agent memories — delete stale/shipped ones, and move durable team-relevant knowledge into the right shared home (a path-scoped rule, a directory CLAUDE.md, root CLAUDE.md, or leave it a skill). |
| `fix-itsm-issue` | Auto | Fix an ITSM ticket end-to-end across every project it affects — read the ticket + attachments, resolve or create the linked platform issue in each affected repo, then ship one PR per repo via implement-and-ship-fix. |
| `fix-sentry-issue` | Auto | Fix a Sentry issue end-to-end — fetch details, create or link a Jira ticket (with a native bidirectional Sentry↔Jira link), then ship the fix (branch, fix, test, review, PR) via implement-and-ship-fix. |
| `handle-jira-issue` | Auto | Handle any Jira issue end-to-end — an ITSM ticket or a project issue (BAC/WEB/FA). |
| `implement-and-ship-fix` | Auto | Ship a fix for an already-identified bug end-to-end — worktree, minimal fix, regression test, review gate, push, PR. |
| `review-gate` | Auto | Run multiple independent code reviewers (the mattpocock-skills two-axis /review + CodeRabbit + Codex) on the committed branch changes before a PR, aggregate and de-dup findings, fix what is valid, and BLOCK the PR (with notes) on any disputed Critical/High finding. |
| `review-github-comments` | Auto | Review and resolve all review comments on a GitHub PR — fetch comments, evaluate each one, apply fixes where needed, and reply to resolve them. |
| `review-jira-attachments` | Auto | Download and analyze the files attached to a Jira issue — HAR network captures, screenshots, logs, PDFs — via the Jira REST API, because acli cannot download attachments. |

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

Every plugin here is a local directory. A marketplace *can* also list a plugin fetched
from another repo (a `github` source with a `strict` pick-list), but we don't — see
[CLAUDE.md](CLAUDE.md) for why that goes stale.

> **Adding or removing a Hoopit skill?** When working in this repo, Claude has a
> project-local `create-hoopit-skill` skill (under `.claude/skills/`) that
> documents the procedure and the files to keep in sync.
