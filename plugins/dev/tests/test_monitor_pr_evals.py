#!/usr/bin/env python3
"""Pins the fake GitHub monitor-pr's suite runs against. Run it by hand after editing
`plugins/dev/skills/monitor-pr/evals/` or the scripts it answers:

    python3 plugins/dev/tests/test_monitor_pr_evals.py

Every case starts the real `watch-pr.sh` against `fake_github.py`, so the fake has to answer
the watch, `pr-state.sh` and `pr-labels.sh` the way GitHub does: a clean head fires GREEN on
the first poll, a thread or a conflict fires ROUND, a push moves the head, and labels, draft
and the body persist between calls.
"""
import atexit, json, os, pathlib, shutil, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent / "skills" / "monitor-pr"
EVALS = ROOT / "evals"
SCRIPTS = ROOT / "scripts"
BRANCH, PR = "feature-x", 4242


def sh(*args, cwd=None, env=None, check=True):
    return subprocess.run(args, cwd=cwd, env=env, check=check, capture_output=True, text=True).stdout


class Run:
    """A run dir as setup.sh leaves it: an origin with master and the PR branch, a clone, the fake."""

    def __init__(self, **case):
        self.dir = pathlib.Path(tempfile.mkdtemp(prefix="monitor-pr-fake-", dir=pathlib.Path.home() / ".cache"))
        atexit.register(shutil.rmtree, self.dir, True)
        git_env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                   "GIT_COMMITTER_EMAIL": "t@t"}
        self.clone = self.dir / "repo"
        sh("git", "init", "-q", "-b", "master", str(self.clone))
        (self.clone / "a.txt").write_text("one\n")
        sh("git", "add", ".", cwd=self.clone)
        sh("git", "commit", "-qm", "base", cwd=self.clone, env=git_env)
        sh("git", "clone", "-q", "--bare", str(self.clone), str(self.dir / "origin.git"))
        sh("git", "remote", "add", "origin", str(self.dir / "origin.git"), cwd=self.clone)
        sh("git", "checkout", "-qb", BRANCH, cwd=self.clone)
        (self.clone / "a.txt").write_text("two\n")
        sh("git", "commit", "-qam", "change", cwd=self.clone, env=git_env)
        sh("git", "push", "-q", "origin", BRANCH, cwd=self.clone)
        self.git_env = git_env
        self.head = sh("git", "rev-parse", "HEAD", cwd=self.clone).strip()
        (self.dir / "github").mkdir()
        (self.dir / "shims").mkdir()
        self.calls = self.dir / "calls.jsonl"
        state = {"repo": "hoopit/api", "base": "master", "initial_head": self.head,
                 "started_at": "2026-10-02T00:00:00Z", "updated_at": "2026-10-02T00:00:00Z",
                 "pr": {"number": PR, "title": "t", "body": "body", "draft": True, "labels": [], "state": "open",
                        "head_ref": BRANCH},
                 "checks": [{"name": "lint", "conclusion": "success"}],
                 "statuses": [{"context": "codex-review", "state": "success"}],
                 "new_head_checks": [{"name": "lint", "conclusion": "success"}],
                 "new_head_statuses": [{"context": "codex-review", "state": "success"}],
                 "threads": [], "issue_comments": [], "issues": {}, "closing_issues": [], "required_checks": [],
                 "conflicting": False, "repo_labels": ["monitored", "agent-working"], "merge_after_polls": None}
        for k, v in case.items():
            if k == "pr":
                state["pr"].update(v)
            else:
                state[k] = v
        text = json.dumps(state).replace("{HEAD}", self.head)
        (self.dir / "github" / "state.json").write_text(text)
        gh = self.dir / "shims" / "gh"
        gh.write_text(f"#!{sys.executable}\nimport sys\nsys.dont_write_bytecode = True\n"
                      f"sys.path.insert(0, {str(EVALS)!r})\nimport fake_github\n"
                      f"fake_github.main({str(self.dir)!r}, {str(self.calls)!r})\n")
        gh.chmod(0o755)
        self.env = {**os.environ, "PATH": f"{self.dir / 'shims'}:{os.environ['PATH']}",
                    "XDG_STATE_HOME": str(self.dir / "state"), "GATE_CHECKS": "codex-review,CodeRabbit"}

    def gh(self, *args, check=True):
        return sh("gh", *args, cwd=self.clone, env=self.env, check=check)

    def state(self):
        return json.loads((self.dir / "github" / "state.json").read_text())

    def watch(self, seconds=6, **env):
        """The watch's lines over a few polls one second apart."""
        p = subprocess.run(["timeout", str(seconds), "bash", str(SCRIPTS / "watch-pr.sh"), "hoopit/api", str(PR), "1"],
                           cwd=self.clone, env={**self.env, **env}, capture_output=True, text=True)
        return p.stdout.splitlines()


