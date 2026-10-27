#!/usr/bin/env python3
"""Pins `linear-board`'s filters and state changes with Linear, `hoopit-board` and GitHub
stubbed: which issues reach triage, the split into platform sub-issues, which units reach
dispatch, a claim undone when Linear refuses it, and each way `settle` ends a claim.

    python3 personal/linear-dispatch/tests/test_linear_board.py

Offline and dependency-free. The Linear daemon runs these commands with nobody watching,
so a filter that admits an issue somebody else holds, half a unit, or a claim that strands
a registry entry, does its damage unseen.
"""
import argparse, contextlib, importlib.machinery, importlib.util, io, json, os, pathlib, re
import subprocess, sys, tempfile

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "linear-board"
ME, OTHER, LUKAS = "user-me", "user-other", "user-lukas"
STATES = [{"id": "s-Triage", "name": "Triage", "type": "triage", "position": 0},
          {"id": "s-Backlog", "name": "Backlog", "type": "backlog", "position": 1},
          {"id": "s-Todo", "name": "Todo", "type": "unstarted", "position": 2},
          {"id": "s-InProgress", "name": "In Progress", "type": "started", "position": 3}]
STATE = {s["id"]: s for s in STATES}


def issue(key, state="Triage", kind="triage", label=None, assignee=None, team="SUP",
          created="2026-10-01T00:00:00Z", priority=0, description="desc", parent=None,
          creator=OTHER):
    labels = [{"id": f"L-{label}", "name": label, "parent": {"name": "agent"}}] if label else []
    return {"id": f"id-{key}", "identifier": key, "title": f"title {key}",
            "description": description, "url": f"https://linear.app/hoopit/issue/{key}",
            "priority": priority, "createdAt": created, "updatedAt": created,
            "team": {"id": f"team-{team}", "key": team,
                     "issueEstimationType": "notUsed" if team in ("SUP", "CAL") else "tShirt"},
            "state": {"id": f"s-{state.replace(' ', '')}", "name": state, "type": kind},
            "assignee": {"id": assignee} if assignee else None,
            "creator": {"id": creator},
            "parent": ({"id": f"id-{parent}", "identifier": parent, "team": {"key": "SUP"}}
                       if parent else None),
            "labels": {"nodes": labels + [{"id": "L-Bug", "name": "Bug", "parent": None}]}}


def child(key, team="BE", parent="SUP-1", label="doable", state="Backlog", kind="backlog",
          assignee=None, creator=ME, priority=0):
    return issue(key, state, kind, label=label, assignee=assignee, team=team, parent=parent,
                 creator=creator, priority=priority)


def verdict_comment(repo="hoopit/api", effort="S", findings="Edit `a.py`.", verdict="doable",
                    user=ME, at="2026-10-02T00:00:00Z", together=True):
    fields = {"verdict": verdict, "repo": repo, "effort": effort, "together": together}
    return {"body": f"**Agent triage: {verdict}**\n\n{findings}\n\n`agent-triage v1 {json.dumps(fields)}`",
            "createdAt": at, "user": {"id": user}}


