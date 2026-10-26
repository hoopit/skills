#!/usr/bin/env python3
"""Pins `linear-board`'s filters and state changes with Linear, `hoopit-board` and GitHub
stubbed: which issues reach triage and dispatch, the verdict's round trip through its
comment, a claim undone when Linear refuses it, and each way `settle` ends a claim.

    python3 personal/linear-dispatch/tests/test_linear_board.py

Offline and dependency-free. The Linear daemon runs these commands with nobody watching,
so a filter that admits an issue assigned to someone else, or a claim that strands a
registry entry, does its damage unseen.
"""
import argparse, contextlib, importlib.machinery, importlib.util, io, json, pathlib, re, sys

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "linear-board"
ME, OTHER = "user-me", "user-other"


def issue(key, state="Backlog", kind="backlog", label=None, assignee=None, team="BE",
          created="2026-10-01T00:00:00Z", priority=0, description="desc"):
    labels = [{"id": f"L-{label}", "name": label, "parent": {"name": "agent"}}] if label else []
    return {"id": f"id-{key}", "identifier": key, "title": f"title {key}",
            "description": description, "url": f"https://linear.app/hoopit/issue/{key}",
            "priority": priority, "createdAt": created, "updatedAt": created,
            "team": {"id": f"team-{team}", "key": team},
            "state": {"id": f"s-{state}", "name": state, "type": kind},
            "assignee": {"id": assignee} if assignee else None,
            "labels": {"nodes": labels + [{"id": "L-bug", "name": "Bug", "parent": None}]}}


def verdict_comment(repo="hoopit/api", effort="S", findings="Edit `a.py`.", verdict="doable",
                    user=ME, at="2026-10-02T00:00:00Z"):
    fields = {"verdict": verdict, "repo": repo, "effort": effort}
    return {"body": f"**Agent triage: {verdict}**\n\n{findings}\n\n`agent-triage v1 {json.dumps(fields)}`",
            "createdAt": at, "user": {"id": user}}


class Fake:
    """Linear behind `gql`, routed by operation name. `fail` names operations to refuse."""

    def __init__(self, issues, comments=None, fail=()):
        self.issues = {i["identifier"]: i for i in issues}
        self.comments = comments or {}
        self.fail, self.calls = set(fail), []

    def __call__(self, query, **v):
        op = re.search(r"(?:query|mutation) (\w+)", query)[1]
        self.calls.append((op, v))
        if op in self.fail:
            raise self.m.LinearError(f"{op} refused")
        if op == "Viewer":
            return {"viewer": {"id": ME}}
        if op == "Open":
            return {"issues": {"pageInfo": {"hasNextPage": False},
                               "nodes": [i for i in self.issues.values()
                                         if i["state"]["type"] in v["types"]]}}
        if op == "Issue":
            return {"issue": self.issues.get(v["id"])}
        if op == "Comments":
            return {"issue": {"comments": {"pageInfo": {"hasNextPage": False},
                                           "nodes": self.comments.get(v["id"], [])}}}
        if op == "Labels":
            return {"issueLabels": {"nodes": [{"id": "G", "team": None, "children": {"nodes": [
                {"id": f"L-{n}", "name": n} for n in ("doable", "not-doable", "released")]}}]}}
        if op == "States":
            return {"team": {"states": {"nodes": [
                {"id": "s-Backlog", "name": "Backlog", "type": "backlog", "position": 0},
                {"id": "s-InProgress", "name": "In Progress", "type": "started", "position": 2}]}}}
        return {}

    def ops(self, name):
        return [v for op, v in self.calls if op == name]


def load(fake, hb=None, pulls=None):
    spec = importlib.util.spec_from_loader("lb", importlib.machinery.SourceFileLoader("lb", str(SCRIPT)))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    fake.m = m
    m.gql = fake
    m.hb_calls = []

    def stub_hb(*args, stdin=None):
        m.hb_calls.append((args, stdin))
        return (hb or (lambda args, stdin: (0, "", "")))(args, stdin)

    m.hb = stub_hb
    m.gh_pull = lambda repo, n: (pulls or {}).get(f"{repo}#{n}")
    return m


def run(m, fn, stdin="", **ns):
    sys.stdin = io.StringIO(stdin)
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        try:
            code = getattr(m, fn)(argparse.Namespace(**ns))
        except SystemExit as e:
            code = e.code
    return out.getvalue(), code


