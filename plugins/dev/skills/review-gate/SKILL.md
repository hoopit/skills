---
name: review-gate
description: Run independent code reviewers. Use right before opening a PR, or before pushing to an open PR.
---

# Review Gate

Reviews the branch's committed changes against a fixed point — the repo's default branch, or on a
`light` pass only what the previous pass hasn't seen — then gates PR creation. The
always-on **independent** review prefers the **`mattpocock-skills:code-review` skill** (a two-axis
Standards + Spec reviewer that spawns its own cold sub-agents — genuinely independent eyes); without
it, a fresh independent subagent, and inline self-review only when no subagent tool is available.
**Codex** is a second, separate engine and is **required**: engine diversity is the point, so a pass
that cannot run it blocks rather than passing on one engine's word.

## Contract

Call after the fix is committed on the branch, **before** push/PR. One call is **one pass** — review,
fix, report — and the caller decides whether to run another (`ship` Step 6 works rounds on a budget).
Return exactly one verdict:

- **`PASS`** — every *valid* finding is fixed; anything left is Low/Medium that you deliberately
  skipped with a one-line justification. Say which **scope** ran and against which fixed point, and
  whether this pass **made fix commits**: fixed code no reviewer has seen is what the caller's next
  round is for. Caller opens the PR and pastes the gate notes into it.
- **`BLOCK: <reason>`** — **Codex did not run** (step 2), there is a **disputed Critical/High** finding
  (you judge it invalid/not worth fixing), or a valid Critical/High that isn't safe to fix here. You
  may **not** unilaterally dismiss a Critical/High. Caller must NOT open the PR — surface the blocking findings; unattended, the
  caller hands back per its own contract, which owns what an escalation writes to the tracker.

## Inputs

Set by the caller; unset, the pass is a full review of the whole branch.

- `SCOPE` *(default `full`)* — how much of the branch this pass puts in front of cold eyes.
  - **`full`** — fixed point `$DEFAULT_BRANCH`, both reviewer axes.
  - **`light`** — fixed point `REVIEWED_AT`, **Standards** axis only: a pass over the previous
    pass's fix commits.
- `REVIEWED_AT` — **required when `SCOPE=light`**: the commit `HEAD` stood at when the previous
  pass's reviewers ran, so everything after it is code no cold reviewer has seen. Missing it, run
  `full` rather than guessing a fixed point.
- `SPEC` *(optional)* — the originating issue / brief the change is meant to deliver, for the Spec
  axis (step 3).
- `CHALLENGE` *(optional)* — focus text for the **challenge**: Codex's adversarial review,
  which questions the approach and its assumptions rather than hunting defects, run
  beside its standard review. Every `full` pass runs it, on a focus derived from `SPEC`
  plus one line naming the shape the diff takes, unless the caller sets a sharper one —
  the shape taken and the alternatives set aside, or the mechanism being stepped back
  from. Findings earlier passes skipped on judgement go into the focus as settled ground,
  each with its reason. A `light` pass runs it only when `CHALLENGE` is set.

A `light` pass trusts the previous verdict on everything before `REVIEWED_AT`, which holds only
while a `full` pass covered it — so the caller owns which scope runs, and `ship` Step 6 carries
that policy.

## Steps

1. **Fixed point.** Resolve `$DEFAULT_BRANCH` from the repo's CLAUDE.md *Workflow skills config*
   (e.g. `master`), then set the base every reviewer in this pass diffs against:
   `REVIEW_BASE=$DEFAULT_BRANCH` under `full`, `REVIEW_BASE=$REVIEWED_AT` under `light`. Run from
   inside the worktree being reviewed. Every reviewer's findings land in one directory this pass
   owns, so set `GATE_DIR=$(mktemp -d "${TMPDIR:-/tmp}/review-gate.XXXXXX")` and keep it for the
   whole pass.