class Fake:
    """Linear behind `gql`, routed by operation name, keeping the issues it is told to
    change. `fail` names operations to refuse."""

    def __init__(self, issues, comments=None, fail=()):
        self.issues = {i["identifier"]: i for i in issues}
        self.comments = comments or {}
        self.fail, self.calls, self.made = set(fail), [], 0

    def by_id(self, iid):
        return next(i for i in self.issues.values() if i["id"] == iid)

    def __call__(self, query, **v):
        op = re.search(r"(?:query|mutation) (\w+)", query)[1]
        self.calls.append((op, v))
        if op in self.fail:
            raise self.m.LinearError(f"{op} refused")
        if op == "Viewer":
            return {"viewer": {"id": ME}}
        if op == "Open":
            return {"issues": {"pageInfo": {"hasNextPage": False}, "nodes": [
                i for i in self.issues.values()
                if i["state"]["type"] == v["type"] and i["team"]["key"] == v["team"]]}}
        if op == "Work":
            return {"issues": {"pageInfo": {"hasNextPage": False}, "nodes": [
                i for i in self.issues.values()
                if any(l["name"] == "doable" for l in i["labels"]["nodes"])
                and ((i.get("parent") or {}).get("team") or {}).get("key") == v["team"]
                and i["state"]["type"] in v["types"]]}}
        if op == "Parts":
            return {"issues": {"pageInfo": {"hasNextPage": False}, "nodes": [
                i for i in self.issues.values()
                if ((i.get("parent") or {}).get("team") or {}).get("key") == v["team"]
                and i["state"]["type"] in v["types"]]}}
        if op == "Children":
            return {"issue": {"children": {"nodes": [
                i for i in self.issues.values()
                if (i.get("parent") or {}).get("identifier") == v["id"]]}}}
        if op == "Issue":
            return {"issue": self.issues.get(v["id"])}
        if op == "Comments":
            return {"issue": {"comments": {"pageInfo": {"hasNextPage": False},
                                           "nodes": self.comments.get(v["id"], [])}}}
        if op == "Labels":
            return {"issueLabels": {"nodes": [{"id": "G", "team": None, "children": {"nodes": [
                {"id": f"L-{n}", "name": n}
                for n in ("doable", "not-doable", "split", "released")]}}]}}
        if op == "Types":
            return {"issueLabels": {"nodes": [{"id": f"L-{n}", "name": n} for n in v["names"]]}}
        if op == "Owner":
            return {"users": {"nodes": [{"id": LUKAS}]}}
        if op == "States":
            return {"team": {"states": {"nodes": STATES}}}
        if op == "Team":
            return {"teams": {"nodes": [{"id": f'team-{v["key"]}', "states": {"nodes": STATES}}]}}
        if op == "Create":
            inp, self.made = v["input"], self.made + 1
            team = inp["teamId"].split("-", 1)[1]
            sup = self.by_id(inp["parentId"])
            new = issue(f"{team}-{100 + self.made}", team=team, creator=ME,
                        parent=sup["identifier"], description=inp["description"])
            new["state"] = dict(STATE[inp["stateId"]])
            new["title"], new["priority"] = inp["title"], inp["priority"]
            self.issues[new["identifier"]] = new
            return {"issueCreate": {"issue": new}}
        if op == "Update":
            i, inp = self.by_id(v["id"]), v["input"]
            nodes = [l for l in i["labels"]["nodes"] if l["id"] not in inp.get("removedLabelIds", [])]
            nodes += [{"id": l, "name": l[2:],
                       "parent": None if l[2:] in ("Bug", "Improvement", "Feature") else {"name": "agent"}}
                      for l in inp.get("addedLabelIds", [])]
            i["labels"] = {"nodes": nodes}
            if "stateId" in inp:
                i["state"] = dict(STATE[inp["stateId"]])
            if "estimate" in inp:
                i["estimate"] = inp["estimate"]
            if "assigneeId" in inp:
                i["assignee"] = {"id": inp["assigneeId"]} if inp["assigneeId"] else None
            return {}
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


def plan(*parts, together=True, kind="Bug"):
    return json.dumps({"type": kind, "together": together,
                       "parts": [dict({"title": f"t {p['repo']}", "findings": "Edit `a.py`."}, **p)
                                 for p in parts]})


def test_inbox_is_supports_triage_queue_alone_newest_first():
    """Only Support's Triage state is triaged: every other team, and every other Support
    state, plans its own work and is never commented on."""
    fake = Fake([issue("SUP-1", created="2026-10-03T00:00:00Z"),
                 issue("SUP-2", assignee=OTHER, created="2026-10-02T00:00:00Z"),
                 issue("SUP-3", label="not-doable"),
                 issue("SUP-4", "Backlog", "backlog"),
                 issue("BE-1", team="BE"),
                 issue("BE-2", "Backlog", "backlog", team="BE")])
    out, code = run(load(fake), "cmd_inbox", limit=10)
    assert [r["key"] for r in json.loads(out)] == ["SUP-1", "SUP-2", "SUP-3"], out
    out, _ = run(load(fake), "cmd_inbox", limit=1)
    assert [r["key"] for r in json.loads(out)] == ["SUP-1"]
    _, code = run(load(fake), "cmd_verdict", stdin="x", key="BE-1", doable=False, not_doable=True,
                  repo=None, effort=None, type="Bug", waits_on="support")
    assert "nor a part this flow split off" in str(code) and fake.ops("Comment") == [], code
    print("  every SUP Triage issue, labelled or not; other teams and states untouched, a BE verdict refused")