def test_inbox_is_every_unlabelled_unstarted_issue_newest_first():
    """Every team and assignee is triaged; a verdict or a start takes an issue out."""
    fake = Fake([issue("SUP-1", "Triage", "triage", team="SUP", created="2026-10-03T00:00:00Z"),
                 issue("BE-1", assignee=OTHER, created="2026-10-02T00:00:00Z"),
                 issue("BE-2", label="not-doable"),
                 issue("BE-3", "In Progress", "started")])
    out, code = run(load(fake), "cmd_inbox", limit=10)
    rows = json.loads(out)
    assert [r["key"] for r in rows] == ["SUP-1", "BE-1"], rows
    assert rows[0]["repo"] is None and rows[1]["repo"] == "hoopit/api", rows
    out, _ = run(load(fake), "cmd_inbox", limit=1)
    assert [r["key"] for r in json.loads(out)] == ["SUP-1"]
    print("  SUP triage and an assigned BE issue are in; labelled and started ones are not")


def test_candidates_skip_other_peoples_issues_and_bare_labels():
    fake = Fake([issue("BE-1", label="doable", priority=3),
                 issue("BE-2", label="doable", assignee=OTHER),
                 issue("BE-3", label="doable", assignee=ME, priority=1),
                 issue("BE-4", label="doable"),
                 issue("BE-5", label="released"),
                 issue("BE-6", "In Progress", "started", label="doable")],
                comments={"BE-1": [verdict_comment(effort="M")],
                          "BE-2": [verdict_comment()],
                          "BE-3": [verdict_comment(repo="hoopit/web-admin", effort="XS")]})
    out, code = run(load(fake), "cmd_candidates")
    rows = json.loads(out)
    assert [r["key"] for r in rows] == ["BE-3", "BE-1"], rows
    assert (rows[0]["repo"], rows[0]["effort"], rows[0]["priority"]) == ("hoopit/web-admin", "XS", "P0")
    assert rows[1]["body"].endswith("## Triage findings\n\n**Agent triage: doable**\n\nEdit `a.py`."), rows[1]
    assert rows[1]["source"] == "linear" and code == 0
    print("  someone else's, unverdicted, released and started issues never reach collide")


def test_a_verdict_swaps_the_label_and_round_trips_through_its_comment():
    fake = Fake([issue("SUP-1", "Triage", "triage", label="released", team="SUP")])
    m = load(fake)
    out, code = run(m, "cmd_verdict", stdin="It is a one-line copy change in `x.ts`.",
                    key="SUP-1", doable=True, not_doable=False, repo="hoopit/web-admin",
                    effort="XS")
    assert code == 0 and out.startswith("DOABLE\tSUP-1"), (out, code)
    (u,) = fake.ops("Update")
    assert u["input"] == {"removedLabelIds": ["L-released"], "addedLabelIds": ["L-doable"]}, u
    (c,) = fake.ops("Comment")
    fake.comments["SUP-1"] = [{"body": c["input"]["body"], "createdAt": "2026-10-05T00:00:00Z",
                               "user": {"id": ME}}]
    fields, findings = m.triage_of("SUP-1")
    assert fields == {"verdict": "doable", "repo": "hoopit/web-admin", "effort": "XS"}, fields
    assert "one-line copy change" in findings and "agent-triage" not in findings, findings
    for bad in ({"repo": None, "effort": "S"}, {"repo": "hoopit/api", "effort": None}):
        _, code = run(m, "cmd_verdict", stdin="x", key="SUP-1", doable=True, not_doable=False, **bad)
        assert "needs --repo and --effort" in str(code), code
    _, code = run(m, "cmd_verdict", stdin="  ", key="SUP-1", doable=False, not_doable=True,
                  repo=None, effort=None)
    assert "findings on stdin are empty" in str(code), code
    print("  released -> doable in one update; the comment parses back; empty reasons refused")


