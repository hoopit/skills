#!/usr/bin/env python3
"""Pins `hoopit-board batch`'s write loop, `next`'s collision judgement, `decisions`'
naming judgement, `scan`'s duplicate judgement, the deploy gate, the per-user config
(`init`, `config`, and the refusal without one), what `provision` writes to a board, and the
Agent field: the hook's state machine, `start` and `bind`, and the sync that writes the board.
Run it by hand after editing any of them:

    python3 scripts/test_hoopit_board.py

No network and no pytest — `gql_write`, `board`, `board_probe` and `locate` are stubbed, so the whole
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
import argparse, contextlib, importlib.machinery, importlib.util, io, json, os, pathlib, re
import subprocess, sys, tempfile

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "bin" / "hoopit-board"
LADDER = SCRIPT.parents[3] / "personal" / "dispatch-ladder" / "ladder.json"
# Every config a test writes lives here, and `HOOPIT_BOARD_CONFIG` points into it: a test
# must never read or write the developer's own config.
SCRATCH = tempfile.TemporaryDirectory(prefix="hoopit-board-test-")
TMP = pathlib.Path(SCRATCH.name)
# The Agent field's session files resolve against this; a test must never touch the
# developer's own sessions.
os.environ["XDG_STATE_HOME"] = str(TMP / "state")


def write_config(name="config.json", **over):
    """A config file under TMP, from a default that every earlier test assumes — the
    repos it names, a production branch that is deliberately not called `production`, and
    the shipped ladder — with `over` replacing top-level keys (None drops one)."""
    data = {"board": {"owner": "acme", "number": 7}, "checkouts": str(TMP / "checkouts"),
            "repos": [{"repo": r, "production_branch": "live"}
                      for r in ("hoopit/api", "hoopit/web-admin", "x/y")],
            "ladder": str(LADDER)}
    data.update(over)
    return write_raw(name, json.dumps({k: v for k, v in data.items() if v is not None}))


def write_raw(name, text):
    path = TMP / name
    path.write_text(text)
    return str(path)


def load(config=None, prime=True):
    """A fresh module with the network stubbed out, reading `config` (the default config
    when None). `hoopit-board` has no `.py` suffix, so it needs its loader named
    explicitly. `prime` reads the config now, so a module keeps its own whatever a later
    test points the environment at."""
    os.environ["HOOPIT_BOARD_CONFIG"] = config or write_config()
    spec = importlib.util.spec_from_loader("hb", importlib.machinery.SourceFileLoader("hb", str(SCRIPT)))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)          # __name__ is "hb", so main() does not run
    if prime:
        m.config()
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

def item(n, status="Ready", effort="M", repo="hoopit/api", prs=(), title=None, drafts=(),
         state="OPEN"):
    """A board item; `drafts` are the ones of its `prs` that are drafts."""
    return {"n": n, "repo": repo, "url": f"https://github.com/{repo}/issues/{n}",
            "title": title or f"issue {n}", "type": "Issue", "issue_type": "",
            "updated": None, "state": state,
            "status": status, "priority": "P2", "effort": effort,
            "autonomy": "Unattended", "not_before": "", "blockers": [], "body": "",
            "content_id": f"C{n}",
            "prs": list(prs), "pr_state": {u: "OPEN" for u in prs},
            "pr_updated": {}, "pr_draft": {u: u in drafts for u in prs},
            "item_id": f"I{n}"}


def next_module(items, owners=None, per_pr=None, bodies=None, paths=(), apps=(), config=None,
                real_gate=False):
    """A `next` with the whole network stubbed: the board, the open-PR sweep, the issue
    body reads and the checkout. Only the judgement is left to the test.

    `paths` is what the checkout holds, so `body_footprint` runs for real — which is where
    a body's prose and its backticked paths are told apart. `real_gate` leaves the deploy
    gate to run, for a test to stub what it reads."""
    m = load(config)
    m.board = lambda: items
    m.footprints = lambda repos, only=None: (m.defaultdict(list, owners or {}), dict(per_pr or {}))
    m.migration_apps = lambda repo: list(apps)
    if not real_gate:
        m.deploy_gate = lambda repo, body: ""
    m.repo_files = lambda repo, _c={}: (set(paths or ()), {}, True)
    # The body cache is the user's own file: a test must neither read nor overwrite it.
    m.body_cache_load = lambda: {}
    m.body_cache_save = lambda cache: None
    m.gh = lambda *a, **k: (bodies or {}).get(int(a[1].rsplit("/", 1)[-1]), "")
    # A key on the machine running the tests must not decide whether the judgement is
    # reachable: every test here says so itself, by stubbing `ask`.
    m.typesafe_key = lambda: "test-key"
    m.judge_candidate.ask = lambda state, questions: (None, "the test set no stub")
    return m


def run_next(m, target=15, no_judge=False, max_active=None, max_review=None):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = m.cmd_next(argparse.Namespace(target=target, exclude=[], scope=None,
                                             no_judge=no_judge, max_active=max_active,
                                             max_review=max_review, live_agents=None,
                                             idle_agents=None, skip_type=[],
                                             allow_manual=False))
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


def test_a_parent_with_open_children_holds_no_slot_and_never_starts():
    """A parent's work is its children, each counted on its own: counting the parent too
    spends a slot twice, and starting it hands one agent every child. Its own open PR
    still holds its files, and once its last child closes it counts again."""
    parent = dict(item(1, status="In progress", prs=["https://github.com/hoopit/api/pull/90"]),
                  open_children=2)
    ready_parent = dict(item(2), open_children=1)
    done_parent = dict(item(3, status="In progress"), open_children=0)
    per_pr = {"hoopit/api#90": {"repo": "hoopit/api", "title": "p", "files": ["a.py"]}}
    m = next_module([parent, ready_parent, done_parent, item(4)], per_pr=per_pr,
                    owners={("hoopit/api", "a.py"): ["#1"]},
                    bodies={4: "edit `a.py`"}, paths=["a.py"])
    swept, footprints = [], m.footprints
    m.footprints = lambda repos, only=None: swept.append(only) or footprints(repos, only)
    d, code = run_next(m, target=2, no_judge=True)
    assert swept == [{"https://github.com/hoopit/api/pull/90"}], swept
    assert d["in_flight"] == 1 and d["deficit"] == 1, d
    assert only(d, "parents") == ["hoopit/api#1", "hoopit/api#2"], d["parents"]
    assert only(d, "startable") == [] and only(d, "blocked") == ["hoopit/api#4"], d
    print("  parents hold no slot and never start; the parent's PR still holds a.py")


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
                    bodies={1: "rework `payments/models.py`"},
                    paths=["payments/models.py"])

    def refuse(state, questions):
        raise AssertionError("asked the model about a path collision it already had")

    m.judge_candidate.ask = refuse
    d, code = run_next(m)
    assert only(d, "blocked") == ["hoopit/api#1"]
    assert d["blocked"][0]["collides"] == {"payments/models.py": ["#900"]}
    print("  an exact hit blocks without a request")


def test_a_cited_instruction_file_is_no_footprint():
    """An issue quotes `AGENTS.md` for the rule it follows. Read as a file it edits, one
    open PR rewriting the rules holds every issue that quotes one."""
    items = [item(1)]
    m = next_module(items, owners={("hoopit/api", "AGENTS.md"): ["#900"],
                                   ("hoopit/api", "payments/AGENTS.md"): ["#900"]},
                    bodies={1: "`AGENTS.md:115-117` says so, as does `payments/AGENTS.md`; "
                               "the fix is in `payments/tasks.py`"},
                    paths=["AGENTS.md", "payments/AGENTS.md", "payments/tasks.py"])
    m.judge_candidate.ask = lambda s, q: ({"adds_migration": {"noul": 0.0}}, None)
    d, code = run_next(m)
    assert code == 0 and only(d, "startable") == ["hoopit/api#1"], d["blocked"]
    assert d["startable"][0]["footprint"] == ["payments/tasks.py"]
    print("  a quoted AGENTS.md neither blocks nor footprints")


def test_the_open_pr_sweep_skips_instruction_files():
    """The other side of the same rule: a PR's own edits to them own nothing, and a PR
    that edits nothing else is not put to a judgement."""
    m = load()
    files = {"900": ["AGENTS.md", "posts/AGENTS.md", ".claude/rules/testing.md"],
             "901": ["AGENTS.md", "posts/tasks.py"]}

    def rest(path, limit, **params):
        if path.endswith("/pulls"):
            return [{"number": int(n), "title": f"pr {n}", "user": {"login": "someone"},
                     "html_url": f"https://github.com/hoopit/api/pull/{n}"} for n in files]
        return [{"filename": f} for f in files[path.split("/")[-2]]]

    m.rest = rest
    owners, per_pr = m.footprints(["hoopit/api"])
    assert dict(owners) == {("hoopit/api", "posts/tasks.py"): ["#901"]}, dict(owners)
    assert list(per_pr) == ["hoopit/api#901"], per_pr
    assert per_pr["hoopit/api#901"]["files"] == ["posts/tasks.py"]
    assert per_pr["hoopit/api#901"]["author"] == "someone"
    assert per_pr["hoopit/api#901"]["url"] == "https://github.com/hoopit/api/pull/901"
    print("  a rules-only PR owns nothing and is never judged")


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




def test_prose_about_a_constraint_does_not_hold_the_migration_graph():
    """`MIGRATION_HINT` matches ordinary English. With the judgement reading the same
    words, a body that only talks about constraints mints nothing and dispatches."""
    items = [item(1)]
    owners = {("hoopit/api", "MIGRATION-GRAPH:payments"): ["#900"]}
    m = next_module(items, owners=owners, apps=["payments"],
                    bodies={1: "the constraint here is time: we regressed when we "
                               "migrated the reminder copy"})
    m.judge_candidate.ask = lambda s, q: ({"adds_migration": {"noul": 0.04}}, None)
    d, code = run_next(m)
    assert only(d, "startable") == ["hoopit/api#1"], d
    assert d["startable"][0]["footprint"] == []
    print("  a prose-only 'constraint' body starts, holding no graph")


def test_a_migration_the_prose_hinted_at_is_still_blocked_by_the_judgement():
    """The other half: the regex loses nothing it was right about. The same body, judged
    above `MIGRATION_YES`, is held exactly as it was before."""
    items = [item(1)]
    owners = {("hoopit/api", "MIGRATION-GRAPH:payments"): ["#900"]}
    m = next_module(items, owners=owners, apps=["payments"],
                    bodies={1: "add a constraint: an order must name its user"})
    m.judge_candidate.ask = lambda s, q: ({"adds_migration": {"noul": 0.84},
                                           "migration_app": {"choice": "payments"}}, None)
    d, code = run_next(m)
    assert only(d, "blocked") == ["hoopit/api#1"]
    assert d["blocked"][0]["judged"] == {"MIGRATION-GRAPH:payments held by #900": 0.84}
    print("  the same body, judged a migration, is held as before")


def test_the_regex_takes_over_when_the_judgement_cannot_run():
    """Fail-open in the one place it now matters: with nothing to read the prose, the
    guess is better than no migration test at all, so the tick is the old tick."""
    items = [item(1)]
    owners = {("hoopit/api", "MIGRATION-GRAPH:payments"): ["#900"]}
    body = "add a constraint: an order must name its user"
    for label, m in (("a failed request",
                      next_module([item(1)], owners=owners, apps=["payments"],
                                  bodies={1: body})),
                     ("--no-judge",
                      next_module([item(1)], owners=owners, apps=["payments"],
                                  bodies={1: body}))):
        m.judge_candidate.ask = lambda s, q: (None, "HTTP 429")
        d, code = run_next(m, no_judge=(label == "--no-judge"))
        assert only(d, "blocked") == ["hoopit/api#1"], (label, d)
        assert d["blocked"][0]["collides"] == {
            "MIGRATION-GRAPH:*": ["#900 (MIGRATION-GRAPH:payments)"]}, (label, d)
    print("  no judgement, and the regex holds the candidate as it always did")


def test_a_held_wildcard_collides_with_the_app_a_later_candidate_names():
    """`:*` is symmetric. Held by work in flight, it collides with a placed token the
    same way a candidate's `:*` collides with a held one — otherwise the token starves
    its own carrier and guards nothing."""
    items = [item(1)]
    owners = {("hoopit/api", "MIGRATION-GRAPH:*"): ["#900"]}
    m = next_module(items, owners=owners, apps=["payments"], bodies={1: "b"})
    m.judge_candidate.ask = lambda s, q: ({"adds_migration": {"noul": 0.9},
                                           "migration_app": {"choice": "payments"}}, None)
    d, code = run_next(m)
    assert only(d, "blocked") == ["hoopit/api#1"], d
    assert d["blocked"][0]["judged"] == {
        "MIGRATION-GRAPH:payments held by #900 (MIGRATION-GRAPH:*)": 0.9}, d
    print("  a held `:*` blocks the migration a later candidate places")


def test_a_repo_with_no_migrations_mints_no_migration_token():
    """`hoopit/web-admin` and `hoopit/flutter-app` have no migrations directory, so a
    token there is one no PR can ever own — and it would still enter `taken` and hold up
    a second pick on the same tick."""
    items = [item(1, repo="hoopit/web-admin")]
    m = next_module(items, bodies={1: "the migration to the new grid dropped a constraint"})
    d, code = run_next(m, no_judge=True)
    assert only(d, "startable") == ["hoopit/web-admin#1"], d
    assert d["startable"][0]["footprint"] == [], d
    print("  a repo with no migrations mints nothing, even on the regex path")


def test_a_migration_file_in_the_body_is_a_hard_token():
    """A resolved migration file is not a guess, so it holds its app's graph whatever the
    judgement says — and it is the only token the regex-free path mints."""
    items = [item(1)]
    owners = {("hoopit/api", "MIGRATION-GRAPH:payments"): ["#900"]}
    m = next_module(items, owners=owners, apps=["payments"],
                    paths=["payments/migrations/0042_order_user.py"],
                    bodies={1: "follow `payments/migrations/0042_order_user.py`"})

    def refuse(state, questions):
        raise AssertionError("asked the model about a path collision it already had")

    m.judge_candidate.ask = refuse
    d, code = run_next(m)
    assert only(d, "blocked") == ["hoopit/api#1"], d
    assert d["blocked"][0]["collides"] == {"MIGRATION-GRAPH:payments": ["#900"]}, d
    print("  a migration file named in the body holds its app's graph")



# ── decisions: is the decision named, and where ─────────────────────────────────────────

PROSE = """## Want