def test_a_not_doable_verdict_types_assigns_and_moves_it_to_backlog():
    """A Support issue that waits on a person leaves Triage for Backlog, typed by triage,
    assigned to whoever must answer, with no agent label — a stale one from an earlier pass
    is cleared."""
    fake = Fake([issue("SUP-1", label="split")])
    m = load(fake)
    out, code = run(m, "cmd_verdict", stdin="Which wording? A or B.", key="SUP-1",
                    doable=False, not_doable=True, repo="hoopit/web-admin", effort=None,
                    type="Improvement", waits_on="product")
    assert code == 0 and out.startswith("NOT-DOABLE\tSUP-1"), (out, code)
    sup = fake.issues["SUP-1"]
    assert sup["state"]["name"] == "Backlog" and sup["assignee"] == {"id": LUKAS}, sup
    assert sorted(l["name"] for l in sup["labels"]["nodes"]) == ["Improvement"], sup["labels"]
    assert fake.calls.index(("Comment", fake.ops("Comment")[0])) < len(fake.calls) - 1
    (c,) = fake.ops("Comment")
    fake.comments["SUP-1"] = [{"body": c["input"]["body"], "createdAt": "2026-10-05T00:00:00Z",
                               "user": {"id": ME}}]
    fields, findings = m.triage_of("SUP-1")
    assert fields == {"verdict": "not-doable", "repo": "hoopit/web-admin", "effort": None}, fields
    assert "Which wording" in findings and "agent-triage" not in findings, findings

    fake = Fake([issue("SUP-2")])
    run(load(fake), "cmd_verdict", stdin="Ask NIF.", key="SUP-2", doable=False, not_doable=True,
        repo=None, effort=None, type="Bug", waits_on="support")
    assert fake.issues["SUP-2"]["assignee"] is None and fake.ops("Owner") == []

    m = load(Fake([issue("SUP-3", "Backlog", "backlog")]))
    for kw, why in (({"type": "Bug", "waits_on": "support"}, "move it back to Triage"),):
        _, code = run(m, "cmd_verdict", stdin="x", key="SUP-3", doable=False, not_doable=True,
                      repo=None, effort=None, **kw)
        assert why in str(code), code
    m = load(Fake([issue("SUP-1")]))
    for kw, why in (({"type": None, "waits_on": "support"}, "needs --type"),
                    ({"type": "Bug", "waits_on": None}, "needs --waits-on")):
        _, code = run(m, "cmd_verdict", stdin="x", key="SUP-1", doable=False, not_doable=True,
                      repo=None, effort=None, **kw)
        assert why in str(code), (kw, code)
    _, code = run(m, "cmd_verdict", stdin="  ", key="SUP-1", doable=False, not_doable=True,
                  repo=None, effort=None, type="Bug", waits_on="support")
    assert "findings on stdin are empty" in str(code), code
    _, code = run(m, "cmd_verdict", stdin="x", key="SUP-1", doable=True, not_doable=False,
                  repo="hoopit/api", effort="S", type="Bug", waits_on=None)
    assert "is split, never labelled" in str(code), code
    print("  Improvement, Lukas, Backlog, stale split label gone; support waits stay unassigned; refusals")


