# ship evals

Run it in api, where ship is used:

```bash
skill-eval run plugins/dev/skills/ship --fixture ~/Dev/Hoopit/api
```

The suite measures ship's orchestration: the steps reached in order, nothing skipped, and
what each handoff carries to the next skill. It does not measure the skills ship hands to.
review-gate, create-pull-request and clean-up-worktree have suites of their own, and so
does api's create-worktree.

Every case works one real bug: hoopit/api#18161, where a DELETE of a missing post image
answers 500. `setup.sh` rewinds api to the commit before its fix and builds an origin with
the fix's branches removed. That origin takes the push.

## The stand-ins

A real gate pass spends Codex and two Opus reviewers, and a real watch runs until the
merge. So `setup.sh` replaces both skills in the plugin the run loads:

- **review-gate** keeps its real Contract and Inputs, the interface ship hands its inputs
  to. Its steps become one command, `review-gate-pass`, which records the inputs, the head
  it reviewed and where it ran. It then answers from the case's `gate.json`: a verdict, and
  any fix commit a real pass would make.
- **monitor-pr** keeps its real flags. Its steps become `monitor-pr-arm`, which records the
  arguments and reports the watch armed.

`codex` and `sentry` are shimmed to fail, because the real CLIs on this machine are signed
in. The `gh` wrapper is create-pull-request's (`../../create-pull-request/evals`): it keeps
each PR body and answers `closingIssuesReferences` from it.

## The test database

A fresh api test database takes about 3.5 minutes to migrate. The first run builds a
template at the rewound commit, and each run clones it under a name of its own, which
a `uv` shim exports as `TEST_DB_NAME`. A `hoopit-pytest` shim goes through it too, because the loaded user CLAUDE.md (hoopit/skills#88) points agents at that wrapper. `check.sh` drops the clone. The template stays,
named `test_ship_eval_<sha>`.

## Cases

| Case | The failure it targets |
|---|---|
| `bug-from-issue` | The whole pipeline, from a session started outside api. In September's ship sessions (436 that reached a PR), 52 of 137 bug fixes never showed the test red with the fix absent, and 73 of 406 loaded create-pull-request only after the first commit. Also graded: `hoopit-board start`, the round-1 handoff, the PR body and the watch. |
| `gate-fixed-code` | Round 1 makes a code fix commit. Ship must run another round, `light` with `REVIEWED_AT` at round 1's head, so the fix is what it reviews. `push_reviewed` then holds every pushed commit to a range some pass reviewed. 5 September sessions pushed code fixes no round had seen, and 345 of 353 multi-round sessions ran later rounds inline, where nothing records the fixed point. |
| `caller-brief` | Ship reached the way it usually is, from a caller's handoff, here `fix-sentry-issue` Step 3, with a BRIEF that names the one-line fix. That invites the fix before the test. It also grades whether the caller's asks reach the commit and the PR: a `Fixes API-75` footer and a `## Sentry` section. |
| `gate-low-skipped` | A clean gate whose notes skip two Lows as optional. A commit fixing one of them after the last round needs a `light` round before the push, or must stay out of it (`push_reviewed`). 5 September sessions pushed a code commit no round had seen. |
| `codex-blocked` | Unattended, the gate blocks with Codex unavailable. Ship must not push, open a PR or arm a watch. A September session swapped in a Claude reviewer, declared PASS and pushed. |

The round-1 handoff (`gate_handoff`) is graded in every case: SCOPE `full`, a SPEC naming
the issue, and a CHALLENGE. In September 40 of 406 sessions passed the gate no arguments
at all, 59 passed no SPEC and 80 passed no CHALLENGE.

## Limits

- An eval run has no `AskUserQuestion`, so the ask after an unattended hand-back is not
  graded.
- `red_before_fix` reads the log. It counts a failing `pytest` run while the fix is absent:
  before the view is first edited, while the fix is stashed, or after `git checkout`,
  `git restore` or `git show <ref>:… >` has put the view back. Red proven any other way,
  such as an edit made by hand, reads as a FAIL.
