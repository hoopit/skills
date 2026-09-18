#!/usr/bin/env python3
"""Pins `hoopit-board batch`'s write loop, `next`'s collision judgement, `decisions`'
naming judgement and `scan`'s duplicate judgement. Run it by hand after editing any of them:

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
import tempfile

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
        code = m.cmd_next(argparse.Namespace(target=target, exclude=[], scope=None,
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
    a = argparse.Namespace(**{"n": 5, "lines": 8, "unnamed": False, "out_of_reach": False,
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


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        print(f"{t.__name__}:")
        t()
    print(f"\n{len(tests)} passed")