An order and its payment belong to the same member.

```
a = b

c = d
```

Repairing the three money-carrying rows changes what a member is charged, so it is
LK's call per #17017 — bring the pre-repair values here first.
"""
HEADED = "## The decision\n\nWhat expiry, and who refreshes?\n\n## Notes\n\nNone.\n"


def decisions(m, bodies, ask, **flags):
    """cmd_decisions over `bodies` ({issue number: body}). Returns (stdout, stderr)."""
    m.board = lambda: [{"repo": "hoopit/api", "n": n, "title": f"t{n}", "type": "Issue",
                        "status": "Backlog", "priority": "P2", "effort": "S",
                        "autonomy": "Needs decision", "url": f"u{n}"} for n in bodies]
    m.gh = lambda *args, **kw: bodies[int(args[1].rsplit("/", 1)[1])]
    m.judge_decision.ask = ask
    a = argparse.Namespace(**{"n": 5, "lines": 8, "unnamed": False, "manual": False, "waiting": False,
                              "no_judge": False, **flags})
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        m.cmd_decisions(a)
    return out.getvalue(), err.getvalue()


def test_a_fence_is_one_block_and_a_heading_its_own():
    blocks = load().body_blocks(PROSE)
    assert [b[0] for b in blocks] == ["## Want", "An order and its payment belong to the same member.",
                                      "```", "Repairing the three money-carrying rows changes "
                                      "what a member is charged, so it is"], blocks
    assert len(blocks[2]) == 5, blocks[2]


def test_a_decision_named_in_prose_is_quoted_from_the_body():
    m = load()
    out, _ = decisions(m, {1: PROSE}, lambda s, q: (
        {"named": {"noul": 0.75}, "opens": {"choice": "B03"}, "closes": {"choice": "B03"}}, None))
    assert "ANSWER THESE — 1 of 1" in out, out
    assert "    LK's call per #17017 — bring the pre-repair values here first." in out, out
    assert "0 name no decision" in out, out


def test_the_model_is_handed_block_ids_and_a_none():
    m, seen = load(), {}
    def ask(state, questions):
        seen.update(state=state, q=questions)
        return None, "stop here"
    decisions(m, {1: PROSE}, ask)
    assert seen["state"]["body"].startswith("B00| ## Want\n\nB01| An order"), seen["state"]
    assert list(seen["q"]["opens"]["criteria"]) == ["B00", "B01", "B02", "B03", "none"]


def test_a_low_probability_never_unnames_a_heading():
    m = load()
    out, _ = decisions(m, {1: HEADED}, lambda s, q: (
        {"named": {"noul": 0.2}, "opens": {"choice": "none"}, "closes": {"choice": "none"}}, None))
    assert "ANSWER THESE — 1 of 1" in out and "What expiry, and who refreshes?" in out, out


def test_a_judgement_that_cannot_run_leaves_the_regex_and_says_so():
    m = load()
    out, err = decisions(m, {1: PROSE, 2: HEADED}, lambda s, q: (None, "HTTP 429"))
    assert "ANSWER THESE — 1 of 1" in out and "1 name no decision" in out, out
    assert "HTTP 429" in err and "2 of 2" in err, err


def test_an_answer_outside_the_body_quotes_nothing():
    m = load()
    out, _ = decisions(m, {1: PROSE}, lambda s, q: (
        {"named": {"noul": 0.9}, "opens": {"choice": "B99"}, "closes": {"choice": "B00"}}, None))
    assert "no block of the body was picked out" in out, out


def test_a_stray_closing_block_does_not_widen_the_quote():
    m = load()
    body = "\n\n".join(f"para {n}" for n in range(12))
    out, _ = decisions(m, {1: body}, lambda s, q: (
        {"named": {"noul": 0.9}, "opens": {"choice": "B01"}, "closes": {"choice": "B11"}}, None),
        lines=40)
    assert "para 1" in out and "para 2" not in out, out


def test_no_judge_asks_nothing():
    m = load()
    def refuse(s, q):
        raise AssertionError("asked")
    out, err = decisions(m, {1: PROSE}, refuse, no_judge=True)
    assert "1 name no decision" in out and not err, (out, err)


# --- scan: the duplicate judgement ---------------------------------------------------

PODS = ("The iOS deploy job in `.github/workflows/deploy.yml` runs `pod install` from "
        "scratch. Cache `ios/Pods` keyed on `ios/Podfile.lock` with `actions/cache`.")
PUB = ("Every deploy job in `.github/workflows/deploy.yml` runs `flutter pub get` cold. "
       "Cache `~/.pub-cache` keyed on `pubspec.lock` with `actions/cache`.")
LOGOUT = ("Opening the app in the morning lands on the login screen. The access token only "
          "renews on a foreground timer in `lib/auth/session_manager.dart`, so the first "
          "request returns 401, which `AuthInterceptor` treats as a sign-out. On a 401, try "
          "the refresh token once before signing the user out.")
RENEW = ("`AuthInterceptor.onError` in `lib/auth/auth_interceptor.dart` calls `signOut()` "
         "for every 401. An expired access JWT is the common case, and the refresh token "
         "is still valid. On 401, call `SessionManager.refresh()` once and replay.")
SCAN_ISSUES = {1: ("ci: cache CocoaPods between deploys", PODS),
               2: ("ci: cache pub packages between deploys", PUB),
               3: ("Members get logged out when the app was in the background overnight", LOGOUT),
               4: ("auth: AuthInterceptor signs out on an expired JWT instead of renewing it", RENEW),
               5: ("economy: read money objects on the training-fee screens",
                   "The training-fee list in `economy/fees.tsx` renders `amount` as a bare "
                   "number. Read the money object the endpoint serves.")}


def scan(m, ask, no_judge=False, issues=SCAN_ISSUES):
    """cmd_scan over `issues` ({number: (title, body)}). Returns (stdout, stderr)."""
    rows = [{**item(n, title=t), "body": b} for n, (t, b) in issues.items()]
    m.board = lambda bodies=False: rows if bodies else [{**r, "body": ""} for r in rows]
    m.judge_pairs.ask = ask
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        m.cmd_scan(argparse.Namespace(no_judge=no_judge))
    return out.getvalue(), err.getvalue()


def relation(same, **probs):
    base = {"duplicate": 0.0, "absorb": 0.0, "related": 0.0, "unrelated": 0.0, **probs}
    return {"same_change": {"noul": same},
            "relation": {"choice": max(base, key=base.get), "probabilities": base}}


def by_titles(verdicts, default):
    """An `ask` that answers by the pair of titles in `state`, whichever way round."""
    def ask(state, questions):
        pair = frozenset((state["a"]["title"][:8], state["b"]["title"][:8]))
        return verdicts.get(pair, default), None
    return ask


AUTH = frozenset(("Members ", "auth: Au"))


def test_a_duplicate_with_no_shared_title_words_is_shortlisted_and_nominated():
    m = load()
    asked = []
    def ask(state, questions):
        asked.append(frozenset((state["a"]["title"][:8], state["b"]["title"][:8])))
        assert set(questions["relation"]["criteria"]) == {"duplicate", "absorb", "related", "unrelated"}
        assert state["a"]["body"] and state["b"]["body"], "the bodies are the evidence"
        return by_titles({AUTH: relation(0.95, duplicate=0.7, absorb=0.29, related=0.01)},
                         relation(0.05, related=0.98, absorb=0.02))(state, questions)
    out, err = scan(m, ask)
    assert AUTH in asked, asked
    merge = out.split("## DUPLICATE / ABSORB")[1].split("## DUPLICATE DOUBT")[0]
    # 0.70 on `duplicate` is a split between two ways of merging, not doubt about merging.
    assert "hoopit/api#3\thoopit/api#4\tduplicate" in merge and "merge:0.99" in merge, out


def test_a_title_overlap_pair_the_model_separates_is_dropped():
    m = load()
    out, err = scan(m, by_titles({}, relation(0.05, related=0.98, absorb=0.02)))
    assert "TITLE OVERLAP" not in out and "hoopit/api#1\t" not in out.split("## DUPLICATE /")[1], out
    assert "dropped as separate work" in out, out


def test_the_band_between_the_thresholds_is_a_doubt_with_its_numbers():
    m = load()
    out, _ = scan(m, by_titles({AUTH: relation(0.2, related=0.56, duplicate=0.42, absorb=0.02)},
                               relation(0.02, unrelated=1.0)))
    doubt = out.split("## DUPLICATE DOUBT")[1]
    assert "hoopit/api#3\thoopit/api#4\trelated\tsame-change:0.20\tmerge:0.44" in doubt, out
    assert "(none)" in out.split("## DUPLICATE /")[1].split("## DUPLICATE DOUBT")[0], out


def test_a_noul_the_choice_disagrees_with_is_a_doubt_not_a_drop():
    m = load()
    out, _ = scan(m, by_titles({AUTH: relation(0.8, related=0.9, duplicate=0.1)},
                               relation(0.02, unrelated=1.0)))
    assert "hoopit/api#3\thoopit/api#4" in out.split("## DUPLICATE DOUBT")[1], out


def test_a_judgement_that_cannot_run_prints_the_overlap_list_and_says_so():
    m = load()
    out, err = scan(m, lambda s, q: (None, "HTTP 503"))
    assert "## TITLE OVERLAP — candidate duplicates, judge them yourself" in out, out
    assert "hoopit/api#1\thoopit/api#2\tbetween,cache,deploys" in out, out
    assert "DUPLICATE" not in out and "HTTP 503" in err, (out, err)


def test_a_stray_failure_is_asked_once_more():
    m = load()
    m.DUP_RETRY_PAUSE = 0
    calls = []
    def ask(state, questions):
        calls.append(1)
        if len(calls) == 1:
            return None, "HTTP 503"
        return relation(0.02, unrelated=1.0), None
    out, err = scan(m, ask)
    assert not err and "shortlisted but not judged" not in out, (out, err)


def test_an_overlap_pair_whose_request_failed_is_still_listed():
    m = load()
    m.DUP_RETRY_PAUSE = 0
    def ask(state, questions):
        if state["a"]["title"].startswith("ci:") and state["b"]["title"].startswith("ci:"):
            return None, "HTTP 429"
        return relation(0.02, unrelated=1.0), None
    out, err = scan(m, ask)
    assert "shortlisted but not judged" in out and "hoopit/api#1\thoopit/api#2" in out, out
    assert "1 of" in err and "HTTP 429" in err, err


def test_scan_no_judge_asks_nothing():
    m = load()
    def refuse(s, q):
        raise AssertionError("asked")
    out, err = scan(m, refuse, no_judge=True)
    assert "## TITLE OVERLAP" in out and "hoopit/api#1\thoopit/api#2" in out and not err, (out, err)


# --- dispatches: the gate-notes judgement --------------------------------------------

NOTES = """## Summary

