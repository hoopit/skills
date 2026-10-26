---
name: review-gate
description: Run independent code reviewers. Use right before opening a PR, or before pushing to an open PR.
---

# Review Gate

Reviews the branch's committed changes against a fixed point — the repo's default branch, or on a
`light` pass only what the previous pass hasn't seen — then gates PR creation. Both reviewers are
**required**, and a pass missing either blocks rather than reporting reduced coverage. The
**independent** review is the **`mattpocock-skills:code-review` skill** (a two-axis Standards + Spec
reviewer that spawns its own cold sub-agents — genuinely independent eyes). **Codex** is a second,
separate engine: engine diversity is the point, so a pass that cannot run it blocks rather than
passing on one engine's word.

## Contract

Call after the fix is committed on the branch, **before** push/PR. One call is **one pass** — review,
fix, report — and the caller runs another until one comes back `PASS` with no fix commits, or
with text-only ones (step 5).
Return exactly one verdict:

- **`PASS`** — every *valid* finding is fixed; anything left is Low/Medium that you deliberately
  skipped with a one-line justification. Say which **scope** ran and against which fixed point, and
  whether this pass **made fix commits** — none, `text-only`, or code: fixed code no reviewer has
  seen is what the caller's next round is for. Caller opens the PR and pastes the gate notes into it.
- **`BLOCK: <reason>`** — **`mattpocock-skills:code-review` is not installed** (step 1),
  **Codex did not run** (step 2), there is a **disputed Critical/High** finding
  (you judge it invalid/not worth fixing), or a valid Critical/High that isn't safe to fix here. You
  may **not** unilaterally dismiss a Critical/High. Caller must NOT open the PR — surface the blocking findings; unattended, the
  caller hands back per its own contract, which owns what an escalation writes to the tracker.

A `PASS` clears the branch to open or push, not to merge. The product repos require a
`merge-briefing` status on a ready PR, which passes once the description carries a merge
briefing for the PR's head whose Codex merge-readiness challenge ran — the read of the PR
as a whole that no pass of this gate gives. `monitor-pr`'s `GREEN` writes it; on a PR
nobody monitors, run the `merge-briefing` skill. Only PRs into the default branch are
judged, and a PR a bot opened passes without one.

## Inputs

Set by the caller; unset, the pass is a full review of the whole branch.

- `SCOPE` *(default `full`)* — how much of the branch this pass puts in front of cold eyes.
  - **`full`** — fixed point `origin/$DEFAULT_BRANCH`, both reviewer axes.
  - **`light`** — fixed point `REVIEWED_AT`, **Standards** axis only: a pass over the previous
    pass's fix commits.
- `REVIEWED_AT` — **required when `SCOPE=light`**: the commit `HEAD` stood at when the previous
  pass's reviewers ran, so everything after it is code no cold reviewer has seen. Missing it, run
  `full` rather than guessing a fixed point.
- `SPEC` *(optional)* — the originating issue / brief the change is meant to deliver, for the Spec
  axis (step 3).
- `CHALLENGE` *(optional)* — focus text for the **challenge**: Codex's adversarial review,
  which questions the approach and its assumptions rather than hunting defects, run
  beside its standard review. Its focus is derived from `SPEC` plus one line naming the
  shape the diff takes, unless the caller sets a sharper one — the shape taken and the
  alternatives set aside, or the mechanism being stepped back from. Findings earlier
  passes skipped on judgement go into the focus as settled ground, each with its reason.
  A `light` pass runs the challenge only when `CHALLENGE` is set; a `full` pass runs it
  on `CHALLENGE_AT`.
- `CHALLENGE_AT` *(optional)* — the commit `HEAD` stood at when the **challenge** last
  ran, and the fixed point that keys it. Unset, nothing has challenged this branch and a
  `full` pass runs one. Set, a `full` pass runs the challenge only when the diff
  `CHALLENGE_AT..HEAD` **moves the shape** — it introduces a mechanism or a file the last
  challenge never saw, it redesigns rather than patches, or it has reached ~50 changed
  lines. Otherwise the challenge does not run and the notes say *shape unchanged since
  `<CHALLENGE_AT>`*. Keying on the last **challenge** rather than the last round is what
  catches a shape that arrives in ten commits none of which moves it alone.
