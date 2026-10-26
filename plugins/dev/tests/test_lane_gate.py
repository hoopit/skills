#!/usr/bin/env python3
"""Pins which PRs `lane-gate.sh` sends to a human. Run it by hand after
editing the gate:

    python3 plugins/dev/tests/test_lane_gate.py

No network: a `gh` shim on PATH answers the three reads the gate makes — the PR, its files a
page at a time, and its closing issues — from a PR described in the test, and runs `--jq`
through `jq` as `gh` does. A `--paginate` read fails: the gate pages by hand.

What it guards is that every changed path, past the first page and under both names of a
rename, is read against the guarded paths, and that a gate which cannot read them all passes
nothing.
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


def gate(files, guarded="", closing=1, author_type="User", cap=None, moves=False):
    """The gate's one line for a PR with these files. GitHub lists
    only the first `cap` files, when one is given; `moves` pushes a new head after the first read
    of the PR, or, as "fails", makes every later read of it fail."""
    d = pathlib.Path(tempfile.mkdtemp(prefix="lane-gate-"))
    try:
        (d / "pr.json").write_text(json.dumps({"number": PR, "files": files, "closing": closing,
                                               "author_type": author_type, "cap": cap, "moves": moves}))
        gh = d / "gh"
        gh.write_text(SHIM.replace("PYTHON", sys.executable, 1))
        gh.chmod(0o755)
        e = dict(os.environ, PATH=f"{d}:{os.environ['PATH']}", LANE_TEST_PR=str(d / "pr.json"), LANE_TEST_REPO=REPO)
        p = subprocess.run(["bash", str(GATE), REPO, str(PR), guarded], env=e, capture_output=True, text=True)
        assert p.returncode == 0, p.stderr
        return p.stdout.strip()
    finally:
        shutil.rmtree(d, True)








def test_a_test_file_is_read_against_the_guarded_paths():
    out = gate([file("models/clubs.sql", 10), file("sql/tests/grant_test.sql", 10)], guarded="^sql/")
    assert out == "gate=human reason=`sql/tests/grant_test.sql` is a guarded path (`^sql/`)", out



def test_github_stays_guarded_with_nothing_configured():
    out = gate([file(".github/workflows/ci.yml", 3)])
    assert out == "gate=human reason=`.github/workflows/ci.yml` is a guarded path (`^\\.github/`)", out


def test_a_rename_out_of_a_guarded_path_is_read_under_both_names():
    out = gate([file("models/tables.py", 0, previous="sql/tables.py")], guarded="^sql/")
    assert out == "gate=human reason=`sql/tables.py` is a guarded path (`^sql/`)", out



def test_files_past_the_first_page_are_read():
    out = gate([file(f"tests/t{i}.py", 1) for i in range(150)] + [file("sql/grant.sql", 1)], guarded="^sql/")
    assert out == "gate=human reason=`sql/grant.sql` is a guarded path (`^sql/`)", out


def test_a_large_pr_passes():
    out = gate([file(f"models/m{i}.sql", 100) for i in range(50)])
    assert out == "gate=pass", out


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
    assert out == ("gate=human reason=a bot opened it; "
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