def test_a_claim_registers_first_and_is_undone_whole_when_linear_refuses():
    issues = [issue("BE-1", label="doable")]
    comments = {"BE-1": [verdict_comment()]}
    fake = Fake(issues, comments)
    m = load(fake)
    out, code = run(m, "cmd_claim", key="BE-1", agent="lin-be-1", model="sonnet",
                    reasoning_effort="medium")
    assert code == 0 and out.startswith("CLAIMED\tBE-1\thoopit/api"), (out, code)
    assert [a for a, _ in m.hb_calls] == [("claims", "list"), ("claims", "put")], m.hb_calls
    assert json.loads(m.hb_calls[1][1])["agent"] == "lin-be-1", m.hb_calls
    (u,) = fake.ops("Update")
    assert u["input"] == {"assigneeId": ME, "stateId": "s-InProgress"}, u
    assert "`lin-be-1` on `sonnet` at `medium` effort" in fake.ops("Comment")[0]["input"]["body"]

    # Refused before anything moved: only the registry entry to undo.
    fake = Fake(issues, comments, fail={"Update"})
    m = load(fake)
    _, code = run(m, "cmd_claim", key="BE-1", agent="lin-be-1", model=None, reasoning_effort=None)
    assert "the claim is undone" in str(code), code
    assert [a for a, _ in m.hb_calls][-1] == ("claims", "drop", "linear", "BE-1"), m.hb_calls

    # Moved, then the comment refused: the move is put back too.
    fake = Fake(issues, comments, fail={"Comment"})
    m = load(fake)
    _, code = run(m, "cmd_claim", key="BE-1", agent="lin-be-1", model=None, reasoning_effort=None)
    assert "the claim is undone" in str(code), code
    moved, back = fake.ops("Update")
    assert back["input"] == {"assigneeId": None, "stateId": "s-Backlog"}, back
    assert [a for a, _ in m.hb_calls][-1] == ("claims", "drop", "linear", "BE-1")

    # A drop that fails is said, not claimed done.
    fake = Fake(issues, comments, fail={"Comment"})
    m = load(fake, hb=lambda args, stdin: (1, "", "disk full") if args[1] == "drop" else (0, "", ""))
    _, code = run(m, "cmd_claim", key="BE-1", agent="x", model=None, reasoning_effort=None)
    assert "registry claim is still there: disk full" in str(code), code

    m = load(Fake([issue("BE-1", label="doable", assignee=OTHER)], comments))
    _, code = run(m, "cmd_claim", key="BE-1", agent="x", model=None, reasoning_effort=None)
    assert "not dispatchable" in str(code) and m.hb_calls == [], code

    listed = lambda args, stdin: ((0, "linear:BE-1\thoopit/api\ta\t-\thttps://github.com/hoopit/api/pull/9\tt", "")
                                  if args == ("claims", "list") else (0, "", ""))
    m = load(Fake(issues, comments), hb=listed)
    _, code = run(m, "cmd_claim", key="BE-1", agent="x", model=None, reasoning_effort=None)
    assert "already in the claims registry" in str(code), code
    assert [a for a, _ in m.hb_calls] == [("claims", "list")], m.hb_calls
    print("  put -> move -> comment; each refusal undoes what landed; a registered key is refused")


def test_only_my_newest_doable_verdict_counts():
    """A synced customer or a colleague writing the triage line must not pick the repo an
    unattended agent works in, nor its brief."""
    m = load(Fake([], {"BE-1": [
        verdict_comment(repo="hoopit/api", at="2026-10-02T00:00:00Z"),
        verdict_comment(repo="evil/repo", user=OTHER, at="2026-10-05T00:00:00Z"),
        {"body": "quoting `agent-triage v1 {\"repo\": \"x/y\"}` mid-text\n\nmore", "createdAt":
         "2026-10-06T00:00:00Z", "user": {"id": ME}},
        {"body": "`agent-triage v1 {not json}`", "createdAt": "2026-10-07T00:00:00Z",
         "user": {"id": ME}}]}))
    fields, findings = m.triage_of("BE-1")
    assert fields["repo"] == "hoopit/api" and findings.endswith("Edit `a.py`."), (fields, findings)

    fake = Fake([issue("BE-1", label="doable")], {"BE-1": [
        verdict_comment(at="2026-10-02T00:00:00Z"),
        verdict_comment(verdict="not-doable", effort=None, at="2026-10-03T00:00:00Z")]})
    out, code = run(load(fake), "cmd_candidates")
    assert json.loads(out) == [] and code == 1, out
    print("  another user's line, a quoted line and bad JSON are ignored; a newer not-doable wins")


