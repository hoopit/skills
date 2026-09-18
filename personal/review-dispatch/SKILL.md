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
hoopit-board dispatches --since <days> --limit 600   # default 14; add --repo owner/name per extra repo
```

A non-empty `truncated` means `--limit` ended the walk inside the window and the oldest
merges are missing: raise it and re-run before reading anything. `gate_judgement` other than
`ran` means some PRs carry fix commits only — say how many, and read the rework numbers as
covering the rest.

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
baseline is what a rung is read against, on two axes. Measured 2026-09-19 over 14 days,
283 merged PRs:

- **Fix commits:** 1183, median 2 per PR, max 36, 101 PRs clean.
- **Gate notes**, over the 196 PRs whose body carries them: **rework median 2.9** (mean 2.4)
  on a scale of 0 clean · 1 nits only · 2 one real defect · 3 repeated defects · 4 the
  approach was sent back; **20 PRs (10%)** where a Critical/High finding was disputed as
  invalid; **5** where the challenge broke a claim a decline rested on.

Re-read it from `population` each run; it drifts.

The tripwires, in order of how loudly they speak:

- `released_total` — the agent gave up and handed the slot back. Any non-zero on a rung that
  has few PRs is worth a look on its own.
- `fix_commits_median` or `rework_median` well above the baseline — the gate kept finding
  work. The rework score is the steadier of the two: one defect fixed in five commits and
  five defects fixed in one read the same on it.
- `clean_prs` near zero where the baseline clears a quarter.
- `pr-quiet` rows from `hoopit-board stale`, which is a stalled agent rather than a bad diff.

## 4. Distrust a clean rung

`fix_commits` counts findings the gate raised **and the agent fixed**. A finding skipped as
invalid, or dropped at challenge, writes no commit — so the count misses exactly how an
under-powered model fails: by generating findings that are not real, or by arguing real
ones away.

The gate notes in each PR body record those findings, and `dispatches` reads them across
the whole window. Per rung, beside the fix-commit median:

- `disputed_rate` — the share of judged PRs where a Critical/High finding was disputed.
- `challenge_broke_prs` — PRs where a decline did not survive the challenge.
- `flags: ["clean-but-disputed"]` — the fix-commit median is under the population's while
  the disputed rate is well over it. This is the rung that looks clean because it argued.

Name a flagged rung as such in the report. Then open its disputed PRs — each row's
`gate.disputed` at or above 0.5 — and read the notes: a flag is where to look, and whether
the disputes were right is yours to judge. `gate_judged` is the n behind every gate number;
step 2's floor of ~5 binds it as it binds `prs`.

The reviewer is pinned Opus/high whatever wrote the diff, so the instrument is constant
across rungs; only the author varies.

## 5. Move at most one rung

A move is one step, on one tier, in `DISPATCH_MODEL`. After it:

- Re-check the invariant across the whole table, not just the tier you touched.
- Every level stays explicit. An unset effort silently inherits `~/.claude/settings.json`
  (`effortLevel`, and `modelSettings` per model) — which a dispatch must never depend on.
- Say in the commentary what the move was measured on.

Moving *up* needs the same evidence as moving down. "It felt risky" is what the ladder
already encodes.

## 6. Report

Per rung: PRs attributed, fix-commit median and rework median against the baseline,
disputed rate, any flag, releases, and whether the row supports a verdict or only a
description. Then the move you made and what it rests on,
or that you made none and what would change that. Finally the attribution gap — how many PRs
in the window carried no rung, since that is the number that decides when this is worth
running again.
