# The ledger

The ledger is a PR's standing record of **judgement** — every decision an agent made on
it that a human might want to overturn. It lives in the PR description, is rewritten in
place each round, and holds the current state of every judgement rather than a history
of rounds. Its readers are the user and the PR's human reviewers, so it is written for
someone who has not read the threads.

Every review thread, failing check and merge conflict lands in exactly one tier:

- **fork** — a decision that belongs to the user. Answered forks stay in the ledger, so
  the answer is visible without reading back through the session.
- **judgement** — a decision the agent settled itself.
- **tally** — labour: work with no decision in it. Counted, never listed.

## Classifying an item

- **source** — `CodeRabbit`, `codex`, `@<login>` for a human reviewer, `CI/<check name>`,
  `conflict`.
- **severity** — `Critical` / `High` / `Med` / `Low`, as the *source* framed it. Lower it
  only with the reason in `why`.
- **decision** — `applied`, `declined`, `open` (replied to, thread left unresolved),
  `fork` (waiting on the user), or `answered: <the user's choice>`.
- **why** — one clause. For `declined`, name the evidence that makes the finding wrong
  here — the test, the line, the config — rather than asserting it.
- **scope** — facts, never a score, and only when the fix reached past the lines the
  source pointed at: `+2 files`, `+1 migration`, `+dep: <name>`, `public API change`. A
  fix that changes exactly what was flagged carries no scope note.
- **link** — the thread or check URL. Paraphrase the source's claim in one clause and
  link it; the thread holds the full text.

A `declined` Critical or High also carries the counterfactual in `why` — what fixing it
as asked would have cost (`~4 files across the serializer layer`). That is the
justification for declining, so it belongs beside the decline.

## Which items earn a row

A row is earned by judgement. An item is a row when **any** of these holds:

- its decision is `declined`, `open`, `fork` or `answered`
- its severity is `Critical` or `High`
- it carries a scope note

The rest is labour — an applied low-severity fix that touched exactly what was flagged, a
check fixed, a conflict merged — and collapses into the tally.

Every thread, check and conflict the round touched ends as a row or inside the tally; the
tally counts are what show nothing was dropped.

## The block

Sections appear only when they hold something. `R<N>` is the round the item entered on.

```markdown
<!-- agent-ledger:start -->
## 🤖 Agent ledger · round 4 · 2 open

### Needs your call
- **R3 · codex · High** — [`api/views.py:88`](<link>) the lock sits inside the loop.
  Two shapes: hoist the lock, or batch the writes. Asked round 3, unanswered.

### Judgements — worth a second look
- **R2 · declined · CodeRabbit · Med** — [`api/serializers.py:41`](<link>) claims an N+1.
  The queryset already has `select_related('team')`; `test_roster_queries` pins the count.
- **R4 · applied · @ola · High** — [`api/models.py:12`](<link>) `owner` made nullable.
  *+2 files, +1 migration* — the PR carried no migration before this.

### Routine
14 nits applied (naming, formatting, docstrings) · 2 checks fixed (`test-api`, `lint`) ·
1 conflict merged
<!-- agent-ledger:end -->
```

## Writing it

Whoever holds the round writes the ledger, as the last action before reporting it.

The block is the ledger's own state: read it back to carry every earlier row forward
unchanged, and edit a row only when that item moved — a fork the user answered becomes
`answered: <choice>`, an open thread that got resolved takes its final decision. The
tally accumulates. A fresh worker rotated in mid-PR recovers the whole history this way.

Read the body fresh at write time, so a human edit made while the round ran survives:

```bash
gh pr view <PR> --repo <OWNER_REPO> --json body --jq .body > body.md
# replace the region between the markers, or append the block when they are absent
gh pr edit <PR> --repo <OWNER_REPO> --body-file body.md
```

The markers keep the write idempotent and leave the rest of the description — the
summary, the `closes #<id>` lines — untouched.

A failed ledger write is never fatal: note it in the round report and carry on.
