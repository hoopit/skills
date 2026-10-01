#!/usr/bin/env python3
"""Pins `field-report`'s counting. Run it by hand after editing the report:

    python3 plugins/dev/tests/test_field_report.py

No network and no pytest: it writes a few synthetic session transcripts, in the shape
Claude Code writes them, under a temporary root and reads the report's JSON back.

What it guards is what a number in the report means. A skill counts only when a session
reaches it by one of the three routes, never because the skill listing names it; a
session that edits a skill, a review-gate probe and an eval run never count; a span's
failures, redos, tokens and ending are its own; and create-worktree's signals land on
the repo the worktree was cut from.
"""
import json, os, pathlib, subprocess, sys, tempfile

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "skills" / "skill-eval" / "scripts" / "field-report"


class Transcript:
    """Writes one transcript's entries, one JSON object per line, as Claude Code does."""

    def __init__(self, path, cwd, day="2026-09-10"):
        self.path, self.cwd, self.day, self.n, self.lines = path, cwd, day, 0, []

    def _ts(self):
        self.n += 1
        return f"{self.day}T10:{self.n // 60:02d}:{self.n % 60:02d}.000Z"

    def _entry(self, type, content, **extra):
        self.lines.append({"type": type, "timestamp": self._ts(), "cwd": self.cwd, "sessionId": "s",
                           "message": {"role": type, "content": content}, **extra})

    def prompt(self, text, origin="human"):
        self._entry("user", text, origin={"kind": origin})

    def meta(self, text):
        self._entry("user", [{"type": "text", "text": text}], isMeta=True)

    def listing(self):
        """The skill listing: every skill's name and path, in every transcript."""
        self.lines.append({"type": "attachment", "timestamp": self._ts(), "attachment": {
            "type": "skill_listing", "content": "- monitor-pr: read skills/monitor-pr/SKILL.md"}})
        self.meta("<system-reminder>skills/monitor-pr/SKILL.md, skills/ship/SKILL.md</system-reminder>")

    def call(self, name, input, result="", error=False, tokens=100, id=None):
        id = id or f"toolu_{self.n}_{name}"
        self._entry("assistant", [{"type": "tool_use", "id": id, "name": name, "input": input}],
                    requestId=f"req_{self.n}")
        self.lines[-1]["message"].update(id=f"msg_{self.n}", usage={
            "input_tokens": tokens, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
            "output_tokens": 0})
        self._entry("user", [{"type": "tool_result", "tool_use_id": id, "content": result, "is_error": error}])
        return id

    def bash(self, command, result="", error=False, **kw):
        return self.call("Bash", {"command": command}, result, error, **kw)

    def skill(self, name):
        self.call("Skill", {"skill": name})
        self.meta(f"Base directory for this skill: /plugins/hoopit-dev/skills/{name.split(':')[-1]}\n\n# {name}")

    def slash(self, name):
        self.prompt(f"<command-message>{name}</command-message>\n<command-name>/{name}</command-name>")
        self.meta(f"Base directory for this skill: /plugins/hoopit-dev/skills/{name.split(':')[-1]}\n\n# {name}")

    def write(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("".join(json.dumps(e) + "\n" for e in self.lines))


def repo(root, name, flutter=False):
    d = root / name
    (d / ".git").mkdir(parents=True)
    if flutter:
        (d / "pubspec.yaml").write_text("name: app\n")
    return d


def build(tmp):
    root = tmp / "projects"
    api, app = repo(tmp, "api"), repo(tmp, "flutter-app", flutter=True)

    # A ship session in api: create-worktree reached by reading its SKILL.md.
    a = Transcript(root / "-api" / "aaaa.jsonl", str(api))
    a.listing()
    a.prompt("Work hoopit/api#1 end to end")
    a.skill("hoopit-dev:ship")
    a.bash("cat .claude/skills/create-worktree/SKILL.md", "# create-worktree")
    a.call("Read", {"file_path": "/tmp/review-gate.Ab12/spec-probe/.claude/skills/create-worktree/SKILL.md"})
    a.bash("git fetch -q; .claude/skills/create-worktree/create-worktree.sh --fetch GH-1/x 2>&1 | tail -3",
           "Worktree ready")
    a.bash(f"cd {api}/.worktrees/GH-1-x && git branch -m GH-1/fix/x")
    a.bash("git push -u origin HEAD", "error: failed to push some refs", error=True)
    a.bash("git push -u origin HEAD", "ok")
    a.call("Agent", {"prompt": "review"}, "done", id="toolu_agent")
    a.prompt("no, that's the wrong branch name")
    a.slash("hoopit-dev:review-gate")
    a.bash("true")
    a.write()
    sub = Transcript(root / "-api" / "aaaa" / "subagents" / "agent-x1.jsonl", str(api))
    sub.prompt("review this", origin="task")
    sub.bash("git diff", tokens=5000)
    sub.write()
    (sub.path.with_suffix(".meta.json")).write_text(json.dumps({"toolUseId": "toolu_agent"}))

    # A flutter session that skips setup steps, then pushes ungenerated code.
    b = Transcript(root / "-flutter-app" / "bbbb.jsonl", str(app))
    b.prompt("Make a worktree and fix the login screen")
    b.skill("create-worktree")
    b.bash("git worktree add --detach /tmp/review-gate.Zz/spec-probe HEAD")
    b.bash("P=/tmp/scratch/probe; git worktree add --detach \"$P\" HEAD")
    b.bash("BRANCH=GH-2/fix/login; WT=\".worktrees/$BRANCH\"; git worktree add -b \"$BRANCH\" \"$WT\" origin/master")
    b.bash("cd .worktrees/GH-2/fix/login && fvm install")
    b.bash("git status --short", " M .fvmrc\n M lib/login.dart")
    b.bash("git push", "error • Target of URI hasn't been generated: 'x.g.dart'\nerror: failed to push", error=True)
    b.prompt("[Request interrupted by user]", origin=None)
    b.write()

    # A session that edits create-worktree: its use of that skill is authoring, not use.
    c = Transcript(root / "-skills" / "cccc.jsonl", str(tmp / "skills"))
    c.prompt("Tighten the create-worktree skill")
    c.skill("create-worktree")
    c.call("Edit", {"file_path": str(api / ".claude/skills/create-worktree/SKILL.md"), "old_string": "a",
                    "new_string": "b"})
    c.skill("create-gh-issue")
    c.write()

    # An eval run and a review-gate probe never count; neither does a session out of range.
    d = Transcript(root / "-evals" / "dddd.jsonl", str(tmp / "evals" / "fixture"))
    d.prompt("eval prompt")
    d.skill("create-worktree")
    d.write()
    e = Transcript(root / "-probe" / "eeee.jsonl", "/tmp/review-gate.Qq/standards-probe")
    e.prompt("probe")
    e.skill("create-worktree")
    e.write()
    f = Transcript(root / "-api" / "ffff.jsonl", str(api), day="2026-08-01")
    f.prompt("old")
    f.skill("create-worktree")
    f.write()
    return root


def report(tmp, root, *args):
    env = {**os.environ, "SKILL_EVAL_HOME": str(tmp / "evals")}
    return subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), "--since", "2026-09-01",
                           "--until", "2026-09-30", "--jobs", "1", *args],
                          env=env, capture_output=True, text=True)


