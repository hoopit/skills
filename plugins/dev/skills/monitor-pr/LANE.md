# The lane

A branch of [GREEN.md](GREEN.md), reached when the recommendation is to merge; steps and
paths named here are [SKILL.md](SKILL.md)'s.

The **lane judge** is a GitHub workflow, `lane-judge.yml`, that decides whether this head
merges with no human read (`auto`) or waits for one (`human`), and merges the `auto`
ones itself. It runs outside this session on purpose: the agent asking to merge is not
the one that rules on it. The session's part is to request the verdict and read it back.

**Request it**, once per head, after the briefing is in the PR description — a merged PR
keeps its briefing. A repo without the workflow has no lane: the first call answers 404,
and the merge question goes as GREEN.md says.

```bash
gh api repos/<OWNER_REPO>/contents/.github/workflows/lane-judge.yml --jq .name
gh workflow run lane-judge.yml --repo <OWNER_REPO> -f pr=<PR> -f head=<the GREEN line's full head sha>
```

**Read the verdict** off the `Lane judge` check run on that head. Wait for it with a
`Monitor` until-loop, ten minutes at most:

```bash
gh api "repos/<OWNER_REPO>/commits/<head sha>/check-runs?check_name=Lane%20judge" \
  --jq '.check_runs | max_by(.completed_at) | .conclusion, .output.title, .output.summary'
```

- `success` — **auto**: the workflow merged this head. Put no merge question. Say in chat
  that the lane judge cleared and merged it, and let the monitor's `PR_CLOSED
  state=MERGED` bring Step 4a.
- `neutral` — **human**: the merge question goes as GREEN.md says, recommendation
  unchanged, carrying the summary's vetoes verbatim. They are what the judge wants a
  person to look at before merging, so they belong beside *what to look at first*.
- no check run inside the ten minutes — **human**, and the question says the verdict
  never arrived, with the workflow run's URL when `gh run list --workflow
  lane-judge.yml --repo <OWNER_REPO> --limit 1` shows one.

A `human` verdict is an answer, and re-dispatching on the same head asks the same
question of the same diff. A new head earns a new request at its own `GREEN`.
