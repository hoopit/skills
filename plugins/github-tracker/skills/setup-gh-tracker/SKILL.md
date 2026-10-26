---
name: setup-gh-tracker
description: Set up your GitHub tracker board and config.
disable-model-invocation: true
---

# Set up the GitHub tracker

One run takes a developer from nothing to a working tracker: `gh` authorised, a board of
their own that carries what `hoopit-board` reads, a config naming it, and the tracker
declared where agents look for it. Every step checks before it acts, so a re-run on a
working setup changes nothing and a run that stopped halfway resumes where it stopped.

**Done** when `hoopit-board provision` ends on `READY`, `hoopit-board config` names the
board and finds every repo's checkout, `hoopit-board open` reads the board, and the
developer's global `~/.claude/CLAUDE.md` declares it. A step that cannot finish — an org
admin to fetch, a click only the developer can make — is reported as what is left, never
skipped over.

## 0. Where things stand

```bash
hoopit-board config
```

- Refuses with no config → a first run; start at step 1.
- Prints a config → show it, and ask: keep it and only re-check (steps 1, 3, 5 and 6), or
  set up again (every step, and step 4 replaces the file with `--force`).

## 1. Authorise `gh`

```bash
gh auth status
```

The tracker writes to a Projects v2 board and reads the org's issue fields, so the token
needs the `project` scope — `read:project` only reads — plus `repo` and `read:org`. Read
the `Token scopes:` line.

- **Not logged in** → the developer runs `! gh auth login -h github.com -s project,read:org`.
- **A scope missing** → the developer runs `! gh auth refresh -h github.com -s project,read:org`.

