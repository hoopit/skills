"""Stands in front of the runner's `gh` shim for one run; `setup.sh` installs it.

- Copies every `--body-file` into `gh-bodies.jsonl` as the call is made, so the checks
  can read a body the agent deletes afterwards.
- Answers a `closingIssuesReferences` query from the body the PR carries at that moment,
  the way GitHub would, so the skill's own check sees a missing closing keyword.
- Answers `gh pr view` with "no pull requests found" until `gh pr create` has run.
- Applies a `gh api` call's `--jq` to the JSON its mock answers, as gh would, so a mock
  holds the whole response whichever field the agent selects.

Everything else goes to the shim, which records the call and answers it from the case's
mocks.
"""
import json, os, shutil, subprocess, sys

import pr_state


def main(run_dir, calls, shim):
    argv = sys.argv[1:]
    for name, value in pr_state._flags(argv):
        if name == "body-file" and value != "-":
            try:
                content = open(value, errors="replace").read()
            except OSError:
                continue
            with open(os.path.join(run_dir, "gh-bodies.jsonl"), "a") as fh:
                fh.write(json.dumps({"argv": argv, "content": content}) + "\n")
    closing = "closingIssuesReferences" in " ".join(argv) and argv[:2] in (["pr", "view"], ["api", "graphql"])
    # Before the PR exists, the branch has none: a static mock would show the agent a PR
    # it never opened.
    unopened = argv[:2] == ["pr", "view"] and not pr_state.load(run_dir, calls)["creates"]
    if closing or unopened:
        with open(calls, "a") as fh:
            fh.write(json.dumps({"tool": "gh", "argv": argv, "stdin": None, "cwd": os.getcwd()}) + "\n")
        if unopened:
            print("no pull requests found for branch", file=sys.stderr)
            sys.exit(1)
        sys.exit(answer_closing(argv, run_dir, calls))
    jq = _jq(argv)
    if argv[:1] == ["api"] and jq and shutil.which("jq"):
        p = subprocess.run([shim] + argv, capture_output=True, text=True)
        sys.stderr.write(p.stderr)
        if p.returncode:
            sys.stdout.write(p.stdout)
            sys.exit(p.returncode)
        sys.exit(_emit(p.stdout, jq))
    os.execv(shim, [shim] + argv)


def _jq(argv):
    return next((v for n, v in zip(argv, argv[1:]) if n in ("--jq", "-q")), None)


def _emit(out, jq):
    """Writes `out` through `jq`, or as it is when it is not JSON."""
    try:
        json.loads(out)
    except ValueError:
        sys.stdout.write(out)
        return 0
    p = subprocess.run(["jq", "-r", jq], input=out, capture_output=True, text=True)
    sys.stdout.write(p.stdout)
    sys.stderr.write(p.stderr)
    return p.returncode


def answer_closing(argv, run_dir, calls):
    state = pr_state.load(run_dir, calls)
    if not state["creates"]:
        print("no pull requests found for branch", file=sys.stderr)
        return 1
    refs = [{"number": n, "url": f"https://github.com/hoopit/api/issues/{n}",
             "repository": {"name": "api", "owner": {"login": "hoopit"}}}
            for n in pr_state.closing_numbers(state["body"])]
    if argv[0] == "api":
        data = {"data": {"repository": {"pullRequest": {
            "closingIssuesReferences": {"nodes": refs, "totalCount": len(refs)}}}}}
    else:
        data = {"closingIssuesReferences": refs}
    jq = _jq(argv)
    out = json.dumps(data)
    if jq and shutil.which("jq"):
        return _emit(out, jq)
    print(out)
    return 0
