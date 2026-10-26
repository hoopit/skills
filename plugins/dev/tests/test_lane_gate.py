#!/usr/bin/env python3
"""Pins what `lane-gate.sh` counts toward the merge lane's size limits. Run it by hand after
editing the gate:

    python3 plugins/dev/tests/test_lane_gate.py

No network: a `gh` shim on PATH answers the three reads the gate makes — the PR, its files a
page at a time, and its closing issues — from a PR described in the test, and runs `--jq`
through `jq` as `gh` does. A `--paginate` read fails: the gate pages by hand.

What it guards is which lines a limit counts — the gate's header defines a test file — and
that a gate which cannot count passes nothing.
"""
import json, os, pathlib, shutil, subprocess, sys, tempfile

GATE = pathlib.Path(__file__).resolve().parent.parent / "skills" / "merge-briefing" / "scripts" / "lane-gate.sh"
REPO, PR = "hoopit/analytics", 61

SHIM = r'''#!PYTHON
import json, os, re, subprocess, sys
pr = json.load(open(os.environ["LANE_TEST_PR"]))
args = sys.argv[1:]
assert args[0] == "api", args
jq, endpoint, i = None, None, 1
while i < len(args):
    a = args[i]
    if a in ("--jq", "-q"):
        jq = args[i + 1]; i += 2
    elif a in ("-F", "-f", "-H", "-X"):
        i += 2
    elif a == "--paginate":
        sys.exit("gh shim: page by hand with per_page and page")
    elif a.startswith("-"):
        i += 1
    else:
        endpoint = endpoint or a; i += 1
repo = os.environ["LANE_TEST_REPO"]
if endpoint == "graphql":
    nodes = [{"repository": {"nameWithOwner": repo}}] * pr["closing"]
    out = {"data": {"repository": {"pullRequest": {"closingIssuesReferences": {"nodes": nodes}}}}}
elif m := re.fullmatch(rf"repos/{re.escape(repo)}/pulls/{pr['number']}/files\?per_page=(\d+)&page=(\d+)",
                       endpoint or ""):
    size, page = int(m[1]), int(m[2])
    out = pr["files"][:pr["cap"]][(page - 1) * size:page * size]
elif endpoint == f"repos/{repo}/pulls/{pr['number']}":
    reads = os.environ["LANE_TEST_PR"] + ".reads"
    n = int(open(reads).read()) if os.path.exists(reads) else 0
    open(reads, "w").write(str(n + 1))
    if n and pr["moves"] == "fails":
        sys.stderr.write("gh: Bad Gateway (HTTP 502)\n"); sys.exit(1)
    out = {"changed_files": len(pr["files"]), "user": {"type": pr["author_type"]},
           "head": {"sha": "b" if n and pr["moves"] else "a"}, "base": {"sha": "c"},
           "requested_reviewers": [], "requested_teams": []}
else:
    sys.stderr.write(f"gh: Not Found (HTTP 404) {endpoint}\n"); sys.exit(1)
if jq is None:
    print(json.dumps(out)); sys.exit(0)
sys.exit(subprocess.run(["jq", "-r", jq], input=json.dumps(out), text=True).returncode)
'''


def file(name, lines, previous=None):
    f = {"filename": name, "changes": lines, "status": "modified"}
    if previous:
        f.update(previous_filename=previous, status="renamed")
    return f


def gate(files, guarded="", closing=1, author_type="User", cap=None, moves=False, **env):
    """The gate's one line for a PR with these files, under these LANE_* overrides. GitHub lists
    only the first `cap` files, when one is given; `moves` pushes a new head after the first read
    of the PR, or, as "fails", makes every later read of it fail."""
    d = pathlib.Path(tempfile.mkdtemp(prefix="lane-gate-"))
    try:
        (d / "pr.json").write_text(json.dumps({"number": PR, "files": files, "closing": closing,
                                               "author_type": author_type, "cap": cap, "moves": moves}))
        gh = d / "gh"
        gh.write_text(SHIM.replace("PYTHON", sys.executable, 1))
        gh.chmod(0o755)
        e = {k: v for k, v in os.environ.items() if not k.startswith("LANE_")}
        e.update(PATH=f"{d}:{os.environ['PATH']}", LANE_TEST_PR=str(d / "pr.json"), LANE_TEST_REPO=REPO, **env)
        p = subprocess.run(["bash", str(GATE), REPO, str(PR), guarded], env=e, capture_output=True, text=True)
        assert p.returncode == 0, p.stderr
        return p.stdout.strip()
    finally:
        shutil.rmtree(d, True)


