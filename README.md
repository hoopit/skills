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
| `hoopit-matt-picks` | A curated set of [mattpocock/skills](https://github.com/mattpocock/skills), tracking upstream |

### Skills by plugin

_Generated from each `SKILL.md` frontmatter and `marketplace.json` by [`scripts/gen-skills-readme.sh`](scripts/gen-skills-readme.sh) — don't edit between the markers by hand._

<!-- BEGIN generated skills: scripts/gen-skills-readme.sh — do not edit between these markers -->
**`hoopit-onboarding`** — Take a fresh machine to a working hoopit/api or hoopit/flutter-app checkout, plus the supporting CLIs.

| Skill | Invocation | Description |
|-------|------------|-------------|
| `install-coderabbit-cli` | Automatic | Install the CodeRabbit CLI, authenticate it, and wire up its Claude Code plugin (the `/coderabbit:review` slash command). |
| `install-sentry-cli` | Automatic | Install the Sentry CLI (the `sentry` binary from cli.sentry.dev) and authenticate it. |
| `setup-api` | Automatic | Set up a brand-new machine for the Hoopit Django API — install tooling (gh, mise/Python 3.14, uv, Docker, pre-commit, Sentry CLI, acli, AWS CLI), clone hoopit/api as a sibling of the skills repo, bootstrap deps + supporting services (Postgres/Redis/stripe-mock), migrate, run the server, and run tests. |
| `setup-flutter-app` | Automatic | Set up a brand-new machine for the Hoopit flutter-app — install tooling (gh, mise/Python, FVM, DCM, Sentry CLIs, acli), clone hoopit/flutter-app as a sibling of the skills repo, bootstrap deps/codegen/l10n/pre-commit, wire up Figma MCP, and run the app. |

**`hoopit-dev`** — Day-to-day dev workflows and CLIs: Jira/Sentry issues, PR review, Atlassian, CircleCI.

| Skill | Invocation | Description |
|-------|------------|-------------|
| `atlassian-cli` | Automatic | Use when working with Jira or Confluence from command line, including authentication, searching issues with JQL, bulk operations, sprint reports, or creating/updating work items using acli |
| `circleci-tests` | Automatic | Fetch failing tests from a CircleCI job URL. |
| `create-pull-request` | Automatic | Create GitHub PRs that always link the work item they implement (Jira/Sentry/etc.) and keep Jira links clean — emit only the keys this PR delivers so GitHub-for-Jira doesn't attach it to unrelated tickets. |
| `curate-memory` | User-invoked only | Review, prune, and promote Claude Code agent memories — delete stale/shipped ones, and move durable team-relevant knowledge into the right shared home (a path-scoped rule, a directory CLAUDE.md, root CLAUDE.md, or leave it a skill). |
| `fix-sentry-issue` | Automatic | Fix a Sentry issue end-to-end — fetch details, create or link a Jira ticket (with a native bidirectional Sentry↔Jira link), branch, fix, test, review, and open a PR. |
| `handle-jira-issue` | Automatic | Handle any Jira issue end-to-end — an ITSM ticket or a project issue (BAC/WEB/FA). |
| `review-gate` | Automatic | Run multiple independent code reviewers (the matt-picks two-axis /review + CodeRabbit + Codex) on the committed branch changes before a PR, aggregate and de-dup findings, fix what is valid, and BLOCK the PR (with notes) on any disputed Critical/High finding. |
| `review-github-comments` | Automatic | Review and resolve all review comments on a GitHub PR — fetch comments, evaluate each one, apply fixes where needed, and reply to resolve them. |
| `review-jira-attachments` | Automatic | Download and analyze the files attached to a Jira issue — HAR network captures, screenshots, logs, PDFs — via the Jira REST API, because acli cannot download attachments. |

**`hoopit-misc`** — Odds and ends: status line.

| Skill | Invocation | Description |
|-------|------------|-------------|
| `setup-statusline` | Automatic | Install the team's custom Claude Code status line (directory, git status, model, effort, exact context usage, session token totals). |

**`hoopit-product`** — Product work: stress-test plans and ideas against the domain model, sharpen terminology, and produce a PRD.

| Skill | Invocation | Description |
|-------|------------|-------------|
| `grill-my-idea` | Automatic | Grilling session that challenges your plan against the existing domain model and sharpens terminology. |

**`hoopit-matt-picks`** — Curated picks from mattpocock/skills, tracking upstream.

Invoked namespaced as `mattpocock-skills:<name>`; descriptions live [upstream](https://github.com/mattpocock/skills).

| Skill | Invocation | Group |
|-------|------------|-------|
| `mattpocock-skills:ask-matt` | Automatic | Engineering |
| `mattpocock-skills:codebase-design` | Automatic | Engineering |
| `mattpocock-skills:diagnosing-bugs` | Automatic | Engineering |
| `mattpocock-skills:domain-modeling` | Automatic | Engineering |
| `mattpocock-skills:grill-with-docs` | Automatic | Engineering |
| `mattpocock-skills:implement` | Automatic | Engineering |
| `mattpocock-skills:improve-codebase-architecture` | Automatic | Engineering |
| `mattpocock-skills:prototype` | Automatic | Engineering |
| `mattpocock-skills:resolving-merge-conflicts` | Automatic | Engineering |
| `mattpocock-skills:setup-matt-pocock-skills` | Automatic | Engineering |
| `mattpocock-skills:tdd` | Automatic | Engineering |
| `mattpocock-skills:to-issues` | Automatic | Engineering |
| `mattpocock-skills:to-prd` | Automatic | Engineering |
| `mattpocock-skills:triage` | Automatic | Engineering |
| `mattpocock-skills:claude-handoff` | Automatic | In progress |
| `mattpocock-skills:decision-mapping` | Automatic | In progress |
| `mattpocock-skills:loop-me` | Automatic | In progress |
| `mattpocock-skills:review` | Automatic | In progress |
| `mattpocock-skills:wayfinder` | Automatic | In progress |
| `mattpocock-skills:wizard` | Automatic | In progress |
| `mattpocock-skills:handoff` | Automatic | Productivity |
| `mattpocock-skills:teach` | Automatic | Productivity |
| `mattpocock-skills:writing-great-skills` | Automatic | Productivity |
<!-- END generated skills -->

The onboarding skills clone their project repo as a **sibling** of wherever you run
them (e.g. `../api`, `../flutter-app`). `hoopit-matt-picks` is sourced from Matt's
repo, so it picks up his latest when you run the update commands above.

## How it works

The marketplace is declared in
[`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json). Each Hoopit
plugin is a self-contained directory under `plugins/<group>/` with its own
`.claude-plugin/plugin.json` and a `skills/` folder; the marketplace entry just
points `source` at that directory. Skills are auto-discovered from the plugin's
own `skills/` folder, so a plugin exposes **only** its own skills — this is why
each group gets its own directory rather than a shared top-level `skills/` (a
single shared folder would leak every skill into every plugin).

`hoopit-matt-picks` is the exception: it uses a `github` source pointing at
`mattpocock/skills` with `strict: true` and an explicit `skills` array listing
the specific skill paths to surface (a marketplace can list a plugin fetched from
a different repo). `strict: true` makes that curated list authoritative, so it
overrides the upstream plugin's own manifest instead of conflicting with it.

> **Adding or removing a Hoopit skill?** When working in this repo, Claude has a
> project-local `create-hoopit-skill` skill (under `.claude/skills/`) that
> documents the procedure and the files to keep in sync.