- `CODEX_MODEL`, `CODEX_EFFORT` *(optional)* — override the model and reasoning effort step 2
  picks for Codex's **standard review**. The challenge takes neither: the script pins its model
  and effort, and only `CODEX_CHALLENGE_MODEL` / `CODEX_CHALLENGE_EFFORT` replace a pinned pair
  Codex no longer accepts.
- `PRIOR_ROUNDS` *(optional)* — one line per earlier pass: the highest severity among its valid
  findings. It is what lets this pass close (step 5).

A `light` pass trusts the previous verdict on everything before `REVIEWED_AT`, which holds only
while a `full` pass covered it — so the caller owns which scope runs, and `ship` Step 6 carries
that policy.

## Steps

1. **Fixed point.** First confirm `mattpocock-skills:code-review` is among your available skills.
   When it is not, return `BLOCK: mattpocock-skills:code-review not installed — claude plugin
   install mattpocock-skills@claude-plugins-official --scope project` before opening anything:
   step 3 has no other independent reviewer, and finding that out after Codex's minutes-long
   run wastes them. Then resolve `$DEFAULT_BRANCH` from the repo's AGENTS.md *Workflow skills config*
   (e.g. `master`), then set the base every reviewer in this pass diffs against:
   `git fetch` and `REVIEW_BASE=origin/$DEFAULT_BRANCH` under `full`, `REVIEW_BASE=$REVIEWED_AT`
   under `light`. **The remote-tracking ref carries the fixed point**, because a worktree branched
   from the remote leaves the local branch behind, and that stale merge-base widens the reviewed
   diff by every unrelated upstream commit. Run from inside the worktree being reviewed. Every
   reviewer's findings land in one directory this pass
   owns, so open it and keep it for the whole pass — step 6 closes it:
   ```bash
   GATE_DIR=$(bash "${CLAUDE_PLUGIN_ROOT}/skills/review-gate/scripts/gate_dir.sh" open)
   ```

   **A text-only diff** — every path in `git diff --name-only "$REVIEW_BASE"...HEAD` is prose:
   `*.md`, `*.mdx`, `*.txt`, `*.rst` — runs Codex's standard review and the **Standards** axis
   alone, whatever `SCOPE` says: no `--challenge`, no Spec axis. There is no approach to argue
   with and no behaviour to hold to a spec, and both reviewers, handed prose, review the prose.
   A workflow, a config file or a script is code. Say in the notes that the diff was text-only.
