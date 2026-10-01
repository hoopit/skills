---
name: skill-eval
description: Measure a skill change against its eval suite. Use when editing a skill that has an `evals/` folder, or writing one.
---

# skill-eval

A skill's suite runs the agent on fixed cases, each in a throwaway clone of the skill's repo,
and grades the **end state** the agent leaves: files, git state, a toolchain that works.
Run it on the skill as the default branch has it and on your edit. The change works when
the checks it targets go up and nothing else goes down.

```bash
E="${CLAUDE_PLUGIN_ROOT}/skills/skill-eval/scripts/skill-eval"
"$E" ab <skill-dir>                    # the default branch's version vs your working tree, then compare
"$E" run <skill-dir> [--ref <ref>]     # one version
"$E" compare <results-a> <results-b>
```

`"$E" <command> --help` lists the rest: `--case`, `--runs`, `--model`, `--slow`, `--keep`.

## Once per machine

The agent runs under a config dir of its own, never your `~/.claude`. Your CLAUDE.md, memory,
plugins and hooks would otherwise move the score, and nobody else could reproduce it.

1. Run `claude setup-token` in a terminal, and save the token to
   `~/.config/skill-eval/oauth-token` (chmod 600).
2. Run `"$E" setup --repo <checkout>` to install the plugins that repo enables into the eval
   config. Do it once for each repo whose plugins differ.

`--as-me` runs under your own config instead. It is for debugging a suite before the token
exists, and its scores are yours alone.

## Reading a result

- **Noise.** `compare` marks a check that moved by two runs or more with `▲` or `▼`. A
  smaller move is noise at 3–5 runs. A suite cannot see a rare failure get rarer; it sees
  cases written so that the old skill fails often.
- **`source_repo_untouched` FAIL.** The agent wrote to your real checkout. Read that run's
  log before anything else.
- **Files.** Results go under `~/.cache/skill-evals/results/<skill>/`, and each run's JSON names
  its log.
- **Cost.** Every run is a full agent session, so `ab` costs cases × runs × 2.
- **`--keep`.** It leaves every fixture on disk, installed dependencies included.

## Field report

`field-report` reads your Claude Code transcripts and prints, per skill, how real sessions
reach it and what it costs them: turns, wall time, tokens, failed calls, redos and the user
stepping in. Run it for a baseline before a change, and again a week after it ships.

```bash
F="${CLAUDE_PLUGIN_ROOT}/skills/skill-eval/scripts/field-report"
"$F" --since 2026-09-01 --until 2026-09-30 [--by week|repo] [--skill <name>] [--json]
```

- A use is a `Skill` call, a slash command or a read of the skill's `SKILL.md`. The skill
  listing never counts. Sessions that edit the skill, review-gate probes and eval runs are
  left out.
- A span runs from a use to the next skill or the end of the turn, so a skill the agent
  leaves without loading another carries the work after it. Compare a skill with itself
  over time, not with another skill.
- Claude Code deletes transcripts after `cleanupPeriodDays` (30 by default). Keep the
  `--json` output of a baseline you will need later.

## Writing a suite

```
<skill>/evals/check.sh                    grades every run (required)
<skill>/evals/setup.sh                    shapes every fixture before the agent starts
<skill>/evals/<case>/prompt.md            frontmatter, then the prompt
<skill>/evals/<case>/setup.sh, check.sh   the same, for one case
<skill>/evals/<case>/mocks/<tool>.json    answers for gh, hoopit-board, acli, linear-gql
```

- **Cases come from real sessions.** Mirror how the skill is actually reached (usually a
  parent skill's instruction, rarely a slash command), and target the failures already
  seen. A case nobody fails measures nothing.
- **The prompt carries everything.** Paste in what the agent would fetch, such as the issue
  text, and say where to stop. A fixture has no tracker access: `gh`, `hoopit-board`, `acli`
  and `linear-gql` are shims, and the push URL is dead.
- **Shims record, mocks answer.** Every shim call lands in `EVAL_CALLS`, one JSON line of
  `tool`, `argv`, `stdin` and `cwd`. Without `mocks/` every call fails. With it, a call
  answers from the first entry in `mocks/<tool>.json` whose `match` regex finds the
  space-joined argv: `[{"match": "^pr create", "stdout": "https://…/pull/7\n", "exit": 0}]`.
  A call nothing matches, a tool without a file included, fails with `no mock for: <argv>`.
- **Frontmatter.** It takes `runs`, `max_turns`, `timeout_seconds`, `model` and `tags`.
  `expect_<name>` reaches the checks as `EVAL_EXPECT_<NAME>`.
- **`check.sh` grades state, not wording.** A tracker write is state: grade the recorded
  call, such as the `gh pr create` title, never what the agent says it did. It prints one line per check:
  `PASS <name>`, `FAIL <name> <reason>` or `SKIP <name> <reason>`.
  - It runs with the fixture as cwd.
  - Its environment has `EVAL_FIXTURE`, `EVAL_BASE` (the commit carrying the skill under
    test), `EVAL_LOG` (the agent's stream-json log), `EVAL_CALLS` (the shims' calls),
    `EVAL_RUN_DIR`, `EVAL_SOURCE` and `EVAL_SLOW`.
  - Run slow checks only when `EVAL_SLOW=1`.
- **`setup.sh`** runs before the agent with the same environment. A non-zero exit fails
  the run without starting the agent.

The fixture is a `git clone --shared` of the repo at its default branch. Its origin carries
the real remote branches, and the skill under test is committed on top. `evals/` is
removed, so the agent never reads the answers.
