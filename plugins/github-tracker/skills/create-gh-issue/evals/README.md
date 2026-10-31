# create-gh-issue evals

Run it in a product repo, where the skill is used:

```bash
skill-eval run plugins/github-tracker/skills/create-gh-issue --fixture ~/Dev/Hoopit/api
```

Every case is graded from the tracker calls the run records (`grade.py`), never from what
the agent says. All cases share `mocks/`: a board snapshot with real titles, and REST answers
for the issues and PRs the prompts name. `setup.sh` adds the two shims the runner lacks.

| Case | The failure it targets |
|---|---|
| `repair-runs-from-local` | A command `manage-prod.py` can run from the reviewed branch, split into an implement issue and a gated run issue. LK: "Why do we need separate implement and run issues for something we can run from local?" |
| `repair-after-deploy` | The converse: a repair of rows a bug keeps writing until its PR ships is a second, `Ops` issue with a live `Gate: deployed` on that PR. |
| `bug-finding` | A bug a run turns up, held out of Ready though startable, or attached as a sub-issue of the item the run was dispatched for. |
| `p1-finding` | The same with a P1 security hole. Run it with `--base e2b8864570~1`: api fixed the hole in that commit, so at HEAD the agent rightly files nothing. |
| `sentry-fixed` | A "verify the Sentry issue stays quiet" follow-up filed, or the resolve held for a deploy, where resolving the Sentry issue in the next release is the whole job. |
| `covered-on-board` | A new issue for a finding an open board item already covers. |
| `drop-shim-is-code` | Code work that waits on something, typed as operational work. |
| `needs-decision` | `Needs decision` with no `## The decision` section: 18 of 159 such filings from 2026-09-15 to 2026-10-01. |
| `price-the-hunt` | A bug whose cause nobody has found, priced on its small eventual diff (hoopit/api#17310 went in at M). |
| `landing-mixed` | A landing's loose ends: an owed verification, a proposal and a point the merge settled, each needing a different answer. |
