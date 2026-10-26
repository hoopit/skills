#!/usr/bin/env bash
# Grades what the run left behind: the target branch and worktree removed or kept as the
# case expects, everything else untouched, and the calls the agent made on the way.
#
# The skill has no tab step: closing the session's herdr tab belongs to monitor-pr's
# landing (LANDING.md step 4), after this skill returns. So any herdr call fails
# tab_untouched, and the herdr shim keeps the run away from the real server either way.
exec python3 - <<'PY'
import json, os, re, subprocess

env = os.environ
fixture = env["EVAL_FIXTURE"]
want = env["EVAL_EXPECT_TARGET"]           # removed | kept
branch = env["EVAL_EXPECT_BRANCH"]
worktree = os.path.join(fixture, env["EVAL_EXPECT_WORKTREE"])
pr = env.get("EVAL_EXPECT_PR", "")
SIBLING = "GH-18270/fix/attendance-export-timezone"
SIBLING_WT = os.path.join(fixture, ".worktrees/GH-18270-fix-attendance-export-timezone")


def say(ok, name, why=""):
    print(f"PASS {name}" if ok else f"FAIL {name} {why}".rstrip())


def git(*args):
    p = subprocess.run(["git", "-C", fixture, *args], capture_output=True, text=True)
    return p.returncode, p.stdout.strip()


def has_branch(name):
    return git("rev-parse", "--quiet", "--verify", f"refs/heads/{name}")[0] == 0


registered = {l[9:] for l in git("worktree", "list", "--porcelain")[1].splitlines() if l.startswith("worktree ")}

# The agent's Bash calls, each with what it printed.
commands, results = {}, {}
for line in open(env["EVAL_LOG"], errors="replace"):
    try:
        e = json.loads(line)
    except ValueError:
        continue
    for c in (e.get("message") or {}).get("content") or []:
        if not isinstance(c, dict):
            continue
        if c.get("type") == "tool_use" and c.get("name") == "Bash":
            commands[c.get("id")] = str((c.get("input") or {}).get("command", ""))
        elif c.get("type") == "tool_result" and c.get("tool_use_id") in commands:
            body = c.get("content")
            if isinstance(body, list):
                body = "\n".join(str(b.get("text", "")) for b in body if isinstance(b, dict))
            results[c["tool_use_id"]] = str(body or "")
calls = [json.loads(l) for l in open(env["EVAL_CALLS"]) if l.strip()]

# --- end state ---------------------------------------------------------------------
if want == "removed":
    say(not has_branch(branch), "target_branch", f"{branch} still exists")
    gone = not os.path.exists(worktree) and worktree not in registered
    say(gone, "target_worktree", "directory still there" if os.path.exists(worktree)
        else "git still lists it")
else:
    say(has_branch(branch), "target_branch", f"{branch} was deleted")
    kept = os.path.isdir(worktree) and worktree in registered
    say(kept, "target_worktree", "directory removed" if not os.path.isdir(worktree)
        else "git no longer lists it")

say(has_branch(SIBLING) and os.path.isdir(SIBLING_WT) and SIBLING_WT in registered,
    "sibling_untouched", "another merged branch or its worktree was removed")
code, master = git("rev-parse", "refs/heads/master")
say(code == 0 and master == env["EVAL_BASE"] and fixture in registered, "main_untouched",
    f"master is {master or 'gone'}, base {env['EVAL_BASE'][:10]}")

# --- the calls ---------------------------------------------------------------------
asked = [c for c in calls if c["tool"] == "gh" and
         any(branch in a or (pr and re.search(rf"\b{pr}\b", a)) for a in c["argv"])]
say(bool(asked), "merge_state_read", "no gh call asked GitHub about the target's PR")

forced = [c for c in commands.values() if re.search(r"worktree\s+remove\b[^\n;&|]*\s(--force|-f)\b", c)]
say(not forced, "no_force", forced[0][:120] if forced else "")

pushes = [c for c in commands.values() if re.search(r"\bgit\b[^\n;&|]*\bpush\b", c)]
say(not pushes, "remote_untouched", pushes[0][:120] if pushes else "")

herdr = [" ".join(c["argv"]) for c in calls if c["tool"] == "herdr"]
say(not herdr, "tab_untouched", f"herdr {herdr[0]}" if herdr else "")

# field-report's failure signal: a line that starts with fatal: or error:.
ERROR_LINE = re.compile(r"(?m)^\s*(?:error|fatal):.*$")
loud = [m.group(0).strip() for r in results.values() for m in [ERROR_LINE.search(r)] if m]
say(not loud, "no_fatal_output", f"{len(loud)} calls, first: {loud[0][:100]}" if loud else "")

# Removing the worktree the shell stands in fails the call that removed it, and the next one.
if os.path.exists(env["EVAL_CWD"]):
    print("SKIP cwd_survives the start dir was not removed")
else:
    lost = [r for r in results.values()
            if "getcwd: cannot access parent directories" in r or "was deleted; shell cwd recovered" in r]
    say(not lost, "cwd_survives", f"{len(lost)} calls lost their cwd")
PY