def test_split_makes_one_sub_issue_per_platform_then_commits_on_the_parent():
    fake = Fake([issue("SUP-1", priority=2)])
    m = load(fake)
    out, code = run(m, "cmd_split", key="SUP-1", stdin=plan(
        {"repo": "hoopit/api", "verdict": "doable", "effort": "S"},
        {"repo": "hoopit/flutter-app", "verdict": "not-doable", "waits_on": "product",
         "findings": "Which screen?", "type": "Improvement"}))
    assert code == 0, (out, code)
    names = lambda i: sorted(l["name"] for l in i["labels"]["nodes"] if not l.get("parent"))
    assert names(fake.issues["BE-101"]) == ["Bug"] and names(fake.issues["APP-102"]) == ["Improvement"]
    assert fake.issues["APP-102"]["assignee"] == {"id": LUKAS} and fake.issues["BE-101"]["assignee"] is None
    assert fake.issues["BE-101"]["estimate"] == 2 and fake.issues["APP-102"]["estimate"] is None
    be, app = fake.issues["BE-101"], fake.issues["APP-102"]
    assert (be["state"]["name"], be["priority"], be["parent"]["identifier"]) == ("Backlog", 2, "SUP-1")
    assert be["description"].startswith("Split from [SUP-1]") and "Edit `a.py`." in be["description"]
    assert m.agent_label(be) == "doable" and m.agent_label(app) == "not-doable"
    sup = fake.issues["SUP-1"]
    assert m.agent_label(sup) == "split" and sup["state"]["name"] == "Todo", sup
    # The parent is written last: its update is the final call.
    assert fake.calls[-1][0] == "Update" and fake.calls[-1][1]["id"] == "id-SUP-1"
    fake.comments["BE-101"] = [{"body": c["input"]["body"], "createdAt": "2026-10-05T00:00:00Z",
                                "user": {"id": ME}} for c in fake.ops("Comment")
                               if c["input"]["issueId"] == "id-BE-101"]
    fields, _ = m.triage_of("BE-101")
    assert fields == {"verdict": "doable", "repo": "hoopit/api", "effort": "S",
                      "together": True}, fields
    assert out.splitlines()[-1] == "SPLIT\tSUP-1", out
    print("  BE doable and APP not-doable under SUP-1, which reads split in Todo last")


def test_a_split_cut_short_is_finished_without_a_second_sub_issue():
    fake = Fake([issue("SUP-1")], fail={"Comment"})
    m = load(fake)
    try:
        run(m, "cmd_split", key="SUP-1", stdin=plan({"repo": "hoopit/api", "verdict": "doable",
                                                     "effort": "S"}))
    except m.LinearError:
        pass
    assert "BE-101" in fake.issues and m.agent_label(fake.issues["BE-101"]) is None
    assert m.agent_label(fake.issues["SUP-1"]) is None, "the parent committed before its parts"
    fake.fail.clear()
    out, code = run(m, "cmd_split", key="SUP-1", stdin=plan({"repo": "hoopit/api",
                                                             "verdict": "doable", "effort": "S"}))
    assert code == 0 and len(fake.ops("Create")) == 1, (out, fake.ops("Create"))
    assert m.agent_label(fake.issues["BE-101"]) == "doable"
    assert m.agent_label(fake.issues["SUP-1"]) == "split"
    _, code = run(m, "cmd_split", key="SUP-1", stdin=plan({"repo": "hoopit/api",
                                                          "verdict": "doable", "effort": "S"}))
    assert "not in SUP Triage" in str(code), code
    print("  a refused comment leaves SUP-1 in the inbox; the rerun labels BE-101 instead of making BE-102")