Fixes the export.

## Review gate

One round. Codex and a cold Standards reviewer.

### Skipped
- Codex challenge (High): the race is already on master.

## Testing

pytest

🤖 Generated with [Claude Code](https://claude.com/claude-code)
"""


def pr_row(n, rung, fix, notes="One round, clean."):
    return {"repo": "hoopit/api", "pr": n, "issue": n, "merged": f"2026-09-{n:02d}T00:00:00Z",
            "rung": rung, "model": None, "reasoning_effort": None, "commits": fix + 1,
            "fix_commits": fix, "findings": [], "released": 0, "url": "", "title": f"PR {n}",
            "gate_notes": notes, "gate": None}


def gate_answer(rework, disputed=0.05, broke=0.05):
    return {"rework": {"score": rework, "confidence": 0.9},
            "disputed": {"noul": disputed}, "challenge_broke": {"noul": broke}}


def dispatches(m, rows, ask, no_judge=False):
    """cmd_dispatches over `rows`, with no cache on disk. Returns (report, stderr, code)."""
    m.GATE_CACHE = None
    m.GATE_RETRY_PAUSE = 0
    m.dispatch_rows = lambda repo, since, limit: ([dict(r) for r in rows], False)
    m.judge_gates.ask = ask
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = m.cmd_dispatches(argparse.Namespace(repos=["hoopit/api"], since=14, limit=200,
                                                   no_judge=no_judge))
    return json.loads(out.getvalue()), err.getvalue(), code


def test_the_notes_block_runs_to_the_next_heading_of_its_depth():
    m = load()
    notes = m.gate_notes(NOTES)
    assert notes.startswith("One round.") and "### Skipped" in notes, notes
    assert "pytest" not in notes and "Fixes the export" not in notes, notes


def test_a_trailing_notes_block_stops_at_the_footer():
    m = load()
    notes = m.gate_notes("## Summary\n\nx\n\n## Code review (review-gate)\n\nClean.\n\n"
                         "🤖 Generated with [Claude Code](https://claude.com/claude-code)\n")
    assert notes == "Clean.", notes


def test_a_heading_about_reviewers_is_not_the_gate_notes():
    m = load()
    assert m.gate_notes("## Three decisions worth a reviewer's attention\n\nx\n") == ""
    assert m.gate_notes(None) == ""


def test_a_rung_clean_on_commits_and_disputed_in_the_notes_is_named():
    """The case the skill exists for: few fix commits because findings were argued away."""
    m = load()
    rows = ([pr_row(n, "sonnet/medium", 0) for n in (1, 2, 3)]
            + [pr_row(n, None, 4, notes="Four findings, all fixed.") for n in range(4, 14)])
    def ask(state, questions):
        return (gate_answer(1.0, disputed=0.9) if "clean" in state["notes"]
                else gate_answer(2.0)), None
    report, err, code = dispatches(m, rows, ask)
    rung = report["by_rung"]["sonnet/medium"]
    assert rung["fix_commits_median"] == 0 and rung["disputed_rate"] == 1.0, rung
    assert rung["flags"] == ["clean-but-disputed"], rung
    assert report["by_rung"]["(unattributed)"]["flags"] == [], report["by_rung"]
    assert report["population"]["gate_judged"] == 13 and code == 0 and not err, (report, err)
    assert report["dispatches"][0]["gate"]["rework"] == 2.0, report["dispatches"][0]
    assert "gate_notes" not in report["dispatches"][0]


def test_a_pr_without_notes_is_left_out_of_the_rework_numbers():
    m = load()
    rows = [pr_row(1, "opus/medium", 0, notes=""), pr_row(2, "opus/medium", 2)]
    report, _, _ = dispatches(m, rows, lambda s, q: (gate_answer(3.0), None))
    rung = report["by_rung"]["opus/medium"]
    assert (rung["gate_noted"], rung["gate_judged"], rung["rework_median"]) == (1, 1, 3.0), rung
    assert {r["pr"]: r["gate"] is None for r in report["dispatches"]} == {1: True, 2: False}


def test_a_gate_judgement_that_cannot_run_keeps_the_fix_commits_and_says_so():
    m = load()
    rows = [pr_row(1, "opus/medium", 2), pr_row(2, "opus/medium", 4)]
    report, err, code = dispatches(m, rows, lambda s, q: (None, "HTTP 429"))
    rung = report["by_rung"]["opus/medium"]
    assert rung["fix_commits_median"] == 4 and rung["rework_median"] is None, rung
    assert rung["flags"] == [] and code == 0, rung
    assert "HTTP 429" in err and "2 of 2" in report["gate_judgement"], (err, report)


def test_a_stray_gate_failure_is_asked_once_more():
    m = load()
    seen = []
    def ask(state, questions):
        seen.append(state["title"])
        if state["title"] == "PR 2" and seen.count("PR 2") == 1:
            return None, "HTTP 503"
        return gate_answer(1.0), None
    report, err, _ = dispatches(m, [pr_row(1, "opus/medium", 0), pr_row(2, "opus/medium", 0)], ask)
    assert report["by_rung"]["opus/medium"]["gate_judged"] == 2 and not err, (report, err)


def test_judged_notes_are_not_asked_about_twice():
    m = load()
    with tempfile.TemporaryDirectory() as d:
        asked = []
        def ask(state, questions):
            asked.append(state["title"])
            return gate_answer(2.0), None
        for _ in range(2):
            m.GATE_CACHE = f"{d}/cache/gate-notes.json"
            m.judge_gates.ask = ask
            rows = [pr_row(1, "opus/medium", 1)]
            assert m.judge_gates(rows) == [] and rows[0]["gate"]["rework"] == 2.0, rows
        assert asked == ["PR 1"], asked


def test_dispatches_no_judge_asks_nothing():
    m = load()
    def refuse(s, q):
        raise AssertionError("asked")
    report, err, _ = dispatches(m, [pr_row(1, "opus/medium", 1)], refuse, no_judge=True)
    assert report["gate_judgement"] == "--no-judge" and not err, (report, err)
    assert report["by_rung"]["opus/medium"]["rework_median"] is None


def gated(prs=None, promoted=()):
    """A module whose gates resolve offline. `prs` maps `repo#n` to whether that pull
    request is merged, its merge sha being `sha-<n>`; a PR missing from it cannot be read.
    `promoted` holds the shas `origin/production` already carries."""
    m = load()
    def rest_one(path):
        repo, n = path.removeprefix("repos/").split("/pulls/")
        merged = (prs or {}).get(f"{repo}#{n}")
        return None if merged is None else {"merged": merged, "merge_commit_sha": f"sha-{n}"}
    m.rest_one = rest_one
    m.promotion_state = lambda repo, sha: "" if sha in promoted else f"{sha} not promoted"
    return m


def check(m, body):
    """cmd_check on an open, unclaimed, unblocked issue in `x/y` with the given body.
    Returns its one line of output."""
    def gh(*a, **k):
        if a[0] == "issue":
            return {"state": "OPEN", "comments": [], "closedByPullRequestsReferences": []}
        return body
    m.gh = gh
    m.issue_gates = lambda repo, number: ("", [])
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        m.cmd_check(argparse.Namespace(repo="x/y", number=9))
    return out.getvalue().strip()


def test_a_gate_sharing_its_line_with_prose_still_holds():
    """hoopit/api#17507: the gate followed a sentence on one line, went unread, and an
    agent was dispatched against an unpromoted PR."""
    m = gated({"x/y#2": True})
    assert check(m, "Follows x/y#1. Gate: deployed x/y#2\n").startswith("SKIP"), "shared line"
    assert "sha-2 not promoted" in check(m, "Gate: deployed #2. Swap in the PR later.\n")


def test_a_gate_on_its_own_line_resolves_as_before():
    m = gated({"x/y#2": True}, promoted={"sha-2"})
    assert check(m, "Intro.\n\nGate: deployed x/y#2\n") == "START\tx/y#9"
    assert "not merged" in gated({"x/y#2": False}).deploy_gate("x/y", "Gate: deployed #2")
    assert gated(promoted={"abc1234"}).deploy_gate("x/y", "Gate: deployed abc1234") == ""


def test_every_gate_in_a_body_must_be_live():
    m = gated({"x/y#2": True, "x/y#3": True}, promoted={"sha-2"})
    why = m.deploy_gate("x/y", "Gate: deployed x/y#2\nGate: deployed x/y#3\n")
    assert why == "sha-3 not promoted", why


def test_a_gate_naming_nothing_readable_holds():
    m = gated()
    why = m.deploy_gate("x/y", "The client half waits. Gate: deployed <the api PR>\n")
    assert why.startswith("a gate names no pull request or sha") and "<the api PR>" in why, why
    # An issue, not a PR, cannot be read off the pulls endpoint: held, not passed over.
    assert "cannot be read" in m.deploy_gate("x/y", "Gate: deployed x/y#7. Replace it later.")


def test_a_gate_in_backticks_is_prose_not_a_gate():
    m = gated()
    body = "Once it exists, add a `Gate: deployed <pr>` line here.\n"
    assert m.deploy_gate("x/y", body) == "" and check(m, body) == "START\tx/y#9"
    assert m.deploy_gate("x/y", "No gates here, Gate keeper.") == ""


# --- the per-user config ---------------------------------------------------------------

def main(m, *argv):
    """`hoopit-board <argv>` through main(). Returns (stdout, stderr, exit code) — the code
    being the message where main() exits with one."""
    out, err = io.StringIO(), io.StringIO()
    saved, sys.argv = sys.argv, ["hoopit-board", *argv]
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                m.main()
                code = 0
            except SystemExit as e:
                code = e.code
    finally:
        sys.argv = saved
    return out.getvalue(), err.getvalue(), code


def refusing(config):
    """A module reading `config` whose network raises: a refusal must come before it."""
    m = load(config, prime=False)
    def boom(*a, **k):
        raise AssertionError("reached GitHub without a config")
    m.gh = m.gql = m.gql_write = m.board = m.board_probe = boom
    return m


SUBCOMMANDS = [["open"], ["next"], ["config"], ["check", "x/y", "1"],
               ["triage", "x/y", "1"], ["dispatches", "--no-judge"]]


def test_no_config_refuses_every_subcommand_and_names_init():
    path = str(TMP / "nowhere" / "config.json")
    for argv in SUBCOMMANDS:
        _, _, code = main(refusing(path), *argv)
        assert isinstance(code, str) and path in code and "hoopit-board init" in code, (argv, code)
    print(f"  {len(SUBCOMMANDS)} subcommands refuse, naming the file and `init`")


def test_an_invalid_config_refuses():
    cases = {
        "not JSON": write_raw("bad.json", "{"),
        "`board.owner`": write_config("b1.json", board={"number": 7}),
        "`board.number`": write_config("b2.json", board={"owner": "acme", "number": "7"}),
        "`repos` must list": write_config("b3.json", repos=[]),
        "no <owner>/<name>": write_config("b4.json", repos=[{"repo": "api",
                                                            "production_branch": None}]),
        "`production_branch`": write_config("b5.json", repos=[{"repo": "a/b"}]),
        "listed twice": write_config("b6.json", repos=[{"repo": "a/b", "production_branch": None}] * 2),
        "`checkouts`": write_config("b7.json", checkouts=""),
    }
    for expect, path in cases.items():
        _, _, code = main(refusing(path), "open")
        assert isinstance(code, str) and path in code and "hoopit-board init" in code, (expect, code)
        assert expect in code or expect == "not JSON" and "unreadable" in code, (expect, code)
    print(f"  {len(cases)} broken configs refused, each saying what is wrong")


def test_help_and_init_help_need_no_config():
    path = str(TMP / "nowhere" / "config.json")
    for argv in (["--help"], ["init", "--help"]):
        out, _, code = main(refusing(path), *argv)
        assert code == 0 and "usage: hoopit-board" in out, (argv, code)
    assert "--owner" in main(refusing(path), "init", "--help")[0]


def init_args(*extra):
    return ["init", "--owner", "acme", "--number", "7", "--checkouts", "~/src",
            "--repo", "acme/api:live", "--repo", "acme/app", *extra]


def test_init_writes_the_config_and_will_not_overwrite_it():
    path = str(TMP / "init" / "a" / "config.json")
    out, _, code = main(refusing(path), *init_args("--no-verify"))
    assert code == 0 and f"WROTE\t{path}" in out, (out, code)
    written = json.loads(pathlib.Path(path).read_text())
    assert written == {"board": {"owner": "acme", "number": 7}, "checkouts": "~/src",
                       "repos": [{"repo": "acme/api", "production_branch": "live"},
                                 {"repo": "acme/app", "production_branch": None}]}, written

    _, _, code = main(refusing(path), *init_args("--no-verify", "--ladder", str(LADDER)))
    assert isinstance(code, str) and "exists" in code and "--force" in code, code
    assert "ladder" not in json.loads(pathlib.Path(path).read_text()), "overwrote without --force"

    _, _, code = main(refusing(path), *init_args("--no-verify", "--force", "--ladder", str(LADDER)))
    assert code == 0 and json.loads(pathlib.Path(path).read_text())["ladder"] == str(LADDER)
    print("  writes it, refuses a second write, replaces it under --force")


def test_init_refuses_a_bad_repo_or_ladder_before_writing():
    path = str(TMP / "init" / "b" / "config.json")
    _, err, code = main(refusing(path), *init_args("--no-verify", "--repo", "acme/web:"))
    assert code == 2 and "acme/web:" in err, (code, err)
    broken = write_raw("broken-ladder.json", json.dumps({
        "models": ["a", "b"], "efforts": ["low", "high"],
        "rungs": {"XS": {"model": "b", "effort": "high"}, "S": {"model": "a", "effort": "low"},
                  "M": {"model": "b", "effort": "high"}, "L": {"model": "b", "effort": "high"},
                  "XL": {"model": "b", "effort": "high"}}}))
    _, _, code = main(refusing(path), *init_args("--no-verify", "--ladder", broken))
    assert "priced under" in str(code), code
    assert not os.path.exists(path), "wrote a config around a broken ladder"


REQUIRED_WORKFLOWS = ["Item added to project", "Item closed", "Pull request linked to issue",
                      "Item reopened"]


def status(name, oid=None, color="GRAY", description=""):
    return {"id": oid or f"opt-{name}", "name": name, "color": color, "description": description}


# The Status options GitHub gives a new board.
GITHUB_DEFAULTS = [status("Todo", "todo-id", "GREEN", "This item hasn't been started"),
                   status("In Progress", "wip-id", "YELLOW", "This is actively being worked on"),
                   status("Done", "done-id", "PURPLE", "This has been completed")]


AGENT_STATES = ["Working", "Needs you", "Idle", "Gone"]


def board_answer(statuses=None, board_fields=None, org_fields=None, items=3, disabled=(),
                 own_fields=(), agent=AGENT_STATES, note=True):
    """A VERIFY_QUERY answer. The defaults are a board carrying everything. `statuses`
    are names or `status()` dicts; `own_fields` are board fields of the project's own;
    `agent` the Agent field's options (None: no field), `note` whether Agent note exists."""
    statuses = ["Backlog", "Ready", "In progress", "In review", "Done"] \
        if statuses is None else statuses
    org = {"Priority": ["P0", "P1", "P2", "P3"], "Effort": ["XS", "S", "M", "L", "XL"],
           "Autonomy": ["Unattended", "Needs decision", "Manual", "Waiting"], "Start date": None}
    org = org if org_fields is None else org_fields
    on_board = list(org) if board_fields is None else board_fields
    return {"organization": {
        "projectV2": {"id": "PVT_7", "title": "Agent board", "items": {"totalCount": items},
            "workflows": {"nodes": [{"name": w, "enabled": w not in disabled}
                                    for w in [*REQUIRED_WORKFLOWS, "Pull request merged"]]},
            "fields": {"nodes": [
                {"id": "F_title", "name": "Title", "isIssueField": False},
                {"id": "F_status", "name": "Status", "isIssueField": False,
                 "options": [s if isinstance(s, dict) else status(s) for s in statuses]},
                *[{"id": f"F_{f}", "name": f, "isIssueField": True, "options": []}
                  for f in on_board],
                *[{"id": f"F_own_{f}", "name": f, "isIssueField": False, "options": []}
                  for f in own_fields],
                *([{"id": "F_agent", "name": "Agent", "isIssueField": False,
                    "dataType": "SINGLE_SELECT",
                    "options": [status(o, f"agent-{o}") for o in agent]}]
                  if agent is not None else []),
                *([{"id": "F_note", "name": "Agent note", "isIssueField": False,
                    "dataType": "TEXT"}] if note else [])]}},
        "issueFields": {"nodes": [
            {"id": f"IF_{f}", "name": f,
             **({"options": [{"name": o} for o in opts]} if opts else {})}
            for f, opts in org.items()]}}}


def run_init(answer, name, written=True):
    path = str(TMP / "init" / name / "config.json")
    m = refusing(path)
    asked = []
    def board_probe(owner, number):
        asked.append({"login": owner, "number": number})
        return answer
    m.board_probe = board_probe
    out, err, code = main(m, *init_args())
    assert asked == [{"login": "acme", "number": 7}], asked
    assert os.path.exists(path) == written, (path, written)
    assert not os.path.exists(path + ".tmp"), "left the aside copy behind"
    return out, err, code


def test_init_verifies_a_complete_board():
    out, _, code = run_init(board_answer(), "ok")
    assert code == 0 and "VERIFIED\thttps://github.com/orgs/acme/projects/7\tAgent board" in out, out


def test_init_lists_what_the_board_is_missing_and_creates_nothing():
    org = {"Priority": ["P0", "P1", "P2", "P3"], "Effort": ["XS", "S", "M", "L", "XL"],
           "Autonomy": ["Unattended", "Needs decision"]}
    out, err, code = run_init(board_answer(
        statuses=["Backlog", "Ready", "In progress", "Done"],
        board_fields=["Priority", "Autonomy"], org_fields=org), "missing")
    assert code == 1, (out, code)
    for line in ("Status has no option 'In review'",
                 "issue field 'Effort' is not added to the board",
                 "Autonomy has no option 'Manual'",
                 "Autonomy has no option 'Waiting'",
                 "acme has no issue field 'Start date'"):
        assert f"  {line}\n" in out, (line, out)
    assert "VERIFIED" not in out and "Nothing was created" in err, (out, err)
    out, err, code = run_init({"organization": {"projectV2": None, "issueFields": {"nodes": []}}},
                              "no-board", written=False)
    assert "not written: acme has no project 7" in str(code), (err, code)
    out, err, code = run_init({"organization": None}, "no-org", written=False)
    assert "acme is no organization" in str(code), (err, code)
    print("  a missing status, board field, option and org field each named; exit 1; "
          "a board that does not exist writes nothing")


def test_init_names_a_disabled_workflow_and_a_shadowing_field():
    out, _, code = run_init(board_answer(disabled=["Item added to project"],
                                         board_fields=["Effort", "Autonomy", "Start date"],
                                         own_fields=["Priority"]), "workflow")
    assert code == 1, (out, code)
    assert "  workflow 'Item added to project' is not enabled (it must set Status to " \
           "'Backlog')\n" in out, out
    assert "  the board's own field 'Priority' shadows the issue field\n" in out, out
    print("  a disabled required workflow and a same-named project field are both missing")


# --- whose turn: caps, the stale check and settle read a PR's draft state ----------------

PR = "https://github.com/hoopit/api/pull/"


def review_board():
    """Flight: 1 has no PR yet, 2 a draft, 3 a ready PR, 4 one of each, 6 a ready PR among
    more linked PRs than the query read — four an agent works and one a human waits on. 5
    is a closed issue a PR pulled back into review."""
    return [item(1, "In progress"),
            item(2, "In review", prs=[PR + "2"], drafts=[PR + "2"]),
            item(3, "In review", prs=[PR + "3"]),
            item(4, "In review", prs=[PR + "4", PR + "40"], drafts=[PR + "40"]),
            item(5, "In review", prs=[PR + "5"], state="CLOSED"),
            {**item(6, "In review", prs=[PR + "6"]), "prs_complete": False},
            item(9)]


def test_the_caps_split_flight_by_draft_state():
    board = review_board()
    d, _ = run_next(next_module(board), target=None, max_active=5, no_judge=True)
    assert (d["in_flight"], d["active"], d["review"]) == (5, 4, 1), d
    assert only(d, "unsettled") == ["hoopit/api#5"], d
    assert d["deficit"] == 1 and only(d, "startable") == ["hoopit/api#9"], d
    d, code = run_next(next_module(board), target=None, max_active=4, no_judge=True)
    assert d["deficit"] == 0 and code == 1, d
    d, code = run_next(next_module(board), target=None, max_active=5, max_review=1,
                       no_judge=True)
    assert d["review"] == 1 and d["deficit"] == 0 and code == 1, d
    d, _ = run_next(next_module(board), target=None, max_active=5, max_review=2, no_judge=True)
    assert d["deficit"] == 1, d
    print("  no PR, a draft, a mixed pair and a truncated list are active; only the "
          "all-ready PR awaits a human")


def test_a_ready_pr_is_never_stale_and_a_quiet_draft_is():
    m = load()
    items = review_board()[:4]
    for i in items:
        i["pr_updated"] = {u: "2026-01-01T00:00:00Z" for u in i["prs"]}
    m.board = lambda: items
    m.claim_of = lambda i: ("gh1", "2026-01-01T00:00:00Z")
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        m.cmd_stale(argparse.Namespace(older_than=6))
    rows = sorted((r.split("\t")[0], r.split("\t")[3]) for r in out.getvalue().splitlines())
    assert rows == [("hoopit/api#1", "no-pr"), ("hoopit/api#2", "pr-quiet"),
                    ("hoopit/api#4", "pr-quiet")], rows
    print("  a quiet draft is pr-quiet, a quiet ready PR is a human's and never stale")


def test_settle_moves_only_a_closed_issue_out_of_review():
    m = load()
    m.board = review_board
    fields = {"Status": {"id": "F_status", "options": []}}
    m.locate = lambda repo, n: ("PVT_7", fields, None, None)
    moved = []
    m.set_status = lambda pid, f, item_id, value: moved.append((pid, item_id, value))
    for apply, verb in ((False, "WOULD-SETTLE"), (True, "SETTLED")):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            m.cmd_settle(argparse.Namespace(apply=apply))
        assert out.getvalue() == f"{verb}\thoopit/api#5\thttps://github.com/hoopit/api/issues/5\n", \
            out.getvalue()
    assert moved == [("PVT_7", "I5", "Done")], moved
    print("  the closed issue goes to Done under --apply, the open ones stay, a dry run writes nothing")


# --- provision ---------------------------------------------------------------------------

def run_provision(answer, *extra, fail=None):
    """`hoopit-board provision` against `answer`, with no config anywhere. Returns
    (stdout lines, stderr, exit code, the mutations it sent); `fail` is the error every
    mutation answers with."""
    m = refusing(str(TMP / "nowhere" / "config.json"))
    writes = []
    m.board_probe = lambda owner, number: answer
    def gql_write(q):
        writes.append(q)
        return fail
    m.gql_write = gql_write
    out, err, code = main(m, "provision", "--owner", "acme", "--number", "7", *extra)
    return out.splitlines(), err, code, writes


def sent_options(query):
    """The (id, name, color) of each option an updateProjectV2Field mutation sends."""
    assert query.count("updateProjectV2Field") == 1, query
    return re.findall(r'\{(?:id:"([^"]*)", )?name:"([^"]*)", color:(\w+), description:"', query)


def test_provision_status_tables_agree():
    m = load()
    assert list(m.STATUS_STYLE) == m.STATUSES
    assert [w for w, _ in m.REQUIRED_WORKFLOWS] == REQUIRED_WORKFLOWS


def test_provision_a_fresh_board_renames_appends_and_drops_the_unused_todo():
    answer = board_answer(statuses=GITHUB_DEFAULTS, items=0)
    lines, _, code, writes = run_provision(answer)
    assert writes == [] and code == 1 and lines[-1] == \
        "NOT READY\thttps://github.com/orgs/acme/projects/7", (writes, code, lines)
    for line in ("OK\t0 items on the board, archived included",
                 "MISSING\tStatus option 'Backlog'",
                 "MISSING\tStatus option 'In progress', renamed from 'In Progress' with its items",
                 "OK\tStatus option 'Done'",
                 "MISSING\tStatus option 'Todo' removed: GitHub's default, and the board has no items"):
        assert line in lines, (line, lines)

    lines, _, code, writes = run_provision(answer, "--apply")
    assert code == 0 and lines[-1] == "READY\thttps://github.com/orgs/acme/projects/7", lines
    assert len(writes) == 1 and 'fieldId:"F_status"' in writes[0], writes
    assert sent_options(writes[0]) == [
        ("", "Backlog", "GREEN"), ("", "Ready", "BLUE"), ("wip-id", "In progress", "YELLOW"),
        ("", "In review", "PURPLE"), ("done-id", "Done", "PURPLE")]
    assert 'description:"This item hasn\'t been started"' in writes[0], writes[0]
    assert "ADDED\tStatus option 'In progress', renamed from 'In Progress' with its items" in lines
    assert not any(l.startswith(("MISSING", "MANUAL")) for l in lines), lines
    print("  Todo dropped, In Progress renamed on its id, three appended, one mutation")


def test_provision_keeps_todo_on_a_board_with_items():
    lines, _, code, writes = run_provision(board_answer(statuses=GITHUB_DEFAULTS, items=4),
                                           "--apply")
    assert code == 0 and len(writes) == 1, (code, writes)
    sent = sent_options(writes[0])
    assert [n for _, n, _ in sent] == [
        "Backlog", "Ready", "In progress", "In review", "Done", "Todo"], sent
    assert sent[-1] == ("todo-id", "Todo", "GREEN"), sent
    assert "OK\tStatus option 'Todo' kept: GitHub's default, and the board's items may hold it" \
        in lines, lines


def test_provision_a_complete_board_writes_nothing_and_is_ready():
    lines, err, code, writes = run_provision(board_answer(statuses=[
        *(status(s) for s in ["Backlog", "Ready", "In progress", "In review", "Done"]),
        status("Parked")]), "--apply")
    assert writes == [] and code == 0 and err == "", (writes, code, err)
    assert lines[-1] == "READY\thttps://github.com/orgs/acme/projects/7", lines
    assert all(l.startswith("OK\t") for l in lines[:-1]), lines
    assert "OK\tStatus option 'Parked' kept: this script never sets it" in lines, lines
    assert "OK\tworkflow 'Item closed' enabled: it must set Status to 'Done'" in lines, lines
    print("  every line OK, no mutation even under --apply, exit 0")


def test_provision_leaves_the_org_fields_to_an_admin():
    org = {"Priority": ["P0", "P1", "P2", "P3"], "Effort": ["XS", "S", "M", "L"],
           "Start date": None}
    lines, _, code, writes = run_provision(
        board_answer(org_fields=org, board_fields=["Priority", "Effort", "Start date"]),
        "--apply")
    assert writes == [] and code == 1, (writes, code)
    assert "MANUAL\torg issue field 'Autonomy'\tan org admin adds it to acme's issue fields, " \
           "with the options Unattended, Needs decision, Manual, Waiting" in lines, lines
    assert "MANUAL\torg issue field 'Effort' option 'XL'\tan org admin adds it to acme's " \
           "issue field" in lines, lines
    assert lines[-1].startswith("NOT READY\t"), lines


def test_provision_adds_an_org_field_the_board_lacks():
    answer = board_answer(board_fields=["Priority", "Effort", "Autonomy"])
    lines, _, code, writes = run_provision(answer)
    assert writes == [] and code == 1 and "MISSING\tissue field 'Start date' on the board" \
        in lines, (writes, lines)
    lines, _, code, writes = run_provision(answer, "--apply")
    assert writes == ['mutation{ createProjectV2IssueField(input:{projectId:"PVT_7", '
                      'issueFieldId:"IF_Start date"}){ clientMutationId } }'], writes
    assert code == 0 and "ADDED\tissue field 'Start date' on the board" in lines, lines

    lines, err, code, writes = run_provision(answer, "--apply", fail="FORBIDDEN")
    assert code == 1 and "MISSING\tissue field 'Start date' on the board" in lines, lines
    assert "FORBIDDEN" in err, err
    print("  added with createProjectV2IssueField; a refused write stays MISSING")


def test_provision_names_a_disabled_workflow_and_a_shadowing_field():
    lines, _, code, writes = run_provision(board_answer(
        disabled=["Pull request linked to issue"],
        board_fields=["Effort", "Autonomy", "Start date"], own_fields=["Priority"]), "--apply")
    assert writes == [] and code == 1, (writes, code)
    assert "MANUAL\tworkflow 'Pull request linked to issue'\tenable it at " \
           "https://github.com/orgs/acme/projects/7/workflows, setting Status to 'In review'" \
           in lines, lines
    assert any(l.startswith("MANUAL\tissue field 'Priority' on the board\tthe board has a "
                            "field of its own") for l in lines), lines


def test_provision_refuses_a_board_that_is_not_there():
    for answer, why in (({"organization": {"projectV2": None, "issueFields": {"nodes": []}}},
                         "acme has no project 7"),
                        ({"organization": None}, "acme is no organization")):
        _, _, code, writes = run_provision(answer, "--apply")
        assert writes == [] and why in str(code), (code, writes)
    out, _, code = main(refusing(str(TMP / "nowhere" / "config.json")), "provision", "--help")
    assert code == 0 and "--apply" in out, (code, out)


def test_probe_answer_reads_not_found_as_absence():
    m = load(None)
    nf = json.dumps({"data": {"organization": {"projectV2": None}},
                     "errors": [{"type": "NOT_FOUND", "message": "Could not resolve"}]})
    assert m.probe_answer(1, nf, "gh: Could not resolve") == {"organization": {"projectV2": None}}
    ok = json.dumps({"data": {"organization": {"projectV2": {"title": "B"}}}})
    assert m.probe_answer(0, ok, "") == {"organization": {"projectV2": {"title": "B"}}}
    for code, out, err in ((1, "", "HTTP 401"),
                           (1, json.dumps({"errors": [{"type": "FORBIDDEN"}]}), "")):
        try:
            m.probe_answer(code, out, err)
        except SystemExit:
            continue
        raise AssertionError(f"accepted {out or err}")
    print("  NOT_FOUND reads as an absent board; any other error exits")


def test_init_stores_a_relative_checkouts_as_absolute():
    path = str(TMP / "init" / "relative" / "config.json")
    m = refusing(path)
    args = list(init_args())
    args[args.index("--checkouts") + 1] = "rel/dir"
    main(m, *args, "--no-verify")
    stored = json.load(open(path))["checkouts"]
    assert stored == os.path.abspath("rel/dir"), stored
    print("  a relative --checkouts is stored absolute")


def test_a_ladder_missing_its_keys_exits_cleanly():
    m = load(None)
    for body in ({"models": ["a"]}, {"models": [], "efforts": [], "rungs": ["XS"]}):
        bad = write_raw("keyless-ladder.json", json.dumps(body))
        try:
            m.load_ladder(bad)
        except SystemExit as e:
            assert "needs `models`" in str(e), e
            continue
        raise AssertionError(f"loaded {body}")
    print("  a ladder missing its keys exits with the file named, not a traceback")


def test_config_prints_the_board_repos_and_ladder():
    checkouts = TMP / "cfg-checkouts"
    (checkouts / "api").mkdir(parents=True, exist_ok=True)
    path = write_config("printed.json", checkouts=str(checkouts),
                        repos=[{"repo": "acme/api", "production_branch": "live"},
                               {"repo": "acme/app", "production_branch": None}])
    out, _, code = main(load(path), "config")
    assert code == 0, code
    assert out.splitlines() == [
        f"config\t{path}",
        "board\thttps://github.com/orgs/acme/projects/7",
        f"checkouts\t{checkouts}",
        f"repo\tacme/api\tproduction_branch=live\tcheckout={checkouts / 'api'}",
        "repo\tacme/app\tproduction_branch=none\tcheckout=missing",
        f"ladder\t{LADDER}"], out
    out, _, _ = main(load(write_config("no-ladder.json", ladder=None)), "config")
    assert out.splitlines()[-1] == "ladder\tnone", out


def test_next_without_a_ladder_still_picks_and_names_no_model():
    m = next_module([item(1, effort="L")], bodies={1: "touch `a.py`"}, paths=["a.py"])
    d, code = run_next(m, no_judge=True)
    rung = json.loads(LADDER.read_text())["rungs"]["L"]
    assert d["startable"][0]["model"] == rung["model"] and d["ladder"] == str(LADDER), d

    m = next_module([item(1, effort="L"), item(2, effort="XS")], bodies={1: "a", 2: "b"},
                    config=write_config("next-no-ladder.json", ladder=None))
    d, code = run_next(m, no_judge=True)
    assert code == 0 and only(d, "startable") == ["hoopit/api#2", "hoopit/api#1"], d
    assert all(e["model"] is None and e["reasoning_effort"] is None for e in d["startable"]), d
    assert d["ladder"] is None
    print("  ranks and picks as before, with model and reasoning_effort null")


def test_a_ladder_priced_out_of_order_refuses_the_tick():
    broken = json.loads(LADDER.read_text())
    broken["rungs"]["XS"], broken["rungs"]["XL"] = broken["rungs"]["XL"], broken["rungs"]["XS"]
    ladder = write_raw("upside-down.json", json.dumps(broken))
    m = next_module([item(1)], config=write_config("upside.json", ladder=ladder))
    try:
        run_next(m, no_judge=True)
    except SystemExit as e:
        assert "priced under" in str(e.code), e.code
    else:
        raise AssertionError("dispatched off a ladder that breaks its rule")


def test_dispatches_says_there_is_no_ladder():
    m = load(write_config("dispatch-no-ladder.json", ladder=None))
    report, err, _ = dispatches(m, [pr_row(1, None, 1)], None, no_judge=True)
    assert report["ladder"] is None and "no ladder" in err, (report, err)


@contextlib.contextmanager
def outside_any_repo():
    """A git hook sets GIT_DIR and GIT_INDEX_FILE, which would point the temp repo's git
    at the repository being committed to."""
    saved = {k: os.environ.pop(k) for k in list(os.environ) if k.startswith("GIT_")}
    try:
        yield
    finally:
        os.environ.update(saved)


def git_checkout(where):
    """A repo at `where` whose `origin/live` holds its first commit and not its second.
    Returns (promoted sha, unpromoted sha)."""
    def git(*args):
        return subprocess.run(["git", "-C", str(where), "-c", "user.name=t",
                               "-c", "user.email=t@t", *args],
                              capture_output=True, text=True, check=True).stdout.strip()
    where.mkdir(parents=True, exist_ok=True)
    git("init", "-q")
    git("commit", "-q", "--allow-empty", "-m", "one")
    first = git("rev-parse", "HEAD")
    git("update-ref", "refs/remotes/origin/live", first)
    git("commit", "-q", "--allow-empty", "-m", "two")
    return first, git("rev-parse", "HEAD")


def test_the_deploy_gate_reads_the_production_branch_from_the_config():
    checkouts = TMP / "gate-checkouts"
    with outside_any_repo():
        promoted, pending = git_checkout(checkouts / "api")
        git_checkout(checkouts / "app")
        path = write_config("gate.json", checkouts=str(checkouts), repos=[
            {"repo": "acme/api", "production_branch": "live"},
            {"repo": "acme/app", "production_branch": None}])
        m = load(path)
        assert m.promotion_state("acme/api", promoted) == ""
        assert m.promotion_state("acme/api", pending) == \
            f"merged as {pending[:10]}, not promoted to live yet"
        # A null branch holds, even with a branch of the conventional name sitting there.
        assert "acme/app has no production branch" in m.promotion_state("acme/app", promoted)
        # A repo the config leaves out holds too, and says which repo and which file.
        why = m.promotion_state("acme/web", promoted)
        assert "acme/web is not a configured repo" in why and path in why, why
    print("  branch from the config; null and unconfigured both hold")


def test_check_and_next_name_an_unconfigured_repo():
    m = load(write_config("unconfigured.json"))
    m.rest_one = lambda path: {"merged": True, "merge_commit_sha": "abc1234"}
    line = check(m, "Gate: deployed other/repo#5\n")
    assert line.startswith("SKIP") and "other/repo is not a configured repo" in line, line

    m = next_module([item(1)], bodies={1: "Gate: deployed other/repo#5"}, real_gate=True)
    m.rest_one = lambda path: {"merged": True, "merge_commit_sha": "abc1234"}
    d, code = run_next(m, no_judge=True)
    assert code == 1 and only(d, "awaiting_deploy") == ["hoopit/api#1"], d
    assert "other/repo is not a configured repo" in d["awaiting_deploy"][0]["gate"], d


def test_the_typesafe_key_comes_from_the_environment_only():
    m = load()
    home = TMP / "home"
    (home / ".claude").mkdir(parents=True, exist_ok=True)
    (home / ".claude" / "settings.json").write_text(
        json.dumps({"env": {"TYPESAFE_API_KEY": "from-a-file"}}))
    saved = {k: os.environ.pop(k, None) for k in ("TYPESAFE_API_KEY", "HOME")}
    os.environ["HOME"] = str(home)
    try:
        assert m.typesafe_key() == "" and "TYPESAFE_API_KEY" in m.judgement_unavailable()
        os.environ["TYPESAFE_API_KEY"] = "from-env"
        assert m.typesafe_key() == "from-env" and m.judgement_unavailable() is None
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v


# --- the Agent field -----------------------------------------------------------------------

STATE_DIRS = iter(range(1000))


def agent_module():
    """A module with a state directory of its own, no process spawned and no pid to judge:
    `spawned` counts the syncs a hook would have started."""
    os.environ["XDG_STATE_HOME"] = str(TMP / f"state-{next(STATE_DIRS)}")
    m = load()
    m.spawned = []
    m.spawn_sync = lambda: m.spawned.append(1)
    m.claude_pid = lambda: None
    return m


def hook(m, sid, name, **kw):
    """One hook event through `agent-hook`, which must print nothing and exit 0. Returns the
    session's (state, note), or None for a session nothing bound."""
    sys.stdin = io.StringIO(json.dumps({"session_id": sid, "hook_event_name": name, **kw}))
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = m.cmd_agent_hook(None)
    assert out.getvalue() == "" and code == 0, (out.getvalue(), code)
    rec = m.session_load(sid)
    return rec and (rec["state"], rec["note"])


def bound(m, sid="s1", repo="hoopit/api", n=5, item="I5"):
    os.environ["CLAUDE_CODE_SESSION_ID"] = sid
    try:
        return m.bind_line(repo, n, "PVT_7", item)
    finally:
        del os.environ["CLAUDE_CODE_SESSION_ID"]


ASK = {"tool_name": "AskUserQuestion", "tool_input": {"questions": [
    {"question": "PR #12 — 2 questions from round 3", "header": "Monitoring",
     "options": [{"label": "Answer in chat (recommended)"}, {"label": "Take all your recommendations"}]}]}}
WATCH = [{"id": "b1", "type": "shell", "status": "running", "description": "monitor-pr #12",
          "command": "bash watch-pr.sh hoopit/api 12 60"}]


def answered(label):
    return {**ASK, "tool_response": {"answers": {"PR #12 — 2 questions from round 3": label}}}


def test_agent_states_styles_and_ranks_agree():
    m = load()
    assert m.AGENT_STATES == AGENT_STATES == list(m.AGENT_STYLE) and set(m.AGENT_RANK) == set(AGENT_STATES)


def test_an_unbound_session_costs_a_lookup_until_there_is_a_session_to_reap():
    m = agent_module()
    state = pathlib.Path(m.agents_dir(create=False))
    for name, kw in (("SessionStart", {"source": "startup"}), ("UserPromptSubmit", {"prompt": "hi"}),
                     ("PreToolUse", ASK), ("Stop", {"background_tasks": []}),
                     ("SessionEnd", {"reason": "other"})):
        assert hook(m, "nobody", name, **kw) is None
    # Nothing ever bound — no config, say — leaves no trace and starts no process.
    assert m.spawned == [] and not state.exists(), (m.spawned, state)
    bound(m, "other")
    m.spawned.clear()
    # Once a record exists, a starting session is the clock that reaps the dead, bound or not.
    hook(m, "nobody", "SessionStart", source="startup")
    assert m.spawned == [1], m.spawned
    print("  no directory and no sync until something is bound; then a start reaps")


def test_a_question_answered_in_chat_stays_yours_until_you_type():
    m = agent_module()
    assert bound(m) == "BOUND\thoopit/api#5\tsession s1"
    assert m.session_load("s1")["state"] == "Working" and m.spawned == [1]
    assert hook(m, "s1", "PreToolUse", **ASK) == \
        ("Needs you", "Monitoring: PR #12 — 2 questions from round 3")
    note = "Monitoring: PR #12 — 2 questions from round 3"
    assert hook(m, "s1", "PostToolUse", **answered("Answer in chat (recommended)")) == ("Needs you", note)
    assert hook(m, "s1", "Stop", background_tasks=WATCH) == ("Needs you", note)
    # The watch wakes the agent; that is no answer.
    assert hook(m, "s1", "UserPromptSubmit",
                prompt="<task-notification>\n<task-id>b1</task-id>") == ("Needs you", note)
    assert hook(m, "s1", "UserPromptSubmit", prompt="go with option 2") == ("Working", "")
    assert hook(m, "s1", "Stop", background_tasks=[]) == ("Idle", "")
    print("  Needs you through the chat answer, the stop and a watch event; typing clears it")


def test_a_question_answered_in_the_dialog_is_working_again():
    m = agent_module()
    bound(m)
    hook(m, "s1", "PreToolUse", **ASK)
    assert hook(m, "s1", "PostToolUse", **answered("Take all your recommendations")) == ("Working", "")
    # A turn that ends with the PR watch armed is still the agent's.
    assert hook(m, "s1", "Stop", background_tasks=WATCH) == ("Working", "")
    assert hook(m, "s1", "UserPromptSubmit", prompt="<task-notification>…") == ("Working", "")
    # Pending is in flight too, and a session cron wakes it as surely as a watch.
    assert hook(m, "s1", "Stop", background_tasks=[{**WATCH[0], "status": "pending"}]) == ("Working", "")
    assert hook(m, "s1", "Stop", background_tasks=[], session_crons=[{"id": "c1"}]) == ("Working", "")
    # The watch expired and nothing re-armed it: the run went quiet without asking.
    assert hook(m, "s1", "Stop", background_tasks=[]) == ("Idle", "")
    assert hook(m, "s1", "StopFailure") == ("Idle", "its last turn failed on an API error")
    print("  answered in the dialog is Working; a watch keeps it Working; a lapsed one is Idle")


def test_a_dialog_that_closed_itself_answered_nothing():
    m = agent_module()
    bound(m)
    hook(m, "s1", "PreToolUse", **ASK)
    assert hook(m, "s1", "PostToolUse", **ASK, tool_response={"answers": {}, "afkTimeoutMs": 60000}) \
        == ("Needs you", "Monitoring: PR #12 — 2 questions from round 3")
    assert hook(m, "s1", "Stop", background_tasks=[])[0] == "Needs you"


def test_a_subagent_never_moves_the_session():
    m = agent_module()
    bound(m)
    assert hook(m, "s1", "PreToolUse", agent_id="a1", agent_type="worker", **ASK) == ("Working", "")
    assert hook(m, "s1", "SubagentStop", agent_id="a1") == ("Working", "")


def test_an_ended_session_is_gone_and_a_resumed_one_idle():
    m = agent_module()
    bound(m)
    hook(m, "s1", "PreToolUse", **ASK)
    assert hook(m, "s1", "SessionEnd", reason="other") == ("Gone", "")
    assert m.session_load("s1")["ended"] is not None
    assert hook(m, "s1", "SessionStart", source="compact") == ("Gone", "")
    assert hook(m, "s1", "SessionStart", source="resume") == ("Idle", "")
    assert m.session_load("s1")["ended"] is None


def test_the_hook_swallows_garbage_and_logs_it():
    m = agent_module()
    sys.stdin = io.StringIO("not json")
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert m.cmd_agent_hook(None) == 0
    assert out.getvalue() == ""
    assert "JSONDecodeError" in pathlib.Path(m.agents_dir("hook.log")).read_text()


IDS = {"agent": "F_agent", "options": {s: f"O_{s}" for s in AGENT_STATES}, "note": "F_note"}


def sync_module(issue_state="open"):
    """agent_module with the board stubbed: `writes` collects each mutation sent, and every
    issue reads as `issue_state`."""
    m = agent_module()
    m.writes, m.reads = [], []
    m.agent_field_ids = lambda project_id, now: IDS
    m.gql_write = lambda q: m.writes.append(q)
    def gh_soft(*args):
        m.reads.append(args[1])
        return issue_state
    m.gh_soft = gh_soft
    return m


def sent(m):
    """Per mutation: the field ids it sets (with the value) or clears."""
    out = [sorted([(f, json.loads(v)) for f, v in
                   re.findall(r'fieldId:"(\w+)", value:\{\w+:("(?:[^"\\]|\\.)*")\}', q)]
                  + [(f, None) for f in re.findall(r'clearProjectV2ItemFieldValue\(input:\{[^}]*fieldId:"(\w+)"', q)])
           for q in m.writes]
    m.writes.clear()
    return out


def test_the_sync_writes_only_what_changed():
    m = sync_module()
    bound(m)
    m.agents_sync()
    assert sent(m) == [[("F_agent", "O_Working"), ("F_note", None)]], m.writes
    m.agents_sync()
    assert sent(m) == [] and m.reads == ["repos/hoopit/api/issues/5"], m.reads
    hook(m, "s1", "PreToolUse", **ASK)
    m.agents_sync()
    assert sent(m) == [[("F_agent", "O_Needs you"),
                        ("F_note", "Monitoring: PR #12 — 2 questions from round 3")]]
    hook(m, "s1", "PostToolUse", **answered("Take all your recommendations"))
    m.agents_sync()
    assert sent(m) == [[("F_agent", "O_Working"), ("F_note", None)]]
    print("  one mutation per change, the issue read once an hour, nothing sent twice")


def test_a_dead_session_is_reaped_and_its_closed_issue_cleared():
    m = sync_module(issue_state="closed")
    bound(m)
    rec = m.session_load("s1")
    dead = subprocess.Popen(["true"])
    dead.wait()
    rec["pid"] = dead.pid
    m.session_save(rec)
    m.agents_sync()
    # Closed: nothing left to show, so both values go and the session lets go of the item.
    assert sent(m) == [[("F_agent", None), ("F_note", None)]], m.writes
    assert m.sessions_load() == [] and m.pushed_load() == {}
    print("  a dead pid reaps to Gone, a closed issue clears instead, and the record goes")


def test_a_dead_session_on_open_work_shows_gone():
    m = sync_module()
    bound(m)
    m.agents_sync()
    sent(m)
    hook(m, "s1", "SessionEnd", reason="other")
    m.agents_sync()
    # An ending reads the issue at once rather than waiting out the hour.
    assert sent(m) == [[("F_agent", "O_Gone")]] and len(m.reads) == 2, (m.writes, m.reads)
    assert [s["state"] for s in m.sessions_load()] == ["Gone"]


def test_the_most_urgent_session_on_an_item_wins():
    m = sync_module()
    bound(m, "old")
    bound(m, "new")
    hook(m, "old", "SessionEnd", reason="other")
    m.agents_sync()
    assert sent(m) == [[("F_agent", "O_Working"), ("F_note", None)]], m.writes
    hook(m, "new", "PreToolUse", **ASK)
    m.agents_sync()
    assert sent(m)[0][0] == ("F_agent", "O_Needs you")


def test_a_sync_already_running_is_left_a_dirty_flag():
    m = sync_module()
    bound(m)
    with m.agents_lock(".sync.lock"):
        m.agents_sync()
        assert m.writes == [] and os.path.exists(m.agents_dir(".dirty"))


def test_field_ids_are_cached_only_once_the_board_has_them():
    m = agent_module()
    answers = [[], [{"id": "F_agent", "name": "Agent", "options": [{"id": "O_W", "name": "Working"}]},
                    {"id": "F_note", "name": "Agent note"}]]
    asked = []
    def gql(q, **v):
        asked.append(v["id"])
        return {"node": {"fields": {"nodes": answers[min(len(asked) - 1, 1)]}}}
    m.gql = gql
    assert m.agent_field_ids("PVT_7", 100) is None
    ids = {"agent": "F_agent", "options": {"Working": "O_W"}, "note": "F_note"}
    # Provisioned since: the next sync finds the field rather than a cached absence.
    assert m.agent_field_ids("PVT_7", 101) == ids and m.agent_field_ids("PVT_7", 102) == ids
    assert asked == ["PVT_7", "PVT_7"], asked
    # A failed write drops the entry, so stale ids are read again.
    m.gh_soft = lambda *a: "open"
    m.gql_write = lambda q: "Could not resolve to a node"
    bound(m)
    m.agents_sync_once(now=103)
    assert "PVT_7" not in m.fields_cache() and len(asked) == 2, asked
    assert m.agent_field_ids("PVT_7", 104) == ids and len(asked) == 3, asked
    print("  absence never cached; ids cached until a write fails on them")


def start_module(status):
    """A module whose issue #5 sits on the board in `status` (None: off the board)."""
    m = agent_module()
    m.calls = []
    res = {"id": "C5", "projectItems": {"nodes": [] if status is None else [
        {"id": "I5", "project": {"id": "PVT_7"}, "fieldValueByName": {"name": status}}]}}
    m.locate = lambda repo, n: ("PVT_7", {"Status": {}}, res, None if status is None else "I5")
    m.ensure_item = lambda repo, n: ("PVT_7", {"Status": {}}, res, "I5")
    m.set_status = lambda pid, f, item, value: m.calls.append(("status", item, value))
    m.gh = lambda *a, **k: m.calls.append(("comment", a[1]))
    return m


def test_start_leaves_work_in_flight_alone_and_binds_the_session():
    for status, lines, calls in (
            ("In progress", ["IN-FLIGHT\thoopit/api#5\tIn progress"], []),
            ("In review", ["IN-FLIGHT\thoopit/api#5\tIn review"], []),
            ("Ready", ["STARTED\thoopit/api#5"],
             [("status", "I5", "In progress"), ("comment", "repos/hoopit/api/issues/5/comments")]),
            (None, ["STARTED\thoopit/api#5"],
             [("status", "I5", "In progress"), ("comment", "repos/hoopit/api/issues/5/comments")])):
        m = start_module(status)
        os.environ["CLAUDE_CODE_SESSION_ID"] = "s9"
        try:
            out, _, code = main(m, "start", "hoopit/api", "5")
        finally:
            del os.environ["CLAUDE_CODE_SESSION_ID"]
        assert code == 0 and out.splitlines() == [*lines, "BOUND\thoopit/api#5\tsession s9"], (status, out)
        assert m.calls == calls, (status, m.calls)
        assert m.session_load("s9")["items"]["hoopit/api#5"]["item"] == "I5"
    print("  in flight: no Status, no marker; otherwise both; bound every time")


def test_bind_outside_a_session_or_off_the_board_changes_nothing():
    m = start_module(None)
    out, _, code = main(m, "bind", "hoopit/api", "5")
    assert code == 0 and out == "NOT-ON-BOARD\thoopit/api#5\n", out
    m = start_module("Backlog")
    os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
    out, _, code = main(m, "bind", "hoopit/api", "5")
    assert code == 0 and out.startswith("UNBOUND\thoopit/api#5"), out
    assert m.calls == [] and m.sessions_load() == []


def test_bind_pr_binds_every_issue_the_description_closes():
    m = start_module("In review")
    m.gh = lambda *a, **k: "Fixes the thing.\n\ncloses #5\ncloses hoopit/web-admin#7\n"
    os.environ["CLAUDE_CODE_SESSION_ID"] = "s3"
    try:
        out, _, code = main(m, "bind", "hoopit/api", "12", "--pr")
    finally:
        del os.environ["CLAUDE_CODE_SESSION_ID"]
    assert code == 0 and out.splitlines() == ["BOUND\thoopit/api#5\tsession s3",
                                              "BOUND\thoopit/web-admin#7\tsession s3"], out
    assert sorted(m.session_load("s3")["items"]) == ["hoopit/api#5", "hoopit/web-admin#7"]


def test_the_agent_commands_need_no_config():
    m = refusing(str(TMP / "nowhere" / "config.json"))
    os.environ["XDG_STATE_HOME"] = str(TMP / f"state-{next(STATE_DIRS)}")
    out, err, code = main(m, "agents")
    assert code == 0 and out == "" and err == "", (out, err, code)
    sys.stdin = io.StringIO(json.dumps({"session_id": "x", "hook_event_name": "Stop"}))
    out, err, code = main(m, "agent-hook")
    assert code == 0 and out == "" and err == "", (out, err, code)


def test_provision_adds_the_agent_fields():
    lines, _, code, writes = run_provision(board_answer(agent=None, note=False), "--apply")
    assert code == 0 and len(writes) == 2, (code, writes)
    agent = next(w for w in writes if "SINGLE_SELECT" in w)
    assert re.findall(r'name:"([^"]*)", color:(\w+)', agent) == [
        ("Working", "GREEN"), ("Needs you", "RED"), ("Idle", "ORANGE"), ("Gone", "GRAY")], agent
    assert 'name:"Agent"' in agent and any("dataType:TEXT" in w and 'name:"Agent note"' in w
                                           for w in writes), writes
    assert "ADDED\tfield 'Agent' with the options Working, Needs you, Idle, Gone" in lines, lines

    lines, _, code, writes = run_provision(board_answer(agent=["Working", "Custom"]), "--apply")
    assert code == 0 and len(writes) == 1, writes
    assert [(i, n) for i, n, _ in sent_options(writes[0])] == [
        ("agent-Working", "Working"), ("agent-Custom", "Custom"), ("", "Needs you"),
        ("", "Idle"), ("", "Gone")], writes[0]
    assert "ADDED\tfield 'Agent' options Needs you, Idle, Gone" in lines, lines

    lines, _, code, writes = run_provision(board_answer(own_fields=[], note=True,
                                                        agent=AGENT_STATES), "--apply")
    assert code == 0 and writes == [] and "OK\tfield 'Agent'" in lines, lines
    print("  both created on a bare board; missing options appended on their ids; a full one is OK")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        print(f"{t.__name__}:")
        t()
    print(f"\n{len(tests)} passed")