def coderabbit(head):
    return [{"id": 1, "user": {"login": "coderabbitai[bot]"}, "body":
             "<!-- This is an auto-generated comment: summarize by coderabbit.ai -->\n"
             f"<!-- final_review_risk_coverage {{\"coveredCommitId\":\"{head}\"}} -->"}]


def thread():
    return {"id": "PRRT_t1", "path": "a.txt", "line": 1, "resolved": False,
            "comments": [{"id": 77, "author": "coderabbitai[bot]", "body": "nit"}]}


def test_clean_head_is_green_on_first_poll():
    r = Run(issue_comments=coderabbit("{HEAD}"))
    lines = r.watch(3)
    assert lines and lines[0] == f"GREEN head={r.head}", lines


def test_statuses_read_as_the_watch_buckets_them():
    r = Run(statuses=[{"context": "codex-review", "state": "pending"}, {"context": "ci", "state": "failure"}])
    out = sh("bash", "-c", f"source {SCRIPTS / 'gh-pr-api.sh'}; pr_checks hoopit/api {r.head}", cwd=r.clone, env=r.env)
    rows = sorted(line.split("\t")[:2] for line in out.splitlines())
    assert rows == [["fail", "ci"], ["pass", "lint"], ["pending", "codex-review"]], rows


def test_a_cancelled_or_timed_out_check_fails_and_fires_a_round():
    r = Run(issue_comments=coderabbit("{HEAD}"), checks=[{"name": "lint", "conclusion": "success"},
            {"name": "test", "conclusion": "cancelled"}, {"name": "e2e", "conclusion": "timed_out"}])
    out = sh("bash", "-c", f"source {SCRIPTS / 'gh-pr-api.sh'}; pr_checks hoopit/api {r.head}", cwd=r.clone, env=r.env)
    rows = sorted(line.split("\t")[:2] for line in out.splitlines())
    assert rows == [["fail", "e2e"], ["fail", "test"], ["pass", "codex-review"], ["pass", "lint"]], rows
    lines = r.watch(3)
    assert lines and lines[0].startswith(f"ROUND head={r.head[:7]}") and "failing=e2e,test " in lines[0], lines
    assert not any(l.startswith("GREEN") for l in lines), lines


def test_a_pending_team_approval_does_not_hold_green():
    r = Run(issue_comments=coderabbit("{HEAD}"), statuses=[
        {"context": "codex-review", "state": "success"},
        {"context": "web-approval", "state": "pending", "description": "Waiting for an approval from @hoopit/web"}])
    lines = r.watch(3)
    assert lines and lines[0] == f"GREEN head={r.head}", lines


def test_a_failed_team_approval_is_no_failing_check():
    r = Run(issue_comments=coderabbit("{HEAD}"), statuses=[
        {"context": "codex-review", "state": "success"}, {"context": "web-approval", "state": "failure"}])
    out = sh("bash", "-c", f"source {SCRIPTS / 'gh-pr-api.sh'}; pr_checks hoopit/api {r.head}", cwd=r.clone, env=r.env)
    assert "web-approval" not in out, out
    assert sh("bash", str(SCRIPTS / "pr-state.sh"), "hoopit/api", str(PR), cwd=r.clone, env=r.env) == \
        "threads=\nfailing=\nconflicting=0\n"
    lines = r.watch(3)
    assert lines and lines[0] == f"GREEN head={r.head}", lines


def test_a_gate_stuck_pending_goes_green_once_gate_timeout_elapses():
    stuck = [{"context": "codex-review", "state": "pending", "description": "Codex review started"}]
    r = Run(issue_comments=coderabbit("{HEAD}"), statuses=stuck)
    assert r.watch(4, GATE_TIMEOUT="60") == []
    r = Run(issue_comments=coderabbit("{HEAD}"), statuses=stuck)
    assert r.watch(6, GATE_TIMEOUT="2") == [f"GREEN head={r.head} pending_gates=codex-review"]