2. **External reviewer (Codex, required).** Run the bundled script:
   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/skills/review-gate/scripts/run_external_reviewers.sh" "$REVIEW_BASE" --out "$GATE_DIR" --challenge "$CHALLENGE" --model "$MODEL" --effort "$EFFORT" $SKIP_DOCS_ONLY
   ```
   Pass `--challenge` on a pass whose challenge runs (Inputs); leave it off otherwise. It
   prints `codex=<ran|cached|skipped|error|unavailable>[:file]` and, with a challenge,
   `codex_challenge=…` on its own line — read each `:file` for that reviewer's findings — and
   for either that did not run a `<name>_reason=<what went wrong>` line. `codex=error` or
   `codex=unavailable` **ends the pass**: the moment the script returns, print
   `🔴 Codex unavailable — <reason>`, fire `PushNotification` with that line, and return
   `BLOCK: Codex unavailable — <reason>` without running the rest of the pass, closing the gate
   dir first (step 6). Nothing later in
   the pass lifts that block — a second engine is what the gate is for — and reviewing the branch
   on one engine spends a round the caller pays for again once Codex is back. Make Codex
   available (its own auth counts — `codex setup`) and run the gate again; the re-run is a whole
   pass, so nothing is lost by stopping here. A `codex_challenge` that fails while `codex` itself
   ran is a skipped reviewer, not a block: record it in the notes. A run printing no `codex=`
   line at all never started — read it as `unavailable`, with whatever the shell said as the
   reason. The script is the whole external-reviewer step: Codex is the only external engine
   this gate runs locally.

  **`cached` reads exactly as `ran`** — same reviewer, same tree, findings the script
   kept from the run that first saw it; read its `:file` and treat the findings as this pass's.
   It answers the re-ask — a pass re-run after a block settled without touching the code, a round
   re-armed after an interruption — not a first review: no tree ever passes this step unreviewed.
   A fresh run would be a second *sample*, which does catch what a first missed, and that is the
   whole of what reuse trades away; `--no-cache` buys it back when a pass wants it.
   **`skipped`** is neither: the diff held nothing but `docs/` and `*.md`, so no reviewer was
   spent on it. It does not block — there is no code for a second engine to read — and the notes
   say the external step skipped and why.

   **The model and effort follow the scope, not a judgement about the diff:**

   | Scope   | `MODEL`                        | `EFFORT`                   |
   |---------|--------------------------------|----------------------------|
   | `full`  | `${CODEX_MODEL:-gpt-6.1-sol}`  | `${CODEX_EFFORT:-high}`    |
   | `light` | `${CODEX_MODEL:-gpt-6-luna}`   | `${CODEX_EFFORT:-medium}`  |

   The gate names both so a local `~/.codex/config.toml` never decides how hard a branch is read.
   `light` runs lighter because it reviews only the previous pass's fix commits, behind a `full`
   pass that cleared everything before `REVIEWED_AT` — the same reason it drops the Spec axis.
   Nobody — not the caller, not this gate — rules a change "simple" and reviews it more cheaply for
   it: that judgement is what the review exists to test, and the passes most likely to be
   misjudged are the ones it would weaken. A missing flag, a model Codex doesn't know, or an effort
   that model does not take ends as `codex=error`, and the pass blocks. For the next pass, set
   `CODEX_MODEL` or `CODEX_EFFORT` to a pair Codex accepts; when it is a pinned default that
   went away, update this table. `~/.codex/models_cache.json` lists candidates but not every
   model Codex accepts — it omits `gpt-6.1-sol` — so confirm a pair with a one-line
   `codex exec -m <model> -c model_reasoning_effort=<effort>` run, not by its absence there.

   **`SKIP_DOCS_ONLY`**: `--skip-docs-only` under `light`, empty under `full`. On a `light` pass
   the diff *is* the fix commits, so a docs-only one has nothing for a code reviewer; on a `full`
   pass the diff is a whole branch, and in a docs or skills repo the Markdown is the code, which
   would leave that repo with no external reviewer at all.
3. **Independent review (always).** Prefer a cold, independent reviewer over grading your own
   work. Under `full` run both axes; under `light` run the **Standards** axis only — a pass over a
   handful of fix commits rarely re-opens the spec question, and a spec answer is what a `full` pass
   is for. Every pass puts cold eyes on the code it covers: `light` narrows the diff and the axes,
   leaving the independence intact.
   **A `light` pass leaves wording out.** Add to its Standards brief: *wording of comments and
   docs is out of scope, except text that contradicts the code in this diff or would make
   its reader act wrongly.* Text was reviewed
   under `full`, and a fresh reader always finds another sentence to improve.
   **The reviewed worktree is shared, so it stays read-only.** The axes and Codex read it at
   once, and a reviewer that reverts a file there hands every peer a tree that is neither the
   branch nor the base — a measurement taken in that window is false, and nothing downstream
   can tell. Give each reviewer its own `PROBE_DIR` on the same prompt as its brief —
   `$GATE_DIR/standards-probe`, `$GATE_DIR/spec-probe` — where
   it builds a private worktree the first time a probe has to change files (the agent
   definition holds how), so only an axis that probes pays for the checkout. A `PROBE_DIR`
   is always inside `$GATE_DIR`: closing the dir is what removes the worktree, and one built
   anywhere else outlives the pass.
   - **Invoke the `mattpocock-skills:code-review` skill** (the two-axis reviewer;
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
   A subagent sitting at `idle` with no result has **not** failed, and a result that never
   arrives is recoverable — see Notes. Work that ladder rather than reviewing the diff yourself.
   Note in the PR at which scope the axes ran.
   `mattpocock-skills:code-review` findings aren't pre-labelled by severity — assign each a severity when you
   triage (step 5): a missing/incorrect spec requirement, or any correctness/security/data-integrity
   issue, is usually Critical/High; baseline code-smells and style nits are Medium/Low.
4. **Aggregate + de-dup.** Merge findings from every reviewer that ran; collapse duplicates (same
   location + same issue → one finding, keep the highest severity and note which reviewers raised it).
5. **Triage each finding (judgment on all):**
   - **Valid → fix it.** Commit each fix separately (convention below). Re-reviewing the fixed
     code is the caller's next round, not a loop inside this pass. *A finding on text* in
     [`../monitor-pr/LEDGER.md`](../monitor-pr/LEDGER.md) holds what a text finding is, its
     severity, and how it is fixed. When every valid finding of the pass is one, fix them in
     one commit and report the fix commits as `text-only`: the caller runs no round over them.
   - **Fix the class, not the instance.** When a finding reveals a *class* of defect (one
     unvalidated field among several consumed, one call site among many, one write path of
     several), sweep for every instance of the class and fix them all — following it past the
     diff into unchanged fields, call sites, consumers, and sibling write paths, which carry
     the same defect while the gate still reads `PASS`. Narrow fixes are what make the caller's
     rounds churn, and they tend to introduce the next round's findings. When the tail of the
     sweep is too large for this change, fix what this change touches and `BLOCK` on the rest
     (the too-large rule below).
   - **The sweep's ceiling is the defect.** When a swept file turns out to be wrong in its own
     right — not merely missing the guard — fix the guard and file the rewrite as its own work
     item, however correct and load-bearing that rewrite would be. Folded in, it is reviewed at
     someone else's change's attention, and it is the half the rounds then spend themselves on.
     The tell is the round tally: one file yielding a finding every round while the rest of the
     diff has converged means the change is carrying two pieces of work. Filing it does not
     block, unlike the sweep too large to finish here: the guard is all this change owed, so
     the pass may still `PASS`.
   - **A closing pass.** Decide every finding before fixing any. When each one declines — on its
     merits or as *not worth a round*, judged against `PRIOR_ROUNDS` and the earlier passes' fix
     commits — the pass closes: *Closing the rounds* in
     [`../monitor-pr/LEDGER.md`](../monitor-pr/LEDGER.md) holds when a finding qualifies and what
     a closing pass skips. It returns `PASS` with no fix commits, each decline in the notes.
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
6. **Close the gate dir, then return the verdict.** Every return closes it — `PASS`, `BLOCK`,
   step 2's early return, a hand-back — once you have read the findings in it:
   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/skills/review-gate/scripts/gate_dir.sh" close "$GATE_DIR"
   ```
   The pass is done when `$GATE_DIR` is gone and the verdict is returned. Closing removes every
   probe worktree inside it along with its registration in the repo, freeing a probe's ~60k files
   now; the plugin's session hooks sweep a pass that never reaches this step, at session end.
   - `PASS` + the scope and its fixed point + whether this pass made fix commits + a notes block
     for the PR: which reviewers ran (and which were skipped/unavailable), the challenge focus
     when one ran, findings fixed, findings skipped (with reasons), findings challenged and how
     they hold. Carry `CHALLENGE_AT` in the verdict — this pass's `REVIEWED_AT` when the
     challenge ran, the sha the caller gave when it did not — because a caller that loses it
     re-challenges a settled shape.
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
  (`mattpocock-skills@claude-plugins-official`). Without it step 1 blocks: there is no in-house
  substitute, and self-review is not independent review.