Both open a browser, so they are the developer's to run: say which one, with the `!`
prefix, and wait. A `GH_TOKEN` or `GITHUB_TOKEN` in the environment overrides the login,
and `gh auth status` says so — that token's scopes are the ones that count, and a
fine-grained token lists none: read a project (step 2's list) to test it instead.

**The org** is the one whose repos the developer works in:
`gh repo view --json owner -q .owner.login` from a checkout, or ask. Priority, Effort,
Autonomy and `Start date` are that org's issue fields, so the board must belong to it too.

```bash
gh api user/memberships/orgs/<org> --jq .state    # active
```

**Done** when the scopes are all there and the membership reads `active`.

## 2. Pick the board

```bash
gh project list --owner <org> --format json --limit 100 \
  --jq '.projects[] | select(.closed | not) | "\(.number)\t\(.title)"'
```

Offer the developer two choices: **reuse** a board they already track agent work on —
name the ones whose title carries their name or login — or **create** a fresh one.
Recommend reuse where one is plainly theirs, since `provision` keeps every item and status
already on it. Another developer's board is never a candidate: its items would be
triaged into someone else's queue.

**Create from the org's template** where it has one. A board's workflow rules — which
status *Item added* or *Pull request linked* sets, what *Auto-archive* filters on — have
no API: they cannot be read or written, only copied. A copy carries the source's views,
fields and configured workflows, all but the auto-add ones, and none of its items. So a
template board is how a new board starts with rules somebody has already tuned:

```bash
gh api graphql -f query='query($o:String!){ organization(login:$o){
  projectsV2(first:20, query:"is:template is:open"){ nodes{ number title } } } }' -f o=<org> \
  --jq '.data.organization.projectsV2.nodes[] | "\(.number)\t\(.title)"'
gh project copy <template> --source-owner <org> --target-owner <org> \
  --title "<login> agent board" --format json --jq .number
```

Where several templates are listed, the agent-tracker one is the one to copy; ask if the
titles do not settle it. Where there is none, create a blank board, and step 3 walks the
workflows by hand:

```bash
gh project create --owner <org> --title "<login> agent board" --format json --jq .number
```

**Done** when the developer has confirmed an owner and number.

## 3. Provision the board

```bash
hoopit-board provision --owner <org> --number <n>            # dry run
hoopit-board provision --owner <org> --number <n> --apply
```

The dry run lists what `--apply` would change. On a board already in use, say what that
means before applying: missing statuses are added and a differently-cased one renamed,
every existing option keeps its id — so no item loses its status — and nothing is
deleted except GitHub's default `Todo` on an empty board. It also creates the `Agent` and
`Agent note` fields, which the plugin's hooks keep in step with the session working each
item. Showing them is a view setting `provision` leaves alone, so suggest it to the
developer: a column in their views, or *Slice by* `Agent`.

Then re-run the dry run and work every `MANUAL` line:

- **A workflow** — no API turns one on or sets its rule. Give the developer the URL from
  the line and the status each one must set:
  - *Item added to project* → `Backlog`
  - *Item closed* → `Done`
  - *Pull request linked to issue* → `In review`
  - *Item reopened* → `Backlog`

  Where the org has a template board, its workflows page is the reference for every other
  rule worth copying by hand. Wait for the developer to say it is done, then run the dry
  run again. The API reports whether a workflow is on, not which status it sets, so ask
  them to confirm the status too — a board copied from a template needs this only for a
  workflow the dry run still flags.
- **An org issue field or option** — only an org admin creates or changes these. Name
  exactly what is missing and who can add it, and carry on with the steps that do not
  depend on it; the run ends on it as what is left.

**Done** when the dry run ends on `READY`.

## 4. Write the config

**The checkouts directory** is the one the developer's repos are cloned side by side
in — the parent of the current checkout, as a first guess. Confirm it.

**The repos** are the ones the board spans: every checkout there whose origin belongs to
the org, as a first guess —

```bash
for d in <checkouts>/*/; do git -C "$d" remote get-url origin 2>/dev/null; done
```

— and the developer keeps or trims the list.

**Each repo's production branch** is the branch whose ancestry says a merge is live in
production, which `Gate: deployed` tests. Read it from a `**Production branch:**` line in
the repo's `AGENTS.md` ("Workflow skills config"). Where that line is absent, ask,
offering `git -C <checkout> ls-remote --heads origin` as the menu plus *none* — a repo
that releases through an app store has no such branch.

```bash
hoopit-board init --owner <org> --number <n> --checkouts <dir> \
  --repo <org>/<name>:<branch> --repo <org>/<name> ...
```

A bare `--repo` means no production branch. Add `--force` only where step 0 agreed to
replace a config. `--ladder` belongs to a backlog daemon's setup, not this one.

**Done** when `hoopit-board config` prints the board and a found checkout for every repo.

## 5. The judgement key

```bash
[ -n "$TYPESAFE_API_KEY" ] && echo set || echo unset
```

Unset leaves `hoopit-board`'s duplicate and collision judgements off, with title and path
matching in their place. The developer turns them on by putting the key in the
environment Claude Code runs with — an `env` entry in `~/.claude/settings.json` reaches
every session. The key goes in by the developer's own hand, never through this chat.

## 6. Declare the tracker

Each product repo's `docs/agents/issue-tracker.md` has an agent ask which tracker to file
in until the developer's global `~/.claude/CLAUDE.md` names one, under a heading calling it
their agent tracker. Look for one:

```bash
grep -n -i -A4 'agent tracker' ~/.claude/CLAUDE.md
```

- **Names this board** → nothing to do.
- **Names another tracker, or none** → show the section below, and append it only on the
  developer's yes; it is their file. Where it replaces another declaration, show both.

```markdown
## My agent tracker

My personal agent tracker is the GitHub project **<title>** — <url>. File issues, TODOs,
follow-ups and findings for agent work there with `github-tracker:create-gh-issue`;
`hoopit-board` is its mechanical half. Assign work items to me (`<login>`).
```

## 7. Report

- The board: title, URL, and whether it was reused or created.
- Each repo with its production branch, or none.
- What is left, if anything: a workflow still off, a field awaiting an org admin, the
  judgement key, the declaration the developer declined.
- The plugins these skills lean on, where `claude plugin list` lacks them: `hoopit-dev`
  (`assess-issue` ships through its `ship`) and `mattpocock-skills` (`grilling`,
  `wizard`).
