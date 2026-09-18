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

  A *guard against X* / *recheck Y* finding earns **the delta** before `applied`: the state
  that exists with the fix, written beside the state without it. Identical states put the row
  at `declined` — the finding is mis-aimed however real its mechanism, and a verified race
  feels settled, which is why nobody asks. Where the two differ only in **recoverability** —
  one visible to a cleanup sweep, one not — that decides it: name the consumers and say which
  state each can see.
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

## A finding on text

A **text finding** is one whose fix changes only wording — a comment, docstring, doc,
skill, log or error message — and nothing that executes.

- **It is `Low`, whatever the source badged it** — a Codex P1 citing a writing rule
  included — with *text finding* as the reason in `why`. Text that makes its reader act
  wrongly keeps the source's severity: a command in a runbook, a security or data claim,
  an instruction an agent follows.
- **Cut before you reword.** The finding is first a question of whether the text earns
  its place: delete it, or shrink it to what the code cannot say for itself, and reword
  only what survives. Record a cut as `applied`, and name the cut in `why`.
- **Sweep the rule once.** The first finding on a writing rule fixes every instance of
  it in the diff, in the same commit.
- **A fix explains itself in the commit message.** It adds two comment lines to the code
  at most, and only what the next reader cannot get from the code. Every sentence a round
  adds is a claim no test holds, and the next round's reviewers audit it.
- **A text-only round is the last round on text.** A round whose valid findings are all
  text findings fixes them in one commit and proceeds — the gate reports it clean, a PR
  round pushes it, and the tally records it as `text-only round R<k>`, which is how a
  later round knows. Text findings arriving after it are *not worth a round*.

## What a decline carries

A decline is the row a fresh reviewer re-raises, so it carries more than a `why`.

- **On a judgement, the reason goes into the code.** A finding that misreads the code —
  the N+1 a `select_related` already prevents — is answered by the code itself. A finding
  that reads the code right and asks for a change deliberately not made leaves the code
  looking wrong to every fresh reader, and the thread reply reaches none of them: write
  the reason at the flagged line, in one line, as documentation of the code — the
  invariant or the trade-off, in the present — and commit it with the round. The scope
  note says where: `rationale at <file:line>` — except in a closing round (*Closing the
  rounds*), which commits nothing. A finding raised again with its rationale
  in place means the rationale is failing or the decline is wrong: rewrite the comment so
  it answers the finding, or take the finding; a third raise takes it.
- **At Critical or High — a Codex P1 is one — the claim is challenged first.** The decline
  rests on a claim (*no caller reaches this*, *prod holds no such row*); put it to the
  challenge before the decline stands, with `GATE_SCRIPT` as your caller gave it — this file is
  opened with `Read`, so a `${CLAUDE_PLUGIN_ROOT}` written here would never be substituted:

  ```bash
  bash <GATE_SCRIPT> \
    <the branch's base> --challenge-only --challenge "<the finding, and the claim that makes it wrong here>"
  ```

  A challenge that breaks the claim turns the decline into a fix; one that does not goes
  into `why` as *claim challenged, stands: <evidence>*. A `codex_challenge_reason` in
  place of a findings file means the challenge never ran, and **an unchallenged claim is
  not a decline**: take the finding, or carry it to the user as a fork when taking it is
  wrong. Recording *claim challenged, stands* on a challenge that did not happen is the
  one thing this rule exists to prevent.
- **At Critical or High, `why` also carries the counterfactual** — what fixing it as
  asked would have cost (`~4 files across the serializer layer`). That is the
  justification for declining, so it belongs beside the decline.

## Closing the rounds

Rounds stop on their own one way: a **closing round**, which declines every item it
holds, commits nothing, and so opens no review of its own. It leaves the PR with nothing
open to review.

**Not worth a round.** A valid finding is ordinarily fixed. A `Med` or `Low` one may
instead be `declined — not worth a round`, with the evidence in `why`, when any of these holds:

- the round before took nothing above `Med` either — the reviewers have moved from defects
  to polish;
- it lands in code a round added (`fixes R<k>`) — the fix it asks for is one more patch on
  a patch;
- it is a text finding and a text-only round has run (*A finding on text*).

A `Critical` or `High` finding is fixed, or declined on its merits under *What a decline
carries*. Only a closing round declines as not worth a round: a round that fixes anything
pushes anyway, and fixes its `Med` and `Low` findings in the same push.

**A round closes** when, with every item decided before any is acted on, each thread
declines — on its merits or as not worth a round — and nothing else is outstanding: no
failing check, no conflict, no fork. It then:

- replies to and resolves every thread, and dismisses CodeRabbit's `CHANGES_REQUESTED`
  review as `review-github-comments` step 5b does;
- puts each judgement decline's rationale in the reply and `why`, with scope
  `rationale not in code` — a rationale commit is a push, and a push is another round;
- pushes nothing and starts no re-review;
- writes the ledger and reports that it closed.

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
whose rounds keep finding defects in their own fixes is churning, and
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
gh api repos/<OWNER_REPO>/pulls/<PR> --jq .body > body.md
# replace the region between the markers, or append the block when they are absent
gh api -X PATCH repos/<OWNER_REPO>/pulls/<PR> -F body=@body.md
```

The markers keep the write idempotent and leave the rest of the description — the
summary, the `closes #<id>` lines — untouched.

A failed ledger write is never fatal: note it in the round report and carry on.
