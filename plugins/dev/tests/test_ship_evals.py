#!/usr/bin/env python3
"""Pins the stand-ins ship's suite puts in place of review-gate and monitor-pr. Run it by
hand after editing `plugins/dev/skills/ship/evals/`, review-gate's Contract and Inputs, or
monitor-pr's flags:

    python3 plugins/dev/tests/test_ship_evals.py

Ship is graded on what it hands these two skills, so each stand-in must keep the real
skill's interface, and the gate's must record the pass and make the fix a real pass would.
"""
import json, os, pathlib, shutil, subprocess, sys, tempfile

DEV = pathlib.Path(__file__).resolve().parent.parent
STANDINS = DEV / "skills" / "ship" / "evals" / "standins"


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def test_install_keeps_the_interface():
    d = pathlib.Path(tempfile.mkdtemp())
    for name in ("review-gate", "monitor-pr"):
        shutil.copytree(DEV / "skills" / name, d / "skills" / name)
    for _ in range(2):
        subprocess.run([sys.executable, STANDINS / "install.py", d], check=True)
    gate = (d / "skills" / "review-gate" / "SKILL.md").read_text()
    real = (DEV / "skills" / "review-gate" / "SKILL.md").read_text()
    assert gate.split("---")[1] == real.split("---")[1], "frontmatter changed"
    for word in ("## Contract", "`SPEC`", "`CHALLENGE`", "`REVIEWED_AT`", "`PRIOR_ROUNDS`", "review-gate-pass"):
        assert word in gate, word
    assert gate.count("<!-- ship eval stand-in -->") == 1
    assert os.listdir(d / "skills" / "review-gate") == ["SKILL.md"]
    watch = (d / "skills" / "monitor-pr" / "SKILL.md").read_text()
    for word in ("--subagent", "--unattended", "monitor-pr-arm"):
        assert word in watch, word
    print("ok test_install_keeps_the_interface")


def test_gate_pass_records_and_fixes():
    d = pathlib.Path(tempfile.mkdtemp())
    repo, case = d / "repo", d / "case"
    repo.mkdir()
    case.mkdir()
    git(repo, "init", "-q", "-b", "master")
    git(repo, "config", "user.email", "t@t")
    git(repo, "config", "user.name", "t")
    (repo / "a.py").write_text("x = 1\n")
    git(repo, "add", "a.py")
    git(repo, "commit", "-qm", "base")
    git(repo, "update-ref", "refs/remotes/origin/master", "HEAD")
    head = git(repo, "rev-parse", "HEAD")
    (case / "gate.json").write_text(json.dumps([
        {"fix": "code", "fix_file": "a.py", "fix_replace": [["x = 1", "x = 2"]], "fix_message": "fix"},
        {"verdict": "BLOCK", "reason": "nope"}]))
    calls = d / "calls.jsonl"
    calls.touch()
    env = {**os.environ, "SHIP_EVAL_CALLS": str(calls), "SHIP_EVAL_CASE_DIR": str(case)}
    gate = [sys.executable, STANDINS / "review-gate-pass"]
    out = subprocess.run(gate + ["--scope", "full", "--spec", "the issue"], cwd=repo, env=env,
                         check=True, capture_output=True, text=True).stdout
    assert out.startswith("PASS") and "Fix commits: code" in out, out
    out = subprocess.run(gate + ["--scope", "light"], cwd=repo, env=env,
                         check=True, capture_output=True, text=True).stdout
    assert out.startswith("BLOCK: nope"), out
    one, two = [json.loads(l) for l in calls.read_text().splitlines()]
    assert (one["pass"], one["head"], one["fix"], one["inputs"]["spec"]) == (1, head, "code", "the issue")
    assert one["after"] != head and (repo / "a.py").read_text() == "x = 2\n"
    # light without REVIEWED_AT runs full, as the real gate does, and records what was asked
    assert (two["pass"], two["inputs"]["scope"], two["verdict"]) == (2, "light", "BLOCK")
    print("ok test_gate_pass_records_and_fixes")


def grade(light_from):
    """check.py over a run whose round 1 made a code fix and whose round 2 ran light from
    `light_from` ("head" for round 1's head, "fix" for the fix commit), then pushed."""
    d = pathlib.Path(tempfile.mkdtemp())
    fixture, case = d / "api", d / "case"
    fixture.mkdir()
    case.mkdir()
    git(fixture, "init", "-q", "-b", "master")
    git(fixture, "config", "user.email", "t@t")
    git(fixture, "config", "user.name", "t")
    (fixture / "a.py").write_text("x = 1\n")
    git(fixture, "add", "a.py")
    git(fixture, "commit", "-qm", "base")
    git(d, "clone", "-q", "--bare", str(fixture), str(d / "origin.git"))
    git(fixture, "remote", "add", "origin", str(d / "origin.git"))
    git(fixture, "fetch", "-q", "origin")
    (d / "origin-heads").write_text(git(d / "origin.git", "for-each-ref", "--format=%(refname) %(objectname)") + "\n")
    git(fixture, "switch", "-qc", "fix")
    (fixture / "a.py").write_text("x = 2\n")
    git(fixture, "commit", "-qam", "the change")
    (case / "gate.json").write_text(json.dumps([
        {"fix": "code", "fix_file": "a.py", "fix_replace": [["x = 2", "x = 3"]], "fix_message": "gate fix"}, {}]))
    calls, log = d / "calls.jsonl", d / "log.jsonl"
    calls.touch()
    log.touch()
    env = {**os.environ, "SHIP_EVAL_CALLS": str(calls), "SHIP_EVAL_CASE_DIR": str(case)}
    gate = [sys.executable, STANDINS / "review-gate-pass"]
    subprocess.run(gate + ["--scope", "full"], cwd=fixture, env=env, check=True, capture_output=True)
    since = json.loads(calls.read_text().splitlines()[0])["head" if light_from == "head" else "after"]
    subprocess.run(gate + ["--scope", "light", "--reviewed-at", since, "--prior-rounds", "Medium"],
                   cwd=fixture, env=env, check=True, capture_output=True)
    git(fixture, "push", "-q", "origin", "fix")
    env = {**os.environ, "EVAL_SUITE_DIR": str(DEV / "skills" / "ship" / "evals"), "EVAL_RUN_DIR": str(d),
           "EVAL_FIXTURE": str(fixture), "EVAL_CALLS": str(calls), "EVAL_LOG": str(log),
           "EVAL_EXPECT_ROUNDS": "2"}
    out = subprocess.run([sys.executable, DEV / "skills" / "ship" / "evals" / "check.py"], cwd=fixture,
                         env=env, capture_output=True, text=True)
    assert not out.stderr, out.stderr
    return {l.split()[1]: l.split()[0] for l in out.stdout.splitlines()}


def test_light_round_from_the_fix_misses_it():
    good, bad = grade("head"), grade("fix")
    assert good["push_reviewed"] == good["gate_rounds"] == "PASS", good
    assert bad["push_reviewed"] == bad["gate_rounds"] == "FAIL", bad
    print("ok test_light_round_from_the_fix_misses_it")


if __name__ == "__main__":
    test_install_keeps_the_interface()
    test_gate_pass_records_and_fixes()
    test_light_round_from_the_fix_misses_it()
    print("\nall passed")
