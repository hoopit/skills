---
name: create-pull-request
description: Create GitHub PRs that always link the work item they implement (Jira/Sentry/etc.) and keep Jira links clean — exactly one key, the one this PR delivers, in the branch/commits/title/body, with every related issue moved to a post-creation PR comment, so GitHub-for-Jira doesn't transition unrelated tickets. Use when naming a branch or writing commit messages / a PR title or body in a Jira-connected repo.
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
digits) it finds in the **branch name, commit messages, and PR title + body**.
Wrapping a key in a link or `/browse/` URL does **not** exempt it (open:
github-for-jira#1031).

Linking is not passive. A key in any of those four surfaces is **transitioned**:
opening the PR moves the issue to In Progress / Code Review, merging it moves the
issue to Awaiting release — and if the issue was already at Awaiting release, the
merge pushes it to Ready for QA, *past* the release automation's
`Awaiting release -> Done` sweep, where it parks indefinitely. The changelog
attributes all of this to the PR author, so it is indistinguishable from a human
move after the fact.

### One key, and it is the one you deliver

Those four surfaces carry **exactly one** Jira key: the issue this PR implements.

- **Required:** the target issue's `JIRA_KEY`, in the branch name, the commit
  subject, and the body's link section.
- **Also allowed:** the originating ITSM ticket *when linked* (keep its `## ITSM`
  section + `Refs <ITSM_ISSUE_KEY>` footer) — it is a different project and the
  workflow depends on that link.
- **Safe — never matches:** a Sentry short ID (e.g. `BAC-QCB`, no digits after
  the dash). Keep the `## Sentry` reference and `Fixes <SENTRY_ID>` footer.
- **Forbidden:** every other key — a spun-out follow-up, a blocked-by or
  related ticket, a "same class as …" or "supersedes …" aside, a sibling-project
  issue.

### Related issues go in a separate PR comment

When the reader genuinely needs the context — a follow-up you filed from the
review, the ticket this one supersedes, a sibling in the same class — post it as
a **comment on the PR after creating it**, never in the title, body, branch or
commits:

```bash
gh pr comment "$PR_URL" --body "Spun out of this review: BAC-1234 (…), BAC-1235 (…)."
```

Comments are not part of the development-information sync, so the keys stay
readable without being linked or transitioned. (Believed reliable, not
independently verified here — if you ever see a ticket move at the timestamp of
a PR *comment* rather than a create/merge event, say so and this rule needs
revisiting.)

### Never label a PR with a parent or epic key

The inverse mistake costs just as much: a PR that delivers a child issue must
**not** be titled or branched with the epic/parent key. A child delivered under
its parent's key is invisible to every key-based check — nobody can tell the
ticket shipped, and it sits in a stale status for weeks while its code is live.
The parent advances when its children do, not by borrowing their PRs.

Before opening: re-read the branch name, every commit subject and body, and the
PR title and body, and confirm no `ABC-123`-shaped key beyond the allowed set has
crept in. Move each one you find into a post-creation comment.

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

Then post any related-issue references as a comment, never in the body:

```bash
gh pr comment "$PR_URL" --body "Spun out of this review: BAC-1234 (…)."
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
