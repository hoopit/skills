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