def test_split_refuses_a_bad_plan_before_writing():
    fake = Fake([issue("SUP-1")])
    m = load(fake)
    for bad, why in (
            ("not json", "not JSON"),
            ('{"parts": []}', "one part per platform"),
            (plan({"repo": "hoopit/skills", "verdict": "doable", "effort": "S"}), "no team owns"),
            (plan({"repo": "hoopit/api", "verdict": "doable"}), "needs an Effort"),
            (plan({"repo": "hoopit/api", "verdict": "doable", "effort": "XL"}), "XL is not doable"),
            (plan({"repo": "hoopit/api", "verdict": "not-doable", "effort": "S"}), "prices nothing"),
            (plan({"repo": "hoopit/api", "verdict": "doable", "effort": "S"},
                  {"repo": "hoopit/api", "verdict": "doable", "effort": "M"}), "appears twice"),
            (json.dumps({"type": "Bug", "parts": [
                {"repo": "hoopit/api", "title": "t", "verdict": "doable", "effort": "S", "findings": "f"},
                {"repo": "hoopit/web-admin", "title": "t", "verdict": "doable", "effort": "S",
                 "findings": "f"}]}), "ship together"),
            (plan({"repo": "hoopit/api", "verdict": "doable", "effort": "S"}, kind="Chore"), '"type"'),
            (plan({"repo": "hoopit/api", "verdict": "not-doable"}), '"waits_on"'),
            (plan({"repo": "hoopit/api", "verdict": "doable", "effort": "S", "waits_on": "product"}),
             "waits on nobody")):
        _, code = run(m, "cmd_split", key="SUP-1", stdin=bad)
        assert why in str(code), (bad, code)
    assert fake.ops("Create") == [] and fake.ops("Update") == []
    m = load(Fake([issue("SUP-1", "Backlog", "backlog")]))
    _, code = run(m, "cmd_split", key="SUP-1", stdin=plan({"repo": "hoopit/api",
                                                          "verdict": "doable", "effort": "S"}))
    assert "not in SUP Triage" in str(code), code
    m = load(fake := Fake([issue("SUP-1", label="not-doable")]))
    _, code = run(m, "cmd_split", key="SUP-1", stdin=plan({"repo": "hoopit/api",
                                                          "verdict": "doable", "effort": "S"}))
    assert code == 0 and m.agent_label(fake.issues["SUP-1"]) == "split", code
    print("  bad plans and an issue outside Triage are refused unwritten; a labelled one in Triage splits")


def test_candidates_offer_whole_units_only():
    """Every sub-issue of one Support issue starts together or not at all, so the parts can
    agree on the contract between them."""
    fake = Fake([child("BE-1", parent="SUP-1", priority=3),
                 child("APP-1", team="APP", parent="SUP-1", priority=3),
                 child("BE-2", parent="SUP-2"),
                 child("APP-2", team="APP", parent="SUP-2", label="not-doable"),
                 child("BE-3", parent="SUP-3", priority=1),
                 child("BE-4", parent="SUP-4", assignee=OTHER),
                 child("BE-5", parent="SUP-5", creator=OTHER),
                 child("BE-6", parent="SUP-6"),
                 child("BE-7", parent="SUP-7", state="In Progress", kind="started")],
                comments={k: [verdict_comment(repo=r, effort=e)] for k, r, e in (
                    ("BE-1", "hoopit/api", "M"), ("APP-1", "hoopit/flutter-app", "S"),
                    ("BE-2", "hoopit/api", "S"), ("BE-3", "hoopit/api", "XS"),
                    ("BE-4", "hoopit/api", "S"), ("BE-5", "hoopit/api", "S"))})
    out, code = run(load(fake), "cmd_candidates")
    rows = json.loads(out)
    assert [(r["unit"], r["key"]) for r in rows] == [
        ("SUP-3", "BE-3"), ("SUP-1", "BE-1"), ("SUP-1", "APP-1")], rows
    assert rows[1]["body"].endswith("## Triage findings\n\n**Agent triage: doable**\n\nEdit `a.py`.")
    assert rows[0]["priority"] == "P0" and code == 0
    print("  SUP-1 whole; SUP-2 held by its not-doable half; others' and bare-label ones never reach collide")


def test_parts_that_ship_apart_start_on_their_own():
    """`together: false` is triage saying waiting buys nothing: a doable part starts while
    its sibling waits on a question."""
    fake = Fake([child("BE-1", parent="SUP-1"),
                 child("APP-1", team="APP", parent="SUP-1", label="not-doable")],
                comments={"BE-1": [verdict_comment(together=False)],
                          "APP-1": [verdict_comment(repo="hoopit/flutter-app", effort=None,
                                                    verdict="not-doable", together=False)]})
    out, code = run(load(fake), "cmd_candidates")
    assert [(r["unit"], r["key"]) for r in json.loads(out)] == [("BE-1", "BE-1")], out
    print("  BE-1 is its own unit and starts; APP-1 waits alone")


