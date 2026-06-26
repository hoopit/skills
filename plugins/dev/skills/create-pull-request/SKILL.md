---
name: create-pull-request
description: Create GitHub PRs that always link the work item they implement (Jira/Sentry/etc.) and keep Jira links clean — emit only the keys this PR delivers so GitHub-for-Jira doesn't attach it to unrelated tickets. Use when naming a branch or writing commit messages / a PR title or body in a Jira-connected repo.
---

# Create a Pull Request

For repos wired to Jira via the **GitHub-for-Jira** integration. Load before you
name a branch, write commit messages, or write a PR title/body — the workflow
skills (`handle-jira-issue`, `fix-sentry-issue`) point here at their PR step.

## Always link the item you're implementing

Every PR **must** link the work item it delivers, near the top of the body, so a
reviewer can jump to its source of truth:

- **Jira** — `https://<org>.atlassian.net/browse/<JIRA_KEY>` (the raw key also
  makes GitHub-for-Jira attach the PR — exactly what you want here).
- **Sentry** — the issue URL, e.g. `https://<org>.sentry.io/issues/<id>/`.
- **Other tracker** — the item's canonical URL.

If there's genuinely no tracked item (e.g. a pure chore), say so in the body.

## Keep Jira links clean (GitHub-for-Jira)

GitHub-for-Jira links the PR to **every** Jira key (`ABC-123` — letters, dash,
digits) in the **branch name, commit messages, and PR title + body**. Wrapping a
key in a link or `/browse/` URL does **not** exempt it (open: github-for-jira#1031).

So: **emit only the keys for items this PR actually delivers** — everything else
stays out of those four surfaces.

- **Link freely:** the target issue's `JIRA_KEY`; the originating ITSM ticket
  *when linked* (keep its `## ITSM` section + `Refs <ITSM_ISSUE_KEY>` footer).
- **Safe — never matches:** a Sentry short ID (e.g. `BAC-QCB`, no digits after
  the dash). Keep the `## Sentry` reference and `Fixes <SENTRY_ID>` footer.
- **Forbidden:** any unrelated work item (sibling-project issue, unrelated task,
  "similar to …" aside). Reference those in Jira, not the PR.

Before opening: re-read freeform sections and commit bodies, and confirm no
`ABC-123`-shaped key beyond the allowed set has crept in.

## Creating the PR

Open the PR with the GitHub CLI, from inside the worktree:

```bash
cd "$WORKTREE_DIR"   # if working in a worktree
gh pr create \
  --title "<branch-name>" \
  --body "## Summary
<what the change does>

<work-item link section(s) — see above>

## Changes
- <bullet summary>

## Testing
- <tests added, or why none was feasible>" \
  --base "$DEFAULT_BRANCH"
```

A calling workflow adds its own body sections (e.g. an `## ITSM` / `## Sentry`
reference, a code-review notes block) — keep those, and apply the link-hygiene
rules above to every section. Report the PR URL when done.

**Required labels — create the PR *with* them.** If an orchestrator (or the
user) requires specific labels, append `--label <name>` per label to
`gh pr create` rather than adding them afterward, so the PR is born labelled and
a `pull_request`-triggered automation never sees an unlabelled window. Omit when
none are required (the human-driven default). Labels must already exist in the
repo; if `gh pr create` rejects one, create the PR without it and backfill with
`gh pr edit <pr> --add-label <name>`.
