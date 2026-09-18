---
name: review-dispatch
description: Review how the backlog daemon's model/effort ladder is performing, and move at most one rung.
argument-hint: "[days] — window to read, default 14"
disable-model-invocation: true
---

# Review the dispatch ladder

`start-backlog-daemon` prices every issue off one table — `DISPATCH_MODEL` in `hoopit-board`,
a joint ladder over model **and** effort:

| Effort | XS | S | M | L | XL |
|---|---|---|---|---|---|
| | sonnet/medium | opus/medium | opus/high | fable/high | fable/xhigh |

It is strictly increasing, and that is the one invariant: **no rung may be priced under a
smaller one.** Checking effort alone is the wrong test — XS and S differ by model, not effort.

You are here to answer one question: *did a rung go too far down?* Not to retune the ladder,
not to add a tier. One move per run, or none.

## 1. Read the record

```bash
hoopit-board dispatches --since <days>        # default 14; add --repo owner/name per extra repo
```

Exit 1 means **nothing is attributed** — no PR in the window carries a rung. Say that and
stop; everything below is unreadable without it.

Attribution comes from the claim comment, which has carried `on \`<model>\` at \`<effort>\`
effort` only since **2026-09-18**. Anything merged before that is `(unattributed)`, and
hand-started work is unattributable for good — only the daemon writes the marker.

## 2. Refuse a verdict the numbers cannot carry

This is the step that earns the skill. The Unattended pool holds roughly 15 XS and 33 S
items, so a rung reaches single-digit PRs and stays there. **You can detect "clearly worse".
You cannot detect "slightly worse", ever.** Say which of the two a rung's row supports.

A rung with fewer than ~5 attributed PRs gets described, not judged. Report the count and
what it would take to read it, rather than a verdict dressed in a hedge.

## 3. Compare against the baseline, not against another rung

Rungs sit on different work — XS is not S — so rung-vs-rung says little. The population
baseline is what a rung is read against. Measured 2026-09-18 over 10 days, 95 merged PRs:
**471 fix commits, median 3 per PR, max 36, 25 PRs clean.** Re-read it from
`by_rung["(unattributed)"]` each run; it drifts.

The tripwires, in order of how loudly they speak:

- `released_total` — the agent gave up and handed the slot back. Any non-zero on a rung that
  has few PRs is worth a look on its own.
- `fix_commits_median` well above the baseline — the gate kept finding work.
- `clean_prs` near zero where the baseline clears a quarter.
- `pr-quiet` rows from `hoopit-board stale`, which is a stalled agent rather than a bad diff.

## 4. Distrust a clean rung

`fix_commits` counts findings the gate raised **and the agent fixed**. A finding skipped as
invalid, or dropped at challenge, writes no commit — so the count misses exactly how an
under-powered model fails: by generating findings that are not real. A rung that looks
*too* clean is the one to check by hand.

Open one PR from it and read the gate notes in the body — which reviewers ran, findings
skipped with reasons, findings challenged and how they held. That prose is the only record
of findings that never became commits. The reviewer is pinned Opus/high whatever wrote the
diff, so the instrument is constant across rungs; only the author varies.

## 5. Move at most one rung

A move is one step, on one tier, in `DISPATCH_MODEL`. After it:

- Re-check the invariant across the whole table, not just the tier you touched.
- Every level stays explicit. An unset effort silently inherits `~/.claude/settings.json`
  (`effortLevel`, and `modelSettings` per model) — which a dispatch must never depend on.
- Say in the commentary what the move was measured on.

Moving *up* needs the same evidence as moving down. "It felt risky" is what the ladder
already encodes.

## 6. Report

Per rung: PRs attributed, fix-commit median against the baseline, releases, and whether the
row supports a verdict or only a description. Then the move you made and what it rests on,
or that you made none and what would change that. Finally the attribution gap — how many PRs
in the window carried no rung, since that is the number that decides when this is worth
running again.
