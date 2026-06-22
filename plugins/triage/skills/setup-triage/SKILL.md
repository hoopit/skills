---
name: setup-triage
description: Discover and write the central triage configuration (.claude/triage-config.json) that all the hoopit-triage skills read — Jira instance + AI custom fields (org-level) plus each project's Jira/Sentry/repo details. Run once in the triage repo (the one with api/web-admin/flutter-app as siblings). Idempotent — fills only what's missing. Use when setting up, configuring, or onboarding triage, or when a triage skill reports its config is missing.
---

# Set up triage config

Writes **one** config file — `.claude/triage-config.json` in this (the triage) repo — that every
`hoopit-triage` skill and script reads: `triage-itsm`, `triage-sentry`, and `auto-fix-next-bug`.

- **Org-level** values (Jira instance, the `AI:` custom-field/option ids, Sentry org, labels, budget) are
  identical across Hoopit and come from the bundled `config.template.json`.
- **Per-project** values live under `projects.<repo>` and are **discovered** from the sibling project
  repos + Sentry: Jira project key, GitHub repo slug, default branch, Sentry project + numeric id.

The writer (`scripts/write_config.py`) is **idempotent and additive**: it never overwrites an existing
value — it only fills keys that are missing or empty. Safe to re-run any time (e.g. after adding a
project or a Sentry slug).

## Prerequisites

- Run this **from the triage repo** (where the triage skills run) — the one that has the project repos
  (`api`, `web-admin`, `flutter-app`) checked out as **siblings** under a common parent.
- `gh auth status` OK (for default branch); `sentry auth status` OK (for Sentry project ids). Missing
  Sentry just leaves those keys null — they're flagged, not fatal.

## Step 1 — Locate the repos

```bash
ROOT="$(git rev-parse --show-toplevel)"           # the triage repo
HOOPIT_ROOT="$(dirname "$ROOT")"                   # parent holding all sibling repos
ls -d "$HOOPIT_ROOT"/*/ | xargs -n1 basename       # candidate project dirs
```

The **config project key is the sibling directory name** (`api`, `web-admin`, `flutter-app`).

## Step 2 — Discover each project

For every sibling dir that has a `CLAUDE.md` (skip the triage repo itself), gather:

```bash
d="$HOOPIT_ROOT/<dir>"
# GitHub repo slug (owner/name):
git -C "$d" remote get-url origin | sed -E 's#.*[:/]([^/]+/[^/]+?)(\.git)?$#\1#'
# Default branch:
git -C "$d" remote show origin | sed -n 's/ *HEAD branch: //p'
# Jira project key (from the repo's Workflow skills config — same grep handle-jira-issue uses):
grep -iE '^\s*[-*]\s*\*\*Jira project key:\*\*' "$d/CLAUDE.md" | grep -oE '`[A-Z][A-Z0-9]+`' | tr -d '`' | head -1
```

Then the Sentry project + numeric id per project (skip / leave null if you can't resolve it):

```bash
sentry api "organizations/hoopit/projects/" | jq -r '.[] | "\(.slug)\t\(.id)"'
```

Match the project to its Sentry slug (e.g. `api` → `bac`/`248915`) and capture both. If a project has no
Sentry project yet (web-admin/flutter today), leave `sentry_project`/`sentry_project_id` unset.

## Step 3 — Merge into the config (idempotent)

Assemble the discovered values as one JSON object keyed by project dir, and hand it to the writer. The
script path is relative to this skill:

```bash
python3 scripts/write_config.py --dry-run --values '{
  "projects": {
    "api":         { "repo": "hoopit/api", "default_branch": "master", "jira_project": "BAC", "sentry_project": "bac", "sentry_project_id": "248915" },
    "web-admin":   { "repo": "hoopit/web-admin", "default_branch": "main", "jira_project": "WEB" },
    "flutter-app": { "repo": "hoopit/flutter-app", "default_branch": "main", "jira_project": "FA" }
  }
}'
```

Review the dry-run report (it lists every key it would **add**, and anything **still missing**), then
re-run **without `--dry-run`** to write `.claude/triage-config.json`. Org-level defaults are filled from
the template automatically; existing values are preserved.

## Step 4 — Report & wire up CLAUDE.md

- Tell the user what was added and surface the `still missing / needs input` items verbatim (e.g.
  web-admin / flutter-app Sentry slugs) — those need a human or a later re-run.
- Ensure this repo's `CLAUDE.md` → `## Agent skills` → `### Workflow skills config` has a line pointing
  at the file, adding it only if absent:

  > Triage config: `.claude/triage-config.json` (managed by the `setup-triage` skill).

## What reads this file

- `triage-itsm/scripts/apply_verdicts.py` — org-level keys (fields, options, `valid_components`, `status_map`).
- `triage-sentry/scripts/{apply_review,promote_pending}.py` — resolve a project block via `--project <key>`
  (default `api`) merged over the org-level keys.
- `auto-fix-next-bug/scripts/select_next_bug.py` — the `projects` map (all boards, or one via `--project`).

All default to `<repo-root>/.claude/triage-config.json`; pass `--field-map`/`--config` only to override.