2. **External reviewer (Codex, required).** Run the bundled script:
   ```bash
   bash "$(find ~/.claude/plugins -path '*review-gate/scripts/run_external_reviewers.sh' | head -1)" "$REVIEW_BASE" --challenge "$CHALLENGE"
   ```
   Pass `--challenge` on every `full` pass and on a `light` pass that was given one; leave it
   off otherwise. It prints `codex=<ran|error|unavailable>[:file]` and, with a challenge,
   `codex_challenge=…` on its own line — read each `:file` for that reviewer's findings — and
   for either that did not run a `<name>_reason=<what went wrong>` line. `codex=error` or
   `codex=unavailable` **ends the pass**: the moment the script returns, print
   `🔴 Codex unavailable — <reason>`, fire `PushNotification` with that line, and return
   `BLOCK: Codex unavailable — <reason>` without running the rest of the pass. Nothing later in
   the pass lifts that block — a second engine is what the gate is for — and reviewing the branch
   on one engine spends a round the caller pays for again once Codex is back. Make Codex
   available (its own auth counts — `codex setup`) and run the gate again; the re-run is a whole
   pass, so nothing is lost by stopping here. A `codex_challenge` that fails while `codex` itself
   ran is a skipped reviewer, not a block: record it in the notes. The script is the whole
   external-reviewer step: Codex is the only external engine this gate runs locally.
3. **Independent review (always).** Prefer a cold, independent reviewer over grading your own
   work. Under `full` run both axes; under `light` run the **Standards** axis only — a pass over a
   handful of fix commits rarely re-opens the spec question, and a spec answer is what a `full` pass
   is for. Every pass puts cold eyes on the code it covers: `light` narrows the diff and the axes,
   leaving the independence intact.
   - **Preferred — invoke the `mattpocock-skills:code-review` skill** (the two-axis reviewer;
     use the namespaced name so it isn't confused with the built-in `/review`, which reviews an
     existing GitHub PR). Give it **`$REVIEW_BASE` as the fixed point** — it runs
     `git diff "$REVIEW_BASE"...HEAD`, spawns its own parallel **Standards** and **Spec** sub-agents
     (cold and independent by construction — don't hand it your implementation reasoning or the triage
     hypothesis), and returns `## Standards` + `## Spec` findings. Under `full`, hand it
     `SPEC` as the spec argument so the **Spec** axis runs; without a `SPEC`, and on every `light`
     pass, that axis does not run.
     **Spawn its sub-agents as `hoopit-dev:code-reviewer`.** The skill supplies the prompts, but
     *you* make the Agent calls — pass `subagent_type: "hoopit-dev:code-reviewer"` for both the
     Standards and Spec agents. That agent (`plugins/dev/agents/code-reviewer.md`) is pinned to
     Opus at high effort, so review quality never inherits a low `/effort` or a smaller session
     model. Only fall back to `general-purpose` with `model: "opus"` if the agent type isn't found.
     **Give each axis its own `FINDINGS_FILE`** — `$GATE_DIR/standards.md` and
     `$GATE_DIR/spec.md` — on the same prompt as the skill's brief. The reviewer writes its
     findings there and returns a `FINDINGS <path> · <n> findings` receipt; you read the file.
     That is what makes a lost report survivable (Notes), so pass the path even when you expect
     the report to arrive normally.
   - **Fallback — if that skill isn't installed** (e.g. only `hoopit-dev`, not `mattpocock-skills`):
     if the Agent/Task tool is available, spawn a fresh `hoopit-dev:code-reviewer` subagent (same
     pinned reviewer as above, `FINDINGS_FILE` included — `$GATE_DIR/independent.md`) to review the
     change **cold**: give it only the repo path and `git diff "$REVIEW_BASE"...HEAD`; otherwise
     review the diff yourself inline. For this fallback look for: correctness/logic bugs, security,
     data-integrity/regressions, missed edge cases, and repo conventions (read the relevant
     `$REPO/.claude/skills/*` for the area you touched).
   A subagent sitting at `idle` with no result has **not** failed, and a result that never
   arrives is recoverable — see Notes. Work that ladder rather than falling back.
   Note in the PR which mode ran (`mattpocock-skills:code-review` · independent subagent ·
   self-review) and at which scope.
   `mattpocock-skills:code-review` findings aren't pre-labelled by severity — assign each a severity when you
   triage (step 5): a missing/incorrect spec requirement, or any correctness/security/data-integrity
   issue, is usually Critical/High; baseline code-smells and style nits are Medium/Low.
4. **Aggregate + de-dup.** Merge findings from every reviewer that ran; collapse duplicates (same
   location + same issue → one finding, keep the highest severity and note which reviewers raised it).