def stuck(age=2000, before=(), **case):
    pending = {"context": "codex-review", "state": "pending", "age": age, "description": "Waiting for Codex (#4242)"}
    return Run(issue_comments=coderabbit("{HEAD}"), statuses=[*before, pending], **{"rereview_goes_pending": True, **case})


def dispatches(r):
    return [d["workflow"] for d in r.state().get("dispatches", [])]


def test_a_stale_pending_review_is_re_requested_a_bounded_number_of_times():
    r = stuck()
    lines = r.watch(8, REREQUEST_AFTER="2", GATE_TIMEOUT="60")
    assert lines == [f"REREQUESTED head={r.head} gate=codex-review request=1/2",
                     f"REREQUESTED head={r.head} gate=codex-review request=2/2",
                     f"GATE_STUCK head={r.head} gate=codex-review requests=2 last_verdict=none"], lines
    assert dispatches(r) == ["codex-review-manual.yml"] * 2


def test_a_healthy_review_is_left_alone_while_it_runs():
    r = stuck(age=30)
    assert r.watch(4, REREQUEST_AFTER="1500", GATE_TIMEOUT="60") == []
    assert dispatches(r) == []


def test_re_requests_keep_their_count_across_a_resumed_and_a_fresh_watch():
    r = stuck()
    assert len(r.watch(2, REREQUEST_AFTER="3", GATE_TIMEOUT="60")) == 1
    assert r.watch(3, REREQUEST_AFTER="3", GATE_TIMEOUT="60", WATCH_RESUME="1") == []
    lines = r.watch(8, REREQUEST_AFTER="1", GATE_TIMEOUT="60")
    assert lines == [f"REREQUESTED head={r.head} gate=codex-review request=2/2",
                     f"GATE_STUCK head={r.head} gate=codex-review requests=2 last_verdict=none"], lines
    assert len(dispatches(r)) == 2


def test_a_re_request_that_answers_clears_a_green_held_for_the_gate():
    r = stuck(age=0, rereview_statuses=[{"context": "codex-review", "state": "success", "description": "Codex reviewed it (#4242)"}])
    lines = r.watch(6, REREQUEST_AFTER="2", GATE_TIMEOUT="0")
    assert lines == [f"GREEN head={r.head} pending_gates=codex-review",
                     f"REREQUESTED head={r.head} gate=codex-review request=1/2",
                     f"GREEN head={r.head} cleared=codex-review"], lines


def test_a_gate_clearing_after_green_survives_a_resume_and_fires_once():
    r = Run(issue_comments=coderabbit("{HEAD}"), statuses=[{"context": "codex-review", "state": "pending"}])
    assert r.watch(2, GATE_TIMEOUT="0") == [f"GREEN head={r.head} pending_gates=codex-review"]
    assert r.watch(2, GATE_TIMEOUT="0", WATCH_RESUME="1") == []
    state = r.state()
    state["statuses"] = [{"context": "codex-review", "state": "success"}]
    (r.dir / "github" / "state.json").write_text(json.dumps(state))
    assert r.watch(3, GATE_TIMEOUT="0", WATCH_RESUME="1") == [f"GREEN head={r.head} cleared=codex-review"]


def test_a_failed_dispatch_stops_asking_and_names_the_pass_the_pending_replaced():
    passed = {"context": "codex-review", "state": "success", "age": 3000, "description": "Codex reviewed it (#4242)"}
    r = stuck(before=[passed], rereview_fails=True)
    assert r.watch(4, REREQUEST_AFTER="1", GATE_TIMEOUT="60", MAX_FETCH_FAILS="2") == [
        f"GATE_STUCK head={r.head} gate=codex-review requests=0 last_verdict=success reason=dispatch-failed"]
    assert len(dispatches(r)) == 2


def test_only_this_prs_pending_is_re_requested():
    rows = {"passed": {"state": "success", "description": "x (#4242)"}, "failed": {"state": "failure", "description": "x (#4242)"},
            "silent": None, "sibling": {"state": "pending", "description": "Waiting (#9999)"}}
    for name, row in rows.items():
        statuses = [{"context": "codex-review", "age": 9000, **row}] if row else []
        r = Run(issue_comments=coderabbit("{HEAD}"), statuses=statuses)
        r.watch(3, REREQUEST_AFTER="0", GATE_TIMEOUT="60")
        assert dispatches(r) == [], name


def test_a_running_check_that_is_no_gate_still_holds_green():
    r = Run(issue_comments=coderabbit("{HEAD}"), statuses=[
        {"context": "codex-review", "state": "success"}, {"context": "ci", "state": "pending"}])
    assert r.watch(4, GATE_TIMEOUT="1") == []


