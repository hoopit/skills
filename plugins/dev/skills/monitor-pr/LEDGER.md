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
  `conflict`, `challenge` for a finding of Codex's adversarial review — which argues
  against the change by design, so its finding **holds** only when a named caller or
  sequence reaches it; the rest are weighed and not held.
- **severity** — `Critical` / `High` / `Med` / `Low`, as the *source* framed it. Lower it
  only with the reason in `why`.
- **decision** — `applied`, `declined`, `open` (replied to, thread left unresolved),
  `fork` (waiting on the user), or `answered: <the user's choice>`. `applied (step back)`
  marks a fix whose shape a design check chose; `why` then carries the shapes weighed and
  the counterfactual.
- **fixes** — `fixes R<k>` when the finding lands in code round *k*'s fix added. This is
  the tag the step back's second-correction trigger reads, so it is never left off.
- **why** — one clause. For `declined`, name the evidence that makes the finding wrong
  here — the test, the line, the config — rather than asserting it.
- **scope** — facts, never a score, and only when the fix reached past the lines the
  source pointed at: `+2 files`, `+1 migration`, `+dep: <name>`, `public API change` — and
  `rationale at <file:line>` on a decline whose reason went into the code. A fix that
  changes exactly what was flagged carries no scope note.
- **link** — the thread or check URL. Paraphrase the source's claim in one clause and
  link it; the thread holds the full text.

## What a decline carries

A decline is the row a fresh reviewer re-raises, so it carries more than a `why`.

- **On a judgement, the reason goes into the code.** A finding that misreads the code —
  the N+1 a `select_related` already prevents — is answered by the code itself. A finding
  that reads the code right and asks for a change deliberately not made leaves the code
  looking wrong to every fresh reader, and the thread reply reaches none of them: write
  the reason at the flagged line, one or two lines, as documentation of the code — the
  invariant or the trade-off, in the present — and commit it with the round. The scope
  note says where: `rationale at <file:line>`. A finding raised again with its rationale
  in place means the rationale is failing or the decline is wrong: rewrite the comment so
  it answers the finding, or take the finding; a third raise takes it.
- **At Critical or High — a Codex P1 is one — the claim is challenged first.** The decline
  rests on a claim (*no caller reaches this*, *prod holds no such row*); put it to the
  challenge before the decline stands:

  ```bash
  bash "$(find ~/.claude/plugins -path '*review-gate/scripts/run_external_reviewers.sh' | head -1)" \
    <the branch's base> --challenge-only --challenge "<the finding, and the claim that makes it wrong here>"
  ```

  A challenge that breaks the claim turns the decline into a fix; one that does not goes
  into `why` as *claim challenged, stands: <evidence>*.
- **At Critical or High, `why` also carries the counterfactual** — what fixing it as
  asked would have cost (`~4 files across the serializer layer`). That is the
  justification for declining, so it belongs beside the decline.

## Which items earn a row

A row is earned by judgement. An item is a row when **any** of these holds:

- its decision is `declined`, `open`, `fork` or `answered`
- its severity is `Critical` or `High`
- it carries a scope note
- it carries a `fixes` tag — a chain of corrections has to be visible to be stopped

The rest is labour — an applied low-severity fix that touched exactly what was flagged, a
check fixed, a conflict merged — and collapses into the tally.

Every thread, check and conflict the round touched ends as a row or inside the tally; the
tally counts are what show nothing was dropped. The tally also carries the two counts
that show whether the rounds converge — **findings in code a round added** and **design
reversals** (a step back that replaced a shape or removed a mechanism) — because a PR
whose rounds keep finding defects in their own fixes is spending its budget on churn, and
the challenge's score — **challenge findings weighed** and how many **held** — so a
reviewer can see the judgements were tested, not just asserted.

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
- **R5 · applied (step back) · codex · P2 · fixes R4** — [`api/models.py:30`](<link>) the
  null-`owner` guard R4 added refused inserts. Shapes weighed: patch the guard for inserts,
  or drop it and let the DB constraint carry the rule — the constraint already does, so the
  guard went. Refusing inserts was the third case the guard would have needed.

### Routine
14 nits applied (naming, formatting, docstrings) · 2 checks fixed (`test-api`, `lint`) ·
1 conflict merged · 1 finding in code a round added · 1 design reversal ·
3 challenge findings weighed, 0 held
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