def test_a_held_part_sent_back_is_judged_again_and_frees_its_unit():
    """The way out of a held unit: a person answers the question and removes the part's
    label; triage judges that part alone, and the unit starts once it reads doable."""
    app = child("APP-1", team="APP", parent="SUP-1", label=None)
    fake = Fake([child("BE-1", parent="SUP-1"), app, issue("SUP-2")],
                comments={"BE-1": [verdict_comment()],
                          "APP-1": [verdict_comment(repo="hoopit/flutter-app", effort=None,
                                                    verdict="not-doable")]})
    m = load(fake)
    out, _ = run(m, "cmd_candidates")
    assert json.loads(out) == [], out
    out, _ = run(m, "cmd_inbox", limit=10)
    rows = {r["key"]: r for r in json.loads(out)}
    assert set(rows) == {"APP-1", "SUP-2"}, rows
    assert (rows["APP-1"]["parent"], rows["APP-1"]["repo"]) == ("SUP-1", "hoopit/flutter-app")
    out, code = run(m, "cmd_verdict", stdin="Answered: screen B.", key="APP-1", doable=True,
                    not_doable=False, repo=None, effort="S", type=None, waits_on=None)
    assert code == 0 and out.startswith("DOABLE\tAPP-1\thoopit/flutter-app\tS"), (out, code)
    assert fake.issues["APP-1"]["estimate"] == 2, fake.issues["APP-1"]
    fake.comments["APP-1"].append({"body": fake.ops("Comment")[-1]["input"]["body"],
                                   "createdAt": "2026-10-09T00:00:00Z", "user": {"id": ME}})
    assert m.triage_of("APP-1")[0]["together"] is True
    out, _ = run(m, "cmd_candidates")
    assert [r["key"] for r in json.loads(out)] == ["BE-1", "APP-1"], out
    _, code = run(m, "cmd_verdict", stdin="x", key="APP-1", doable=True, not_doable=False,
                  repo=None, effort=None, type=None, waits_on=None)
    assert "needs --effort" in str(code), code
    print("  APP-1 reappears in the inbox unlabelled, reads doable again, and SUP-1's unit starts whole")


def test_fetch_takes_only_linear_uploads_into_a_fresh_directory():
    m = load(Fake([]))
    m.linear_key = lambda: "k"
    with tempfile.TemporaryDirectory() as d:
        pathlib.Path(d, "x").write_text("x")
        _, code = run(m, "cmd_fetch", urls=["https://uploads.linear.app/a/b"], into=d)
        assert "is not empty" in str(code), code
        out, code = run(m, "cmd_fetch", urls=["https://evil.example/a.png"],
                        into=os.path.join(d, "fresh"))
        assert code == 1 and out.startswith("skip\thttps://evil.example/a.png\tnot a Linear upload"), out
    print("  a used directory is refused; a non-Linear URL is never sent the key")


def test_eligible_is_a_flow_made_waiting_sub_issue_of_support():
    m = load(Fake([]))
    for kind, ok in (("backlog", True), ("unstarted", True), ("triage", False),
                     ("started", False), ("completed", False)):
        assert m.eligible(child("BE-1", kind=kind), ME) is ok, kind
    assert not m.eligible(child("BE-1", creator=OTHER), ME)
    assert not m.eligible(child("BE-1", parent=None), ME)
    assert not m.eligible(child("DES-1", team="DES"), ME)
    assert not m.eligible(issue("SUP-1", label="doable"), ME)
    print("  waiting sub-issues the flow made in a repo's team, under Support; nothing else")


