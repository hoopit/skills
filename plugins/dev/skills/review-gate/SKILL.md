---
name: review-gate
description: Run independent code reviewers (the mattpocock-skills two-axis /review + Codex) on the committed branch changes before a PR, aggregate and de-dup findings, fix what is valid, and BLOCK the PR (with notes) on any disputed Critical/High finding. Use right before opening a PR; handle-jira-issue Step 7 calls it. Codex is skipped if not installed locally; an independent review always runs (mattpocock-skills /review, else a cold subagent, else inline self-review).
---

# Review Gate

Runs up to two **independent** reviewers on the current branch's changes vs the repo's default
branch, then gates PR creation. An independent review always runs; **Codex runs only if
available locally** (skipped, not failed, when absent). Diversity is the point — Codex is
a separate engine, and the always-on review prefers the **`mattpocock-skills:code-review`
skill** (a two-axis Standards + Spec reviewer that spawns its own cold sub-agents — genuinely
independent eyes). If that skill isn't installed it falls back to a fresh independent subagent, and to
inline self-review only when no subagent tool is available.

## Contract

Call after the fix is committed on the branch, **before** push/PR. Return exactly one verdict:

- **`PASS`** — every *valid* finding is fixed; anything left is Low/Medium that you deliberately
  skipped with a one-line justification. Caller opens the PR and pastes the gate notes into it.
- **`BLOCK: <reason>`** — there is a **disputed Critical/High** finding (you judge it invalid/not worth
  fixing), or a valid Critical/High that isn't safe to fix here. You may **not** unilaterally dismiss a
  Critical/High. Caller must NOT open the PR — surface the blocking findings; in an unattended loop the
  caller takes its escape hatch (Jira comment + transition to **Escalated** + return `BLOCKED`).

## Steps

1. **Base branch.** Resolve `$DEFAULT_BRANCH` from the repo's CLAUDE.md *Workflow skills config*
   (e.g. `master`). Run from inside the worktree being reviewed.
2. **External reviewer (Codex, skip-if-unavailable).** Run the bundled script:
   ```bash
   bash "$(find ~/.claude/plugins -path '*review-gate/scripts/run_external_reviewers.sh' | head -1)" "$DEFAULT_BRANCH"
   ```
   It prints `codex=<ran|error|unavailable>[:file]`. Read the `:file` for Codex's findings. Treat
   `error`/`unavailable` as **skipped** — note it, never fail the gate on it.
   **Never run CodeRabbit locally** — it is not part of this gate.
3. **Independent review (always).** Prefer a cold, independent reviewer over grading your own work:
   - **Preferred — invoke the `mattpocock-skills:code-review` skill** (the two-axis reviewer;
     use the namespaced name so it isn't confused with the built-in `/review`, which reviews an
     existing GitHub PR). Give it **`$DEFAULT_BRANCH` as the fixed point** — it runs
     `git diff "$DEFAULT_BRANCH"...HEAD`, spawns its own parallel **Standards** and **Spec** sub-agents
     (cold and independent by construction — don't hand it your implementation reasoning or the triage
     hypothesis), and returns `## Standards` + `## Spec` findings. If you have the originating Jira
     issue / PRD (e.g. handle-jira-issue passes it through), give it to the skill as the spec argument
     so the **Spec** axis runs; otherwise that axis self-skips.
     **Spawn its sub-agents as `hoopit-dev:code-reviewer`.** The skill supplies the prompts, but
     *you* make the Agent calls — pass `subagent_type: "hoopit-dev:code-reviewer"` for both the
     Standards and Spec agents. That agent (`plugins/dev/agents/code-reviewer.md`) is pinned to
     Fable at high effort, so review quality never inherits a low `/effort` or a smaller session
     model. Only fall back to `general-purpose` with `model: "fable"` if the agent type isn't found.
   - **Fallback — if that skill isn't installed** (e.g. only `hoopit-dev`, not `mattpocock-skills`):
     if the Agent/Task tool is available, spawn a fresh `hoopit-dev:code-reviewer` subagent (same
     pinned reviewer as above) to review the change **cold** — give it only the repo path and `git diff "$DEFAULT_BRANCH"...HEAD`; otherwise review
     the diff yourself inline. For this fallback look for: correctness/logic bugs, security,
     data-integrity/regressions, missed edge cases, and repo conventions (read the relevant
     `$REPO/.claude/skills/*` for the area you touched).
   Note in the PR which mode ran (`mattpocock-skills:code-review` · independent subagent · self-review).
   `mattpocock-skills:code-review` findings aren't pre-labelled by severity — assign each a severity when you
   triage (step 5): a missing/incorrect spec requirement, or any correctness/security/data-integrity
   issue, is usually Critical/High; baseline code-smells and style nits are Medium/Low.
4. **Aggregate + de-dup.** Merge findings from every reviewer that ran; collapse duplicates (same
   location + same issue → one finding, keep the highest severity and note which reviewers raised it).
5. **Triage each finding (judgment on all):**
   - **Valid → fix it.** Commit each fix separately (convention below). After fixing, re-run the
     affected reviewer(s); loop until no new *valid* Critical/High remains.
   - **Fix the class, not the instance.** When a finding reveals a *class* of defect (one
     unvalidated field among several consumed, one call site among many, one write path of
     several), sweep for every instance of the class and fix them all — following it past the
     diff into unchanged fields, call sites, consumers, and sibling write paths, which carry
     the same defect while the gate still reads `PASS`. Narrow fixes are what re-trigger the
     next review round, and they tend to introduce the round's new findings. When the tail of
     the sweep is too large for this change, fix what this change touches and `BLOCK` on the
     rest (the too-large rule below).
   - **Invalid Low/Medium → skip**, recording a one-line reason (collected for the PR).
   - **Invalid (disputed) Critical/High → `BLOCK`.** Record the finding + your reasoning. Do not skip it.
   - **Valid but unsafe / too large to fix in this change → `BLOCK`** with that reason.
6. **Return the verdict:**
   - `PASS` + a notes block for the PR: which reviewers ran (and which were skipped/unavailable),
     findings fixed, findings skipped (with reasons).
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

- If only the always-on review ran (Codex unavailable), say so explicitly in the PR notes so the
  human knows review coverage was reduced — `mattpocock-skills:code-review` covers standards +
  spec, so bug/security depth leans on Codex when it runs.
- `mattpocock-skills:code-review` ships via the **`mattpocock-skills`** plugin
  (`mattpocock-skills@claude-plugins-official`). Without it the gate uses the cold-subagent fallback
  above — equivalent independence, minus the structured two-axis split.
- `codex` may be slow (minutes) and needs its own auth (codex setup); an auth/`error` result is
  treated as a skipped reviewer, not a gate failure.
