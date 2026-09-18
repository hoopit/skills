#!/usr/bin/env python3
"""Pins `hoopit-board batch`'s write loop and `next`'s collision judgement. Run it by
hand after editing either:

    python3 scripts/test_hoopit_board.py

No network and no pytest — `gql_write`, `board` and `locate` are stubbed, so the whole
file runs offline in well under a second.

`next` is here for a second reason: it decides with no model in the loop, so a wrong
verdict dispatches two agents onto one file with nobody watching. The judgement it asks
of Jev must be strictly additive and must fail open, and neither property is visible from
reading one branch.

What `batch` is here for: GitHub refuses a request past its own complexity guard with
"Resource limits for this query exceeded", and the ceiling is not fixed — the same
50-alias request goes through on a fresh point budget and is refused deep into a spent
one. So the guard fires rarely and unpredictably, ordinary use never reaches the retry
that handles it, and the failure it prevents is the expensive kind: a sweep that writes
half the board and reports success. Nothing else exercises this path.
"""
import argparse, contextlib, importlib.machinery, importlib.util, io, json, pathlib, re, sys

SCRIPT = pathlib.Path(__file__).with_name("hoopit-board")


def load():
    """A fresh module with the network stubbed out. `hoopit-board` has no `.py`
    suffix, so it needs its loader named explicitly."""
    spec = importlib.util.spec_from_loader("hb", importlib.machinery.SourceFileLoader("hb", str(SCRIPT)))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)          # __name__ is "hb", so main() does not run
    m.board = lambda: [{"repo": "hoopit/api", "n": i, "item_id": f"I{i}",
                        "content_id": f"C{i}", "type": "Issue"} for i in range(1, 61)]
    # The date field's BATCH_FIELDS entry is None — it has no options to enumerate.
    m.issue_fields = lambda: {f: {"id": f"F{f}", "options": [
        {"name": v, "id": f"O{v}"} for v in (m.BATCH_FIELDS[f] or [])]}
        for f in m.BATCH_FIELDS}
    return m


def run(m, lines):
    """cmd_batch over the given stdin. Returns (stdout, stderr, exit code)."""
    sys.stdin = io.StringIO("".join(lines))
    out, err, code = io.StringIO(), io.StringIO(), 0
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            m.cmd_batch(None)
        except SystemExit as e:
            code = e.code
    return out.getvalue(), err.getvalue(), code


def sets(out):
    return [l for l in out.splitlines() if l.startswith("SET")]


def capped(fn, limit=200):
    """A stub that gives up rather than hanging. A retry that fails to shrink spins
    forever, and a test that hangs reports nothing — this turns that into a red."""
    calls = [0]

    def wrapped(q):
        calls[0] += 1
        assert calls[0] <= limit, f"gave up after {limit} requests: the retry is not shrinking"
        return fn(q)

    return wrapped


ONE = [f"hoopit/api#{i}\tAutonomy=Unattended\n" for i in range(1, 61)]
THREE = [f"hoopit/api#{i}\tPriority=P2\tEffort=M\tAutonomy=Unattended\n" for i in range(1, 61)]


def test_shrinks_until_the_request_fits():
    """A server that refuses anything over 7 aliases still gets all 60 items."""
    m = load()
    m.ALIASES_PER_REQUEST = 50
    tried = []

    def picky(q):
        n = q.count("setIssueFieldValue")
        tried.append(n)
        return "Resource limits for this query exceeded." if n > 7 else None

    m.gql_write = capped(picky)
    out, _, code = run(m, ONE)
    assert code == 0, code
    assert len(sets(out)) == len(set(sets(out))) == 60, "every item written exactly once"
    assert tried[0] == 50 and tried[-1] <= 7, tried
    print(f"  shrinks {tried[:4]}… and settles at {tried[-1]}")


