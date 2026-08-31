---
name: create-pull-request
description: Create GitHub PRs that link the work item they deliver and keep Jira keys off unrelated tickets. Use when naming a branch, writing commit messages, or writing a PR title or body in a Jira-connected repo.
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

## Keep Jira keys on their own ticket (GitHub-for-Jira)

GitHub-for-Jira scans four **linked surfaces** — the branch name, the commit
messages, the PR title and the PR body — and acts on every Jira key (`ABC-123` —
letters, dash, digits) it finds there. Wrapping a key in a link or `/browse/`
URL does not exempt it (open: github-for-jira#1031).

It acts, not merely links: opening the PR moves each key it found to In Progress
/ Code Review, merging moves it to Awaiting release, and a key already at
Awaiting release is pushed to Ready for QA — past the release automation's
`Awaiting release -> Done` sweep, where it parks indefinitely.

### One key on the linked surfaces, and it is the one you deliver

- **Required:** the target issue's `JIRA_KEY`, in the branch name, the commit
  subject, and the body's link section.
- **Also allowed:** the originating ITSM ticket *when linked* (keep its `## ITSM`
  section + `Refs <ITSM_ISSUE_KEY>` footer) — a different project, and the
  workflow depends on that link.
- **Inert — never matches:** a Sentry short ID (e.g. `BAC-QCB`, no digits after
  the dash). Keep the `## Sentry` reference and `Fixes <SENTRY_ID>` footer.
- **Everything else drops the hyphen:** a spun-out follow-up, a blocked-by or
  related ticket, a "same class as …" or "supersedes …" aside, a sibling-project
  issue.

Write a non-primary issue with a space where the hyphen goes — `ABC 123`, not
`ABC-123`. The scan matches letters-dash-digits, so the spaced form is inert: a
reviewer still reads it and can paste it into Jira, and nothing is linked or
transitioned. It is not a clickable key, which is the point.

```
Spun out of this review: ABC 123 (co-guardian partial invoice), ABC 124.
```

### A child's PR carries the child's key

A PR that delivers a child issue takes the child's key on its linked surfaces,
not the epic's or parent's. Delivered under a parent's key, the work is
invisible to every key-based check: nobody can tell the ticket shipped, and it
sits in a stale status for weeks while its code is live. A parent advances when
its children do.

### Before you open the PR

Re-read every linked surface and confirm each `ABC-123`-shaped key on it is in
the allowed set. Drop the hyphen from every one that is not.

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