def main():
    failures = []

    def expect(ok, what):
        print(("ok    " if ok else "FAIL  ") + what)
        if not ok:
            failures.append(what)

    with tempfile.TemporaryDirectory() as t:
        tmp = pathlib.Path(t)
        root = build(tmp)
        p = report(tmp, root, "--json")
        expect(p.returncode == 0, f"the report runs (got {p.returncode}: {p.stderr[-600:]})")
        out = json.loads(p.stdout)
        rows = {r["skill"]: r for r in out["rows"]}

        expect("monitor-pr" not in rows, "the skill listing alone never counts as a use")
        cw = rows.get("create-worktree", {})
        expect(cw.get("sessions") == 2, f"create-worktree counts the api and flutter sessions only (got {cw.get('sessions')})")
        expect(cw.get("routes") == {"tool": 1, "slash": 0, "read": 1},
               f"a SKILL.md read is a route, one under a review-gate probe is not (got {cw.get('routes')})")
        expect(rows.get("ship", {}).get("routes", {}).get("tool") == 1, "a Skill tool call is a route")
        expect(rows.get("review-gate", {}).get("routes", {}).get("slash") == 1,
               "a slash command that loads a skill body is a route")
        expect(rows.get("create-gh-issue", {}).get("sessions") == 1,
               "a session editing one skill still counts the others it uses")

        expect(cw.get("failed_spans") == 2, f"both create-worktree spans saw a failed call (got {cw.get('failed_spans')})")
        expect(cw.get("redo_spans") == 1, f"the failed push run again is a redo (got {cw.get('redo_spans')})")
        expect(cw.get("corrected") == 1, "a human prompt that reads as a correction ends a span as corrected")
        expect(cw.get("interrupted") == 1, "an interrupt ends a span as interrupted")
        expect(cw.get("tokens", {}).get("sum", 0) >= 5000 + 6 * 100,
               f"a span's tokens include the subagent it dispatched (got {cw.get('tokens')})")
        expect(rows.get("ship", {}).get("turns", {}).get("p50") == 1,
               "a span ends where the next skill starts: ship's holds only its own Skill call")

        sig = {s["repo"]: s for s in out["signals"].get("create-worktree", [])}
        expect(set(sig) == {"api", "flutter-app"}, f"probes and unresolved paths are no creations (got {sorted(sig)})")
        api, app = sig.get("api", {}), sig.get("flutter-app", {})
        expect(api.get("creations") == 1 and api.get("creation failed", 0) == 0, "the script run is one clean creation")
        expect(api.get("renamed") == 1, "a branch renamed right after creation is counted")
        expect(app.get("creations") == 1, "a raw `git worktree add` with its path in variables is a creation")
        expect(app.get("steps skipped") == 1, "a flutter worktree missing setup steps is counted")
        expect(app.get("ungenerated push") == 1, "a push failing on ungenerated code is counted")
        expect(app.get("fvm files dirty") == 1, "a dirty .fvmrc after setup is counted")

        p = report(tmp, root)
        expect(p.returncode == 0 and "create-worktree" in p.stdout and "create-worktree signals" in p.stdout,
               f"the default output is a table (got:\n{p.stdout}{p.stderr[-400:]})")
        p = report(tmp, root, "--by", "week", "--skill", "create-worktree")
        expect("2026-W37" in p.stdout and "ship" not in p.stdout.split("signals")[0],
               f"--by week labels ISO weeks and --skill filters (got:\n{p.stdout})")

    print(f"\n{len(failures)} failed" if failures else "\nall passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