def test_a_verdict_comment_that_fails_leaves_the_issue_in_the_inbox():
    fake = Fake([issue("BE-1")], fail={"Comment"})
    m = load(fake)
    try:
        run(m, "cmd_verdict", stdin="why", key="BE-1", doable=True, not_doable=False,
            repo="hoopit/api", effort="S")
    except m.LinearError:
        pass
    else:
        raise AssertionError("a refused comment was not an error")
    assert fake.ops("Update") == [], fake.ops("Update")
    fake = Fake([issue("BE-1", label="doable")])
    run(load(fake), "cmd_verdict", stdin="again", key="BE-1", doable=True, not_doable=False,
        repo="hoopit/api", effort="S")
    assert fake.ops("Update") == [], "re-labelling the same verdict sent an update"
    _, code = run(load(fake), "cmd_verdict", stdin="x", key="BE-1", doable=False,
                  not_doable=True, repo=None, effort="S")
    assert "prices nothing" in str(code), code
    print("  no label without its comment; the same verdict twice sends no label change")


def test_release_hands_back_to_backlog_and_unassigns_only_me():
    fake = Fake([issue("BE-1", "In Progress", "started", label="doable", assignee=ME)])
    m = load(fake)
    out, code = run(m, "cmd_release", key="BE-1", reason="the premise was wrong")
    (u,) = fake.ops("Update")
    assert u["input"] == {"removedLabelIds": ["L-doable"], "addedLabelIds": ["L-released"],
                          "stateId": "s-Backlog", "assigneeId": None}, u
    assert m.hb_calls[-1][0] == ("claims", "drop", "linear", "BE-1")
    fake = Fake([issue("BE-1", "In Progress", "started", label="doable", assignee=OTHER)])
    run(load(fake), "cmd_release", key="BE-1", reason="r")
    assert "assigneeId" not in fake.ops("Update")[0]["input"]
    print("  released, Backlog, unassigned from me — a colleague's assignment is left alone")


def test_settle_ends_only_finished_claims():
    pr = lambda n: f"https://github.com/hoopit/api/pull/{n}"
    listing = "\n".join([
        f"linear:BE-1\thoopit/api\ta\t-\t{pr(1)}\tt",          # merged
        f"linear:BE-2\thoopit/api\ta\t-\t{pr(2)}\tt",          # closed unmerged
        f"linear:BE-3\thoopit/api\ta\t-\t{pr(3)}\tt",          # still open
        f"linear:BE-4\thoopit/api\ta\t-\t-\tt",                # ended in Linear
        f"linear:BE-5\thoopit/api\ta\t-\t-\tt",                # no PR yet
        f"github:x\thoopit/api\ta\t-\t-\tt"])                  # another source
    issues = [issue(k, "In Progress", "started", label="doable", assignee=ME)
              for k in ("BE-1", "BE-2", "BE-3", "BE-5")] + [issue("BE-4", "Done", "completed")]
    pulls = {"hoopit/api#1": "MERGED", "hoopit/api#2": "CLOSED", "hoopit/api#3": "OPEN"}
    hb = lambda args, stdin: (0, listing, "") if args == ("claims", "list") else (0, "", "")

    fake = Fake(issues)
    m = load(fake, hb, pulls)
    out, code = run(m, "cmd_settle", apply=False)
    assert [l.split("\t")[:2] for l in out.splitlines()] == [
        ["merged", "BE-1"], ["closed", "BE-2"], ["ended", "BE-4"]], out
    assert fake.ops("Update") == [] and fake.ops("Comment") == [], "a dry run changed something"
    assert [a for a, _ in m.hb_calls] == [("claims", "list")], m.hb_calls

    fake = Fake(issues)
    m = load(fake, hb, pulls)
    run(m, "cmd_settle", apply=True)
    drops = [a[2:] for a, _ in m.hb_calls if a[:2] == ("claims", "drop")]
    assert drops == [("linear", "BE-1"), ("linear", "BE-2"), ("linear", "BE-4")], drops
    merged, closed = fake.ops("Update")
    assert merged == {"id": "id-BE-1", "input": {"removedLabelIds": ["L-doable"]}}, merged
    assert closed["id"] == "id-BE-2" and closed["input"]["addedLabelIds"] == ["L-released"], closed
    print("  merged and ended are dropped, closed is released; open, PR-less and github claims untouched")


