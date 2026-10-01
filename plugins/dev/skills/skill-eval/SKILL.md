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
"$E" ab <skill-dir> --fixture <checkout>   # a plugin's skill, run in a product repo
"$E" compare <results-a> <results-b>
```

`"$E" <command> --help` lists the rest: `--case`, `--runs`, `--model`, `--effort`, `--slow`, `--keep`.

## Once per machine

The agent runs under a config dir of its own, never your `~/.claude`. Your CLAUDE.md, memory,
plugins and hooks would otherwise move the score, and nobody else could reproduce it.

1. Run `claude setup-token` in a terminal, and save the token to
   `~/.config/skill-eval/oauth-token` (chmod 600).
2. Run `"$E" setup --repo <checkout>` to install the plugins that repo enables into the eval
   config. Do it once for each repo whose plugins differ. Each run copies that store, with
   auto-update off, so a run never changes the version the next one measures.

`--as-me` runs under your own config instead. It is for debugging a suite before the token
exists, and its scores are yours alone.

## Reading a result

- **Model and effort.** Every run pins both: `opus` at `medium` effort unless the case or
  `--model` / `--effort` says otherwise. `compare` refuses two sets that differ in either,
  and a set taken before effort was recorded.
- **Noise.** `compare` marks a check that moved by two runs or more with `▲` or `▼`. A
  smaller move is noise at 3–5 runs. A suite cannot see a rare failure get rarer; it sees
  cases written so that the old skill fails often.
- **`source_repo_untouched` FAIL.** The agent wrote to your real checkout. Read that run's
  log before anything else.
- **Files.** Results go under `~/.cache/skill-evals/results/<repo>/<skill>/`, and each run's JSON names
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
- **Frontmatter.** It takes `runs`, `max_turns`, `timeout_seconds`, `model`, `effort` and `tags`.
  `expect_<name>` reaches the checks as `EVAL_EXPECT_<NAME>`.
- **`cwd: <path>`** starts the agent in `$EVAL_RUN_DIR/<path>` instead of the fixture, for a
  session that began in another repo. A `setup.sh` makes that dir, and the run fails without
  starting the agent if it is missing. The fixture is `$EVAL_RUN_DIR/<repo>`, so a clone at
  `$EVAL_RUN_DIR/api` reaches it as `../<repo>`. Both dirs are trusted.
- **`check.sh` grades state, not wording.** A tracker write is state: grade the recorded
  call, such as the `gh pr create` title, never what the agent says it did. It prints one line per check:
  `PASS <name>`, `FAIL <name> <reason>` or `SKIP <name> <reason>`.
  - It runs with the fixture as cwd.
  - Its environment has `EVAL_FIXTURE`, `EVAL_BASE` (the commit carrying the skill under
    test), `EVAL_LOG` (the agent's stream-json log), `EVAL_CALLS` (the shims' calls),
    `EVAL_RUN_DIR`, `EVAL_CWD` (where the agent started), `EVAL_SOURCE` and `EVAL_SLOW`.
  - Run slow checks only when `EVAL_SLOW=1`.
- **`setup.sh`** runs before the agent with the same environment. A non-zero exit fails
  the run without starting the agent.

The fixture is a `git clone --shared` of the repo at its default branch. Its origin carries
the real remote branches, and the skill under test is committed on top. `evals/` is
removed, so the agent never reads the answers.

A skill a plugin ships runs in the product repos, not in the plugin's own. Give it
`--fixture <checkout>`: the fixture clones that checkout with nothing committed over it,
and the agent loads the whole plugin from your working tree, or from `--ref`, through
`--plugin-dir`. The installed copy is disabled for the run, so the agent sees one copy of
each skill. The suite stays in the skill's own `evals/`, and `EVAL_SOURCE` is the
checkout.