def test_a_claim_registers_first_and_is_undone_whole_when_linear_refuses():
    comments = {"BE-1": [verdict_comment()]}
    fake = Fake([child("BE-1")], comments)
    m = load(fake)
    out, code = run(m, "cmd_claim", key="BE-1", agent="lin-be-1", model="sonnet",
                    reasoning_effort="medium")
    assert code == 0 and out.startswith("CLAIMED\tBE-1\thoopit/api"), (out, code)
    assert [a for a, _ in m.hb_calls] == [("claims", "list"), ("claims", "put")], m.hb_calls
    (u,) = fake.ops("Update")
    assert u["input"] == {"assigneeId": ME, "stateId": "s-InProgress"}, u
    assert "`lin-be-1` on `sonnet` at `medium` effort" in fake.ops("Comment")[0]["input"]["body"]

    fake = Fake([child("BE-1")], comments, fail={"Update"})
    m = load(fake)
    _, code = run(m, "cmd_claim", key="BE-1", agent="x", model=None, reasoning_effort=None)
    assert "the claim is undone" in str(code), code
    assert [a for a, _ in m.hb_calls][-1] == ("claims", "drop", "linear", "BE-1"), m.hb_calls

    fake = Fake([child("BE-1")], comments, fail={"Comment"})
    m = load(fake)
    _, code = run(m, "cmd_claim", key="BE-1", agent="x", model=None, reasoning_effort=None)
    assert "the claim is undone" in str(code), code
    moved, back = fake.ops("Update")
    assert back["input"] == {"assigneeId": None, "stateId": "s-Backlog"}, back

    fake = Fake([child("BE-1")], comments, fail={"Comment"})
    m = load(fake, hb=lambda args, stdin: (1, "", "disk full") if args[1] == "drop" else (0, "", ""))
    _, code = run(m, "cmd_claim", key="BE-1", agent="x", model=None, reasoning_effort=None)
    assert "registry claim is still there: disk full" in str(code), code

    m = load(Fake([child("BE-1", assignee=OTHER)], comments))
    _, code = run(m, "cmd_claim", key="BE-1", agent="x", model=None, reasoning_effort=None)
    assert "not dispatchable" in str(code) and m.hb_calls == [], code

    listed = lambda args, stdin: ((0, "linear:BE-1\thoopit/api\ta\t-\thttps://github.com/hoopit/api/pull/9\tt", "")
                                  if args == ("claims", "list") else (0, "", ""))
    m = load(Fake([child("BE-1")], comments), hb=listed)
    _, code = run(m, "cmd_claim", key="BE-1", agent="x", model=None, reasoning_effort=None)
    assert "already in the claims registry" in str(code), code
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

    fake = Fake([child("BE-1")], {"BE-1": [
        verdict_comment(at="2026-10-02T00:00:00Z"),
        verdict_comment(verdict="not-doable", effort=None, at="2026-10-03T00:00:00Z")]})
    out, code = run(load(fake), "cmd_candidates")
    assert json.loads(out) == [] and code == 1, out
    print("  another user's line, a quoted line and bad JSON are ignored; a newer not-doable wins")


def test_release_hands_back_to_its_team_backlog_and_unassigns_only_me():
    fake = Fake([child("BE-1", state="In Progress", kind="started", assignee=ME)])
    m = load(fake)
    run(m, "cmd_release", key="BE-1", reason="the premise was wrong")
    (u,) = fake.ops("Update")
    assert u["input"] == {"removedLabelIds": ["L-doable"], "addedLabelIds": ["L-released"],
                          "stateId": "s-Backlog", "assigneeId": None}, u
    assert m.hb_calls[-1][0] == ("claims", "drop", "linear", "BE-1")
    fake = Fake([child("BE-1", state="In Progress", kind="started", assignee=OTHER)])
    run(load(fake), "cmd_release", key="BE-1", reason="r")
    assert "assigneeId" not in fake.ops("Update")[0]["input"]
    print("  released, back in its team's Backlog, unassigned from me — a colleague's assignment is left alone")