def fixtures(lines):
    """`lines` lines of test fixtures, spread over every shape the gate leaves out of its counts."""
    names = ["tests/fixtures/clubs.json", "pipelines/test/data.csv", "models/club_test.sql",
             "pipelines/test_clubs.py", "cdk/__snapshots__/stack.ts.snap", "cdk/stack.snap"]
    each, rest = divmod(lines, len(names))
    return [file(name, each + (i < rest)) for i, name in enumerate(names)]


def test_test_fixtures_leave_the_size_count():
    out = gate([file("models/clubs.sql", 350)] + fixtures(500))
    assert out == "gate=pass", out


def test_over_the_default_limits_takes_a_human():
    out = gate([file("models/clubs.sql", 500)])
    assert out == "gate=human reason=500 changed lines outside tests, over 400", out


def test_a_repos_limits_replace_the_defaults():
    out = gate([file("models/clubs.sql", 500)], LANE_MAX_LINES="1000", LANE_MAX_FILES="40")
    assert out == "gate=pass", out


def test_a_limit_that_is_not_a_whole_number_passes_nothing():
    for bad in ("400 lines", "1e3", "abc", "040"):
        out = gate([file("models/clubs.sql", 1)], LANE_MAX_LINES=bad)
        assert out == f"gate=human reason=lane limit `{bad}` is not a whole number", out
    out = gate([file("models/clubs.sql", 1)], LANE_MAX_FILES="40,")
    assert out == "gate=human reason=lane limit `40,` is not a whole number", out


def test_only_files_outside_tests_count_toward_the_file_limit():
    many = [file(f"models/m{i}.sql", 1) for i in range(16)]
    out = gate(many + [file(f"tests/t{i}.py", 1) for i in range(30)])
    assert out == "gate=human reason=16 changed files outside tests, over 15", out
    out = gate(many[:15] + [file(f"tests/t{i}.py", 1) for i in range(30)])
    assert out == "gate=pass", out


def test_a_test_file_is_still_read_against_the_guarded_paths():
    out = gate([file("models/clubs.sql", 10), file("sql/tests/grant_test.sql", 10)], guarded="^sql/")
    assert out == "gate=human reason=`sql/tests/grant_test.sql` is a guarded path (`^sql/`)", out


def test_a_name_that_only_contains_test_still_counts():
    names = ["pipelines/latest.py", "models/contest_entries.sql", "testing/clubs.py", "models/attest.sql"]
    out = gate([file(n, 101) for n in names])
    assert out == "gate=human reason=404 changed lines outside tests, over 400", out


def test_github_stays_guarded_with_nothing_configured():
    out = gate([file(".github/workflows/ci.yml", 3)])
    assert out == "gate=human reason=`.github/workflows/ci.yml` is a guarded path (`^\\.github/`)", out


def test_a_rename_out_of_a_guarded_path_is_read_under_both_names():
    out = gate([file("models/tables.py", 0, previous="sql/tables.py")], guarded="^sql/")
    assert out == "gate=human reason=`sql/tables.py` is a guarded path (`^sql/`)", out


def test_a_rename_into_tests_counts_unless_it_was_a_test_already():
    moved = [file(f"tests/m{i}.py", 1, previous=f"models/m{i}.py") for i in range(16)]
    out = gate(moved)
    assert out == "gate=human reason=16 changed files outside tests, over 15", out
    out = gate([file(f"tests/m{i}.py", 1, previous=f"test/m{i}.py") for i in range(16)])
    assert out == "gate=pass", out


def test_files_past_the_first_page_are_counted():
    out = gate([file(f"tests/t{i}.py", 1) for i in range(150)] + [file("models/clubs.sql", 401)])
    assert out == "gate=human reason=401 changed lines outside tests, over 400", out


def test_a_listing_short_of_the_file_count_passes_nothing():
    files = [file(f"tests/t{i}.py", 1) for i in range(120)] + [file("sql/grant.sql", 1000)]
    out = gate(files, guarded="^sql/", cap=120)
    assert out == "gate=human reason=could read only 120 of the 121 changed files", out


def test_a_pr_that_moved_while_its_files_were_read_passes_nothing():
    out = gate([file("tests/t.py", 1)], moves=True)
    assert out == "gate=human reason=the PR moved while its files were read", out
    out = gate([file("tests/t.py", 1)], moves="fails")
    assert out == "gate=human reason=could not re-read the PR", out


def test_every_reason_is_named():
    out = gate([file("models/clubs.sql", 500), file("sql/grant.sql", 1)], guarded="^sql/", closing=0,
               author_type="Bot")
    assert out == ("gate=human reason=501 changed lines outside tests, over 400; a bot opened it; "
                   "`sql/grant.sql` is a guarded path (`^sql/`); it closes no issue in this repository"), out


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