def test_thread_and_conflict_fire_a_round():
    r = Run(issue_comments=coderabbit("{HEAD}"), threads=[thread()], conflicting=True)
    lines = r.watch(3)
    assert lines[0] == f"ROUND head={r.head} unresolved=1 new_threads=1 failing= conflicting=1", lines
    assert sh("bash", str(SCRIPTS / "pr-state.sh"), "hoopit/api", str(PR), cwd=r.clone, env=r.env) == \
        "threads=PRRT_t1:1\nfailing=\nconflicting=1\n"


def test_a_lone_gate_verdict_stalls_the_head():
    r = Run(issue_comments=coderabbit("{HEAD}"), statuses=[{"context": "codex-review", "state": "failure"}])
    lines = r.watch(4, STALL_AFTER="0")
    assert lines[:2] == [f"ROUND head={r.head} unresolved=0 new_threads=0 failing=codex-review conflicting=0",
                         f"STALLED head={r.head} verdicts=codex-review:1"], lines


def test_a_push_and_a_resolve_take_the_head_to_green():
    r = Run(issue_comments=coderabbit("{CURRENT_HEAD}"), threads=[thread()], conflicting=True)
    (r.clone / "a.txt").write_text("three\n")
    sh("git", "commit", "-qam", "fix", cwd=r.clone, env=r.git_env)
    sh("git", "push", "-q", "origin", BRANCH, cwd=r.clone)
    r.gh("api", "repos/hoopit/api/pulls/4242/comments", "--field", "in_reply_to=77", "--field", "body=done")
    r.gh("api", "graphql", "-f", 'query=mutation { resolveReviewThread(input: {threadId: "PRRT_t1"}) { thread { isResolved } } }')
    new = sh("git", "rev-parse", "HEAD", cwd=r.clone).strip()
    assert r.gh("api", "repos/hoopit/api/pulls/4242", "--jq", ".head.sha").strip() == new
    assert r.watch(3) == [f"GREEN head={new}"]
    t = r.state()["threads"][0]
    assert t["resolved"] and len(t["comments"]) == 2


def test_labels_draft_and_body_persist():
    r = Run()
    sh("bash", str(SCRIPTS / "pr-labels.sh"), "hoopit/api", str(PR), "+monitored", "+agent-working", cwd=r.clone, env=r.env)
    sh("bash", str(SCRIPTS / "pr-labels.sh"), "hoopit/api", str(PR), "-agent-working", "-not-there", cwd=r.clone, env=r.env)
    assert r.state()["pr"]["labels"] == ["monitored"]
    r.gh("pr", "ready", str(PR), "--repo", "hoopit/api")
    assert r.gh("api", "repos/hoopit/api/pulls/4242", "--jq", ".draft").strip() == "false"
    body = r.dir / "body.md"
    body.write_text("new body\n")
    r.gh("api", "-X", "PATCH", "repos/hoopit/api/pulls/4242", "-F", f"body=@{body}")
    assert r.gh("pr", "view", str(PR), "--json", "body", "--jq", ".body") == "new body\n\n"
    calls = [json.loads(l) for l in r.calls.read_text().splitlines()]
    assert all(c["tool"] == "gh" and "head" in c and not c.get("fake") for c in calls), calls


def test_user_merge_after_polls_closes_the_watch():
    r = Run(issue_comments=coderabbit("{HEAD}"), merge_after_polls=2)
    lines = r.watch(6)
    assert lines == [f"GREEN head={r.head}", "PR_CLOSED state=MERGED"], lines
    assert r.gh("pr", "list", "--head", BRANCH, "--state", "merged", "--json", "number", "--jq", ".[].number").strip() == str(PR)


def test_an_unknown_call_fails_and_is_marked():
    r = Run()
    p = subprocess.run(["gh", "api", "repos/hoopit/api/nonsense"], cwd=r.clone, env=r.env, capture_output=True, text=True)
    assert p.returncode == 1 and "HTTP 404" in p.stderr
    assert json.loads(r.calls.read_text().splitlines()[-1])["fake"] == "unhandled"


if __name__ == "__main__":
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print(f"ok   {name}")
            except Exception as e:  # report every case, not only the first failure
                failed += 1
                print(f"FAIL {name}: {e!r}")
    sys.exit(1 if failed else 0)
