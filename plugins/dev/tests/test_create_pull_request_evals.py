#!/usr/bin/env python3
"""Pins how create-pull-request's suite reads a run's PR. Run it by hand after editing
`plugins/dev/skills/create-pull-request/evals/`:

    python3 plugins/dev/tests/test_create_pull_request_evals.py

The checks grade the title and body GitHub would show, so a body passed by file, one
replaced by `gh pr edit`, and a paragraph wrapped mid-sentence must all read right.
"""
import json, os, pathlib, subprocess, sys, tempfile

EVALS = pathlib.Path(__file__).resolve().parent.parent / "skills" / "create-pull-request" / "evals"
sys.path.insert(0, str(EVALS))
import pr_state

SHIM = '''#!%s
import json, os, sys
with open(%r, "a") as fh:
    fh.write(json.dumps({"tool": "gh", "argv": sys.argv[1:], "stdin": None, "cwd": os.getcwd()}) + "\\n")
'''


def run_dir():
    """A run dir whose `gh` is the suite's wrapper in front of a shim that only records."""
    d = pathlib.Path(tempfile.mkdtemp())
    (d / "shims").mkdir()
    calls = d / "calls.jsonl"
    calls.touch()
    shim = d / "shims" / "gh.shim"
    shim.write_text(SHIM % (sys.executable, str(calls)))
    shim.chmod(0o755)
    wrap = d / "shims" / "gh"
    wrap.write_text(f"#!{sys.executable}\nimport sys\nsys.path.insert(0, {str(EVALS)!r})\n"
                    f"import gh_wrap\ngh_wrap.main({str(d)!r}, {str(calls)!r}, {str(shim)!r})\n")
    wrap.chmod(0o755)
    return d


def gh(d, *argv):
    return subprocess.run([str(d / "shims" / "gh"), *argv], capture_output=True, text=True, cwd=d)


def test_body_file_survives_its_deletion():
    d = run_dir()
    (d / "b.md").write_text("Part of #18303.\n")
    gh(d, "pr", "create", "--draft", "--title", "GH-18303: Retire it", "--body-file", "b.md")
    (d / "b.md").unlink()
    s = pr_state.load(str(d), str(d / "calls.jsonl"))
    assert s["title"] == "GH-18303: Retire it" and s["body"] == "Part of #18303.\n", s
    assert s["flags"].get("base") is None and "draft" in s["flags"]


def test_closing_query_answers_from_the_current_body():
    d = run_dir()
    q = ["pr", "view", "--json", "closingIssuesReferences", "--jq", ".closingIssuesReferences[].number"]
    assert gh(d, *q).returncode == 1, "a PR nobody opened has no closing references"
    gh(d, "pr", "create", "--title", "t", "--body", "Refs #18303")
    assert gh(d, *q).stdout.strip() == ""
    (d / "c.md").write_text("Closes #18303\n")
    gh(d, "pr", "edit", "--body-file", "c.md")
    assert gh(d, *q).stdout.strip() == "18303"
    s = pr_state.load(str(d), str(d / "calls.jsonl"))
    assert s["body"] == "Closes #18303\n" and s["verified"] and s["edits"] == 1


def test_closing_numbers():
    assert pr_state.closing_numbers("closes #1\nFixes: hoopit/api#2\nresolved #3") == [1, 2, 3]
    assert pr_state.closing_numbers("refs #1, part of #2, step 1 of #3") == []


def test_wrapped_lines():
    wrapped = "This paragraph was wrapped at a hundred columns by an agent who\nthought it was a commit body.\n"
    assert pr_state.wrapped_lines(wrapped)
    one_line = "## Summary\nA paragraph on one line, however long it runs, is what GitHub renders well.\n\n- a\n- b\n"
    assert not pr_state.wrapped_lines(one_line)
    fenced = "```\nsome code that runs past fifty characters on a line, and on\nand on\n```\n"
    assert not pr_state.wrapped_lines(fenced)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