def test_settle_reads_mixed_and_unreadable_prs_and_survives_a_failure():
    """A first PR closed and a second merged is a finished claim. One PR GitHub will not
    show keeps the claim. A release Linear refuses is named and does not stop the rest."""
    pr = lambda n: f"https://github.com/hoopit/api/pull/{n}"
    listing = "\n".join([
        f"linear:BE-1\thoopit/api\ta\t-\t{pr(1)},{pr(2)}\tt",   # closed + merged
        f"linear:BE-2\thoopit/api\ta\t-\t{pr(1)},{pr(9)}\tt",   # closed + unreadable
        f"linear:BE-3\thoopit/api\ta\t-\t{pr(1)}\tt",           # closed: release refused
        f"linear:BE-4\thoopit/api\ta\t-\t-\tt"])                # ended
    issues = [issue(k, "In Progress", "started", label="doable", assignee=ME)
              for k in ("BE-1", "BE-2", "BE-3")] + [issue("BE-4", "Canceled", "canceled")]
    pulls = {"hoopit/api#1": "CLOSED", "hoopit/api#2": "MERGED"}
    hb = lambda args, stdin: (0, listing, "") if args == ("claims", "list") else (0, "", "")
    fake = Fake(issues, fail={"Comment"})
    m = load(fake, hb, pulls)
    out, code = run(m, "cmd_settle", apply=True)
    assert [l.split("\t")[:2] for l in out.splitlines()] == [
        ["merged", "BE-1"], ["skip", "BE-3"], ["ended", "BE-4"]], out
    drops = [a[3] for a, _ in m.hb_calls if a[:2] == ("claims", "drop")]
    assert drops == ["BE-1", "BE-4"], drops
    print("  closed+merged settles, an unreadable PR holds, a refused release is skipped")


def test_eligible_covers_every_not_started_state_and_nothing_else():
    m = load(Fake([]))
    for kind, ok in (("triage", True), ("backlog", True), ("unstarted", True),
                     ("started", False), ("completed", False), ("canceled", False)):
        assert m.eligible(issue("BE-1", kind=kind, label="doable"), ME) is ok, kind
    assert not m.eligible(issue("BE-1", label="not-doable"), ME)
    print("  triage, backlog and unstarted are dispatchable; started and ended are not")


def test_the_registry_contract_holds_against_the_real_hoopit_board():
    """The rest of this file stubs `hoopit-board`. This runs the real one, against a
    scratch registry, so a change to `claims list`'s columns or `put`'s schema fails here."""
    import os, subprocess, tempfile
    board = SCRIPT.parents[3] / "plugins" / "github-tracker" / "bin" / "hoopit-board"
    with tempfile.TemporaryDirectory() as state:
        env = {**os.environ, "XDG_STATE_HOME": state}
        m = load(Fake([issue("BE-1", label="doable")], {"BE-1": [verdict_comment()]}))
        m.hb = lambda *args, stdin=None: (lambda r: (r.returncode, r.stdout, r.stderr))(
            subprocess.run([sys.executable, str(board), *args], input=stdin,
                           capture_output=True, text=True, env=env))
        out, code = run(m, "cmd_claim", key="BE-1", agent="lin-be-1", model=None,
                        reasoning_effort=None)
        assert code == 0, (out, code)
        pr = "https://github.com/hoopit/api/pull/7"
        out, code = run(m, "cmd_pr", key="BE-1", url=pr)
        assert code == 0, (out, code)
        assert m.linear_claims() == [("BE-1", [pr])], m.linear_claims()
        assert m.drop("BE-1") is None and m.linear_claims() == []
    print("  claim -> pr -> list -> drop round-trips through the real registry")


def test_provision_adds_only_what_is_missing():
    fake = Fake([])
    m = load(fake)
    m.group_labels = lambda: ("G", {"doable": "L1"})
    out, _ = run(m, "cmd_provision", apply=True)
    assert out.splitlines() == ["OK\tagent/doable", "ADD\tagent/not-doable", "ADD\tagent/released"]
    assert [v["input"]["name"] for v in fake.ops("Label")] == ["not-doable", "released"]
    assert all(v["input"]["parentId"] == "G" for v in fake.ops("Label"))
    print("  an existing child is kept; the missing two are created under the group")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        print(f"{t.__name__}:")
        t()
    print(f"\n{len(tests)} passed")