5. **Triage each finding (judgment on all):**
   - **Valid → fix it.** Commit each fix separately (convention below). Re-reviewing the fixed
     code is the caller's next round, not a loop inside this pass.
   - **Fix the class, not the instance.** When a finding reveals a *class* of defect (one
     unvalidated field among several consumed, one call site among many, one write path of
     several), sweep for every instance of the class and fix them all — following it past the
     diff into unchanged fields, call sites, consumers, and sibling write paths, which carry
     the same defect while the gate still reads `PASS`. Narrow fixes are what spend the caller's
     round budget, and they tend to introduce the next round's findings. When the tail of the
     sweep is too large for this change, fix what this change touches and `BLOCK` on the rest
     (the too-large rule below).
   - **Challenge findings hold** only when a named caller or sequence reaches them
     (*Classifying an item* in [`../monitor-pr/LEDGER.md`](../monitor-pr/LEDGER.md)). One
     that holds is fixed; the rest are recorded as *challenged, not reached: <evidence>*.
     A `BLOCK` needs a disputed Critical/High of the standard kind.
   - **Invalid Low/Medium → skip**, recording a one-line reason (collected for the PR). A
     skip on judgement — the finding reads the code right and asks for a change deliberately
     not made — carries its reason in the code, and a finding raised again is that
     rationale failing: *What a decline carries* in the same file holds both rules.
   - **Invalid (disputed) Critical/High → `BLOCK`.** Record the finding + your reasoning. Do not skip it.
     The dispute rests on a claim, and *What a decline carries* puts the claim to the
     challenge first, with `$REVIEW_BASE` as the base: a broken claim is a fix, a surviving
     one is recorded beside the block as *claim challenged, stands: <evidence>*, which is
     what the user weighs.
   - **Valid but unsafe / too large to fix in this change → `BLOCK`** with that reason.
6. **Return the verdict:**
   - `PASS` + the scope and its fixed point + whether this pass made fix commits + a notes block
     for the PR: which reviewers ran (and which were skipped/unavailable), the challenge focus
     when one ran, findings fixed, findings skipped (with reasons), findings challenged and how
     they hold.
   - `BLOCK: <one-line reason>` + the blocking findings and your reasoning.

## Fix commit convention

One commit per fix, **no Jira key** in the message (review fixes aren't tied to a ticket):

```
<short imperative subject>

Reviewer finding (<reviewer> · <severity>):
<the finding as reported>

Solution:
<what was changed and why>
```

## Notes

- Codex is where the bug/security depth comes from — `mattpocock-skills:code-review` covers
  standards + spec — which is why a pass without it blocks instead of reporting reduced coverage.
  Lifting the block is the user's call, not the gate's: the caller asks (`ship` Step 6 offers
  *Open the PR anyway*), and a PR opened that way says in its body that Codex never ran.
- `mattpocock-skills:code-review` ships via the **`mattpocock-skills`** plugin
  (`mattpocock-skills@claude-plugins-official`). Without it the gate uses the cold-subagent fallback
  above — equivalent independence, minus the structured two-axis split.
- `codex` may be slow (minutes) and needs its own auth (codex setup); an auth/`error` result
  blocks the pass exactly as a missing install does — fix the auth and run the gate again. The
  script already retried it once, so `error` is a second failure, not a blip: re-running the
  gate on the spot buys a third attempt at best.
- **A reviewer subagent at `idle` with no result is not a dead one.** It usually means the work
  finished and the result has not been handed back yet, and delivery can lag the work by a long way.
  Spawning replacements or dropping to self-review on that signal throws away the independent axis
  while its findings are still in flight. Recover the review in this order, stopping at the first
  that yields it:
  1. **`SendMessage` the agent by name** and wait — a send resumes it from its transcript, so
     re-emitting the report costs it one round.
  2. **Read its `FINDINGS_FILE`.** The reviewer writes findings before it finishes, so the file
     stands whether or not the message ever lands. This is why step 3 passes the path.
  3. **Pull the report out of its transcript.** The reviewer's own transcript is at
     `~/.claude/projects/<cwd with / → ->/<this session id>/subagents/agent-<agentId>.jsonl`,
     where `agentId` came back in the spawn result. Extract only the assistant text — never
     `Read` the JSONL, whose tool traffic will swamp your context:

     ```bash
     jq -r 'select(.type=="assistant") | .message.content[]? | select(.type=="text") | .text' "$f"
     ```

  `TaskOutput` is not on this ladder: it is deprecated for agent tasks, and its output file is a
  symlink to that same JSONL.
