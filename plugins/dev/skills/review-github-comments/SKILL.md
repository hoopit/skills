---
name: review-github-comments
description: Review and resolve all review comments on a GitHub PR — fetch comments, evaluate each one, apply fixes where needed, and reply to resolve them.
---

# GitHub PR Review Comments Workflow

## Prerequisites
- The `gh` CLI must be authenticated.
- You must be in the project repository (or a worktree of it).

## Steps

### 1. Get PR metadata
Ask the user for the PR URL if not provided. Extract the `<owner>/<repo>` and `<pr_number>` from the URL.

Then echo the PR url once, so Claude Code renders its footer PR badge for the rest of
the session (it builds that badge by scanning command output for a PR url, and the
`gh api` calls below never print one):
```bash
gh pr view <pr_number> --repo <owner>/<repo> --json url --jq .url
```

### 1b. Work in the PR's worktree if one exists
Fixes must land on the PR branch, so before touching any code find where that branch
is checked out:
```bash
gh pr view <pr_number> --repo <owner>/<repo> --json headRefName --jq .headRefName
git worktree list
```
- If a worktree already has the PR branch checked out, `cd` into it and do all
  edits, commits and pushes there — don't create a second one.
- Otherwise, if the current checkout is on a different branch, add a worktree for
  the PR branch (`git fetch origin <branch> && git worktree add <path> <branch>`)
  rather than switching the user's current checkout.
- Run `git pull --ff-only` in the chosen worktree so you're editing the latest
  PR head before applying fixes.

### 2. Fetch review comments and thread resolution status

Fetch the raw comments:
```bash
gh api repos/<owner>/<repo>/pulls/<pr_number>/comments --paginate
```

Then check which threads are actually unresolved via GraphQL (the REST comments API has no `resolved` field). `reviewThreads` is paginated, so walk every page — a fixed `first: 50` silently drops unresolved threads on a busy PR:
```bash
gh api graphql --paginate \
  -f query='
query($owner: String!, $repo: String!, $pr: Int!, $endCursor: String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      reviewThreads(first: 100, after: $endCursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          isResolved
          comments(first: 1) {
            nodes {
              databaseId
            }
          }
        }
      }
    }
  }
}' -F owner=<owner> -F repo=<repo> -F pr=<pr_number>
```
> `--paginate` requires both the `$endCursor` variable and the `pageInfo` block to follow the cursor. It prints one JSON document **per page**, so merge the `nodes` arrays across pages instead of reading only the first document.

Cross-reference `databaseId` with the REST comment IDs to build a map of `comment_id → isResolved`. Process only threads where `isResolved: false`.

### 3. For each unresolved comment thread

1. **Read the comment** — understand the reviewer's finding, suggestion, or question.
2. **Locate the relevant code** — use the `path` and `line`/`original_line` fields to find the file and line(s) in the local codebase.
3. **Evaluate the comment** — determine whether:
   - **(a) The issue is valid and actionable** — a real bug, improvement, or style fix that should be applied.
   - **(b) The issue is invalid or not applicable** — the reviewer's suggestion is incorrect, outdated, or doesn't apply to the current context.
   - **(c) Unclear or needs more investigation** — you have findings to share but aren't confident enough to resolve it.

4. **Take action based on evaluation:**
   - **Case (a) — Valid & actionable:** Apply the code fix, then reply to the comment explaining what was changed. **Resolve the thread.**
   - **Case (b) — Invalid / not applicable:** Reply to the comment explaining why the suggestion doesn't apply or is incorrect. **Resolve the thread.**
   - **Case (c) — Uncertain / needs discussion:** Reply to the comment with your findings, analysis, or questions. **Do NOT resolve the thread** — leave it open for further discussion.

### 4. Reply to and resolve comment threads

**Replying to a comment** (works for both replies and disagreements):
```bash
gh api repos/<owner>/<repo>/pulls/<pr_number>/comments \
  --field in_reply_to=<comment_id> \
  --field body="Your reply text here."
```
> Note: `in_reply_to` must be an integer. Do **not** use `-f` (string flag) — use `--field` so it is sent as a number.

**Resolving a thread** requires the GraphQL mutation (the REST API has no resolve endpoint). Use the `id` field from the GraphQL thread query above:
```bash
gh api graphql -f query='
mutation {
  resolveReviewThread(input: { threadId: "<PRRT_...node_id>" }) {
    thread { isResolved }
  }
}'
```

### 5. Commit and push
After processing all comments:
1. Stage all modified files.
2. Commit with a descriptive message, e.g.:
   ```
   fix: address PR review comments

   Resolved comments from coderabbitai on PR #<pr_number>.
   ```
3. Push to the PR branch. **Always push** unless the user explicitly asked not to
   (e.g. "don't push", "leave it local") — a fix that only exists locally doesn't
   answer the reviewer, and the reply you already posted claims it's addressed.
   If pushing is declined, say so plainly in the summary.


### 5b. Clear a stale CodeRabbit "changes requested" review
CodeRabbit often submits its findings as a `REQUEST_CHANGES` review. Resolving the threads
does **not** clear that state — the PR stays blocked on "changes requested" until the review
is superseded or dismissed. After pushing, check:
```bash
gh api repos/<owner>/<repo>/pulls/<pr_number>/reviews \
  --jq '.[] | select(.state=="CHANGES_REQUESTED") | {id, user: .user.login}'
```
For each `CHANGES_REQUESTED` review from `coderabbitai[bot]`:
- **If you fixed or explained every thread from that review**, ask CodeRabbit to re-review so it
  supersedes its own verdict — post a PR comment `@coderabbitai review`. That is the preferred
  path; it also surfaces anything your fixes introduced. If the user wants the PR unblocked
  immediately (or CodeRabbit doesn't respond), dismiss the stale review instead:
  ```bash
  gh api -X PUT repos/<owner>/<repo>/pulls/<pr_number>/reviews/<review_id>/dismissals \
    -f message="Addressed in <short-sha>; threads resolved." -f event=DISMISS
  ```
- **If any thread from that review is still open (case c)**, leave the review in place — the
  block is legitimate — and say so in the summary.

Never dismiss a `CHANGES_REQUESTED` review from a **human** reviewer; only they (or a re-review)
should clear it. Mention it in the summary as still pending.

### 6. Report summary
Print a summary table of all processed comments:

| # | File | Reviewer | Action | Resolved? |
|---|------|----------|--------|-----------|
| 1 | `path/to/file` | coderabbitai | Applied fix | ✅ Yes |
| 2 | `path/to/other` | coderabbitai | Invalid — explained why | ✅ Yes |
| 3 | `path/to/another` | coderabbitai | Shared findings, needs discussion | ❌ No |