- **The Codex CLI backs the external step.** The standard review runs as `codex exec review`, the
  challenge as a `codex exec` turn in a read-only sandbox, on the adversarial prompt and output
  schema vendored under `challenge/` from the codex plugin; its findings are that schema's JSON.
  Without the CLI both report `unavailable`. Both take minutes and need Codex's own auth
  (`codex setup`), and an auth `error` blocks exactly as a missing install does — fix it and run the gate again. The
  script already retried once, so `error` is a second failure: re-running the gate on the spot
  buys a third attempt at best.
- **Stop a Codex run by killing its pid, one at a time.** `TaskStop` on the shell that launched
  the script leaves Codex running, so read the pid off `ps` and kill that:

  ```bash
  ps -eo pid,args | grep 'codex exec review --base'   # the standard review
  ps -eo pid,args | grep 'codex exec .*--output-schema' # the challenge
  ```

  Match the one you mean, or you take the other down with it; `readlink /proc/<pid>/cwd` tells
  this worktree's run from another session's. Killing by pattern
  instead — `pkill -f` — is wrong twice over: every concurrent session's review matches the same
  pattern, and the `bash -c` wrapper running the `pkill` carries the pattern in its own argv, so
  it kills its caller too (the shell reports 144) whatever the escaping.
- **A reviewer subagent at `idle` with no result is not a dead one.** It usually means the work
  finished and the result has not been handed back yet, and delivery can lag the work by a long way.
  Spawning replacements or reviewing the diff yourself on that signal throws away the independent axis
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