def test_an_items_three_axes_ride_in_one_mutation():
    """Every alias in a request must be unique, or the server rejects the whole thing.

    An item's axes go in one `setIssueFieldValue` input list, so a request holds one
    alias per item however many axes it carries — and a SET line is all-or-nothing,
    which is what lets a mid-run failure name exactly which items landed."""
    m = load()
    m.ALIASES_PER_REQUEST = 50
    tried, aliases, fields_per_alias = [], [], []

    def picky(q):
        tried.append(q.count("setIssueFieldValue"))
        aliases.append(re.findall(r"\b(f\d+):", q))
        fields_per_alias.append(q.count("fieldId:") // max(tried[-1], 1))
        return "Resource limits for this query exceeded." if tried[-1] > 10 else None

    m.gql_write = capped(picky)
    out, _, code = run(m, THREE)
    assert code == 0 and len(sets(out)) == 60
    for names, n in zip(aliases, tried):
        assert len(names) == n, f"{n} mutations but {len(names)} aliases"
        assert len(set(names)) == n, f"duplicate alias in a request: {names}"
    assert set(fields_per_alias) == {3}, f"axes split across mutations: {fields_per_alias}"
    assert all(l.count("=") == 3 for l in sets(out)), "a SET line lost a field"
    print(f"  one alias an item, 3 axes inside it, requests of {sorted(set(tried))}")


def test_an_unshrinkable_refusal_stops():
    """A guard that refuses even one item exits rather than looping forever."""
    m = load()
    m.gql_write = capped(lambda q: "Resource limits for this query exceeded.")
    _, _, code = run(m, ONE)
    assert code != 0 and "0 of 60 items written" in str(code), code
    print("  exits, and says nothing was written")


def test_a_mid_run_failure_says_how_far_it_got():
    """The writes before the failure have landed; the message has to admit it."""
    m = load()
    m.ALIASES_PER_REQUEST = 10
    calls = [0]

    def flaky(q):
        calls[0] += 1
        return None if calls[0] <= 2 else '[{"message":"Something else broke"}]'

    m.gql_write = capped(flaky)
    out, _, code = run(m, ONE)
    assert code != 0 and "20 of 60 items written" in str(code), code
    assert len(sets(out)) == 20, "printed a SET line for a write that did not land"
    print("  reports '20 of 60 items written', prints 20 SET lines")


def test_the_happy_path_is_unchanged():
    m = load()
    m.gql_write = capped(lambda q: None)
    out, err, code = run(m, ONE)
    assert code == 0 and len(sets(out)) == 60 and "60 items" in err
    print("  60 SET lines, '60 items' on stderr")


def test_bad_input_is_refused_before_any_write():
    """Validation runs before the board read, so a typo costs nothing and writes nothing."""
    for line, expect in [("hoopit/api#1\tAutonomy=Bogus\n", "no option 'Bogus'"),
                         ("hoopit/api#1\tNonsense=X\n", "no such field"),
                         ("not-a-tag\tAutonomy=Unattended\n", "not a <repo>#<n>")]:
        m = load()
        m.board = lambda: (_ for _ in ()).throw(AssertionError("read the board before validating"))
        m.gql_write = lambda q: (_ for _ in ()).throw(AssertionError("wrote before validating"))
        _, _, code = run(m, [line])
        assert code != 0 and expect in str(code), (line, code)
    print("  three bad inputs refused, board never read")


# --- `next`'s collision judgement -------------------------------------------------------

def item(n, status="Backlog", effort="M", repo="hoopit/api", prs=(), title=None):
    return {"n": n, "repo": repo, "url": f"https://github.com/{repo}/issues/{n}",
            "title": title or f"issue {n}", "type": "Issue", "updated": None,
            "status": status, "priority": "P2", "effort": effort,
            "autonomy": "Unattended", "not_before": "", "content_id": f"C{n}",
            "prs": list(prs), "pr_state": {u: "OPEN" for u in prs},
            "pr_updated": {}, "item_id": f"I{n}"}


def next_module(items, owners=None, per_pr=None, bodies=None, footprint=None, apps=()):
    """A `next` with the whole network stubbed: the board, the open-PR sweep, the issue
    body reads and the checkout. Only the judgement is left to the test."""
    m = load()
    m.board = lambda: items
    m.footprints = lambda repos: (m.defaultdict(list, owners or {}), dict(per_pr or {}))
    m.repo_files = lambda repo, _c={}: (set(), {}, True)
    m.migration_apps = lambda repo: list(apps)
    m.deploy_gate = lambda repo, body: ""
    m.body_footprint = lambda repo, body: list((footprint or {}).get(body, []))
    m.gh = lambda *a, **k: (bodies or {}).get(int(a[1].rsplit("/", 1)[-1]), "")
    m.judge_candidate.ask = lambda state, questions: (None, "the test set no stub")
    return m


def run_next(m, target=15, no_judge=False):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = m.cmd_next(argparse.Namespace(target=target, exclude=[], repos=None,
                                             no_judge=no_judge))
    return json.loads(out.getvalue()), code


def only(d, key):
    return [f'{e["repo"]}#{e["n"]}' for e in d[key]]


def test_a_judgement_that_cannot_run_dispatches_exactly_as_before():
    """The fail-open contract. No key, a timeout, a 429 — the tick is the tick it would
    have been, and the reason is in the output rather than in a dropped candidate."""
    items = [item(1)]
    m = next_module(items, bodies={1: "rewrite the member import"})
    m.judge_candidate.ask = lambda s, q: (None, "HTTP 429")
    judged, code = run_next(m)

    m2 = next_module([item(1)], bodies={1: "rewrite the member import"})
    plain, code2 = run_next(m2, no_judge=True)

    assert code == code2 == 0
    assert only(judged, "startable") == only(plain, "startable") == ["hoopit/api#1"]
    assert judged["judgement"] == "failed: HTTP 429" and plain["judgement"] == "off"
    del judged["judgement"], plain["judgement"]
    assert judged == plain, "a failed judgement changed the tick"
    print("  a 429 leaves the tick byte-identical to --no-judge")


def test_prose_only_work_is_caught_against_an_open_pr():
    """The gap the judgement exists for: an issue naming no resolvable path footprints
    empty, clears every exact test, and dispatches onto a PR's files."""
    items = [item(1, title="fix the member import timeout")]
    per_pr = {"hoopit/api#900": {"repo": "hoopit/api", "title": "member import",
                                 "files": ["niflib/nif_ems_client.py"]}}
    m = next_module(items, per_pr=per_pr, bodies={1: "the member import stalls forever"})
    m.judge_candidate.ask = lambda s, q: ({"pr:hoopit/api#900": {"noul": 0.91},
                                           "adds_migration": {"noul": 0.02}}, None)
    d, code = run_next(m)
    assert code == 1 and d["startable"] == []
    assert only(d, "blocked") == ["hoopit/api#1"]
    assert d["blocked"][0]["judged"] == {"hoopit/api#900": 0.91}
    print("  0.91 against an open PR blocks a candidate no path test would stop")


def test_the_uncertain_band_hands_the_item_back():
    """Between the thresholds is neither a dispatch nor a rejection: untuned numbers must
    not invent a verdict on work nobody is watching."""
    items = [item(1)]
    per_pr = {"hoopit/api#900": {"repo": "hoopit/api", "title": "p", "files": ["a.py"]}}
    m = next_module(items, per_pr=per_pr, bodies={1: "something adjacent"})
    m.judge_candidate.ask = lambda s, q: ({"pr:hoopit/api#900": {"noul": 0.5},
                                           "adds_migration": {"noul": 0.0}}, None)
    d, code = run_next(m)
    assert only(d, "needs_judgement") == ["hoopit/api#1"]
    assert d["startable"] == [] and d["blocked"] == [] and code == 1
    print("  0.5 lands in needs_judgement, dispatched by nobody")


def test_an_exact_collision_is_never_put_to_the_model():
    """A resolved path is ground truth. Asking about it would spend a request to be
    overruled, and a model that said `no` must not be able to clear it."""
    items = [item(1)]
    m = next_module(items, owners={("hoopit/api", "payments/models.py"): ["#900"]},
                    bodies={1: "b"}, footprint={"b": ["payments/models.py"]})

    def refuse(state, questions):
        raise AssertionError("asked the model about a path collision it already had")

    m.judge_candidate.ask = refuse
    d, code = run_next(m)
    assert only(d, "blocked") == ["hoopit/api#1"]
    assert d["blocked"][0]["collides"] == {"payments/models.py": ["#900"]}
    print("  an exact hit blocks without a request")


def test_a_migration_the_model_places_collides_on_the_graph():
    """`MIGRATION_HINT` fires on prose and misses work that adds a migration without
    saying so. A placed token collides with the app whose graph is already taken."""
    items = [item(1)]
    owners = {("hoopit/api", "MIGRATION-GRAPH:payments"): ["#900"]}
    m = next_module(items, owners=owners, bodies={1: "the order user must match"},
                    apps=["payments", "dugnad"])
    m.judge_candidate.ask = lambda s, q: ({"adds_migration": {"noul": 0.84},
                                           "migration_app": {"choice": "payments"}}, None)
    d, code = run_next(m)
    assert only(d, "blocked") == ["hoopit/api#1"]
    assert d["blocked"][0]["judged"] == {"MIGRATION-GRAPH:payments held by #900": 0.84}
    print("  a migration placed in `payments` collides with the PR holding that graph")


def test_an_unowned_migration_token_still_guards_the_rest_of_the_tick():
    """Two candidates that each add a migration to one app must not both go out on the
    same tick: the first one picked takes the graph."""
    items = [item(1), item(2)]
    m = next_module(items, bodies={1: "add a constraint", 2: "add another constraint"},
                    apps=["payments"])
    m.judge_candidate.ask = lambda s, q: ({"adds_migration": {"noul": 0.9},
                                           "migration_app": {"choice": "payments"}}, None)
    d, code = run_next(m)
    assert only(d, "startable") == ["hoopit/api#1"], d["startable"]
    assert only(d, "blocked") == ["hoopit/api#2"], d["blocked"]
    print("  the first pick takes the migration graph, the second is held")



if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        print(f"{t.__name__}:")
        t()
    print(f"\n{len(tests)} passed")