def test_settle_ends_only_finished_claims():
    pr = lambda n: f"https://github.com/hoopit/api/pull/{n}"
    listing = "\n".join([
        f"linear:BE-1\thoopit/api\ta\t-\t{pr(1)}\tt",          # merged
        f"linear:BE-2\thoopit/api\ta\t-\t{pr(2)}\tt",          # closed unmerged
        f"linear:BE-3\thoopit/api\ta\t-\t{pr(3)}\tt",          # still open
        f"linear:BE-4\thoopit/api\ta\t-\t-\tt",                # ended in Linear
        f"linear:BE-5\thoopit/api\ta\t-\t-\tt",                # no PR yet
        f"github:x\thoopit/api\ta\t-\t-\tt"])                  # another source
    issues = lambda: [child(k, state="In Progress", kind="started", assignee=ME)
                      for k in ("BE-1", "BE-2", "BE-3", "BE-5")] + [
        child("BE-4", state="Done", kind="completed", label=None)]
    pulls = {"hoopit/api#1": "MERGED", "hoopit/api#2": "CLOSED", "hoopit/api#3": "OPEN"}
    hb = lambda args, stdin: (0, listing, "") if args == ("claims", "list") else (0, "", "")

    fake = Fake(issues())
    m = load(fake, hb, pulls)
    out, code = run(m, "cmd_settle", apply=False)
    assert [l.split("\t")[:2] for l in out.splitlines()] == [
        ["merged", "BE-1"], ["closed", "BE-2"], ["ended", "BE-4"]], out
    assert fake.ops("Update") == [] and fake.ops("Comment") == [], "a dry run changed something"

    fake = Fake(issues())
    m = load(fake, hb, pulls)
    run(m, "cmd_settle", apply=True)
    drops = [a[3] for a, _ in m.hb_calls if a[:2] == ("claims", "drop")]
    assert drops == ["BE-1", "BE-2", "BE-4"], drops
    merged, closed = fake.ops("Update")
    assert merged == {"id": "id-BE-1", "input": {"removedLabelIds": ["L-doable"]}}, merged
    assert closed["id"] == "id-BE-2" and closed["input"]["addedLabelIds"] == ["L-released"], closed
    print("  merged and ended are dropped, closed is released; open, PR-less and github claims untouched")


def test_settle_reads_mixed_and_unreadable_prs_and_survives_a_failure():
    pr = lambda n: f"https://github.com/hoopit/api/pull/{n}"
    listing = "\n".join([
        f"linear:BE-1\thoopit/api\ta\t-\t{pr(1)},{pr(2)}\tt",   # closed + merged
        f"linear:BE-2\thoopit/api\ta\t-\t{pr(1)},{pr(9)}\tt",   # closed + unreadable
        f"linear:BE-3\thoopit/api\ta\t-\t{pr(1)}\tt",           # closed: release refused
        f"linear:BE-4\thoopit/api\ta\t-\t-\tt"])                # ended
    issues = [child(k, state="In Progress", kind="started", assignee=ME)
              for k in ("BE-1", "BE-2", "BE-3")] + [
        child("BE-4", state="Canceled", kind="canceled", label=None)]
    pulls = {"hoopit/api#1": "CLOSED", "hoopit/api#2": "MERGED"}
    hb = lambda args, stdin: (0, listing, "") if args == ("claims", "list") else (0, "", "")
    m = load(Fake(issues, fail={"Comment"}), hb, pulls)
    out, code = run(m, "cmd_settle", apply=True)
    assert [l.split("\t")[:2] for l in out.splitlines()] == [
        ["merged", "BE-1"], ["skip", "BE-3"], ["ended", "BE-4"]], out
    assert [a[3] for a, _ in m.hb_calls if a[:2] == ("claims", "drop")] == ["BE-1", "BE-4"]
    print("  closed+merged settles, an unreadable PR holds, a refused release is skipped")


def test_provision_adds_only_what_is_missing():
    fake = Fake([])
    m = load(fake)
    m.group_labels = lambda: ("G", {"doable": "L1", "not-doable": "L2"})
    out, _ = run(m, "cmd_provision", apply=True)
    assert out.splitlines() == ["OK\tagent/doable", "OK\tagent/not-doable", "ADD\tagent/split",
                                "ADD\tagent/released"], out
    assert [v["input"]["name"] for v in fake.ops("Label")] == ["split", "released"]
    print("  existing labels kept; split and released created under the group")


def test_the_registry_contract_holds_against_the_real_hoopit_board():
    """The rest of this file stubs `hoopit-board`. This runs the real one, against a
    scratch registry, so a change to `claims list`'s columns or `put`'s schema fails here."""
    board = SCRIPT.parents[3] / "plugins" / "github-tracker" / "bin" / "hoopit-board"
    with tempfile.TemporaryDirectory() as state:
        env = {**os.environ, "XDG_STATE_HOME": state}
        m = load(Fake([child("BE-1")], {"BE-1": [verdict_comment()]}))
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


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        print(f"{t.__name__}:")
        t()
    print(f"\n{len(tests)} passed")
