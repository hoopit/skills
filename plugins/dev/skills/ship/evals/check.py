"""The checks behind check.sh: what ship reached, in what order, and what each handoff
carried, read from the recorded calls (the shims and the stand-ins), the run's origin and
the agent's log. A case's `expect_*` frontmatter says what it wants:

    expect_board       1 when the run itself must `hoopit-board start` the issue, before Step 2
    expect_red         1 when the regression test must go red with the fix absent
    expect_cpr_order   1 when create-pull-request must be loaded before the first commit
    expect_spec        regex the first gate pass's SPEC must match
    expect_rounds      the number of gate passes a clean run makes
    expect_unattended  1 when monitor-pr must get --unattended, 0 when it must not
    expect_blocked     1 when the gate blocks: nothing may be pushed or opened
    expect_footer      regex every pushed commit's message must match: a caller's ask
    expect_section     regex the PR body must match: a caller's ask
"""
import json, os, re, subprocess, sys

sys.path.insert(0, os.path.join(os.environ["EVAL_SUITE_DIR"], "../../create-pull-request/evals"))
import pr_state

env = os.environ
E = lambda k: env.get(f"EVAL_EXPECT_{k}")
run_dir, fixture = env["EVAL_RUN_DIR"], env["EVAL_FIXTURE"]
origin = os.path.join(run_dir, "origin.git")
VIEW = "posts/views/post_image_detail_view.py"
PR = "18412"


def say(ok, name, why=""):
    print(f"PASS {name}" if ok else f"FAIL {name} {why}".rstrip())


def git(*args, cwd=fixture):
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    return p.stdout.strip()


calls = [json.loads(l) for l in open(env["EVAL_CALLS"]) if l.strip()]
gate = [c for c in calls if c["tool"] == "review-gate"]
monitor = [c for c in calls if c["tool"] == "monitor-pr"]
state = pr_state.load(run_dir, env["EVAL_CALLS"])
before = dict(l.split() for l in open(os.path.join(run_dir, "origin-heads")) if l.strip())

# The agent's tool calls in order, each with what it returned.
steps, by_id = [], {}
for line in open(env["EVAL_LOG"], errors="replace"):
    try:
        e = json.loads(line)
    except ValueError:
        continue
    for c in (e.get("message") or {}).get("content") or []:
        if not isinstance(c, dict):
            continue
        if c.get("type") == "tool_use":
            step = {"name": c.get("name"), "input": c.get("input") or {}, "out": "", "error": False}
            steps.append(step)
            by_id[c.get("id")] = step
        elif c.get("type") == "tool_result" and c.get("tool_use_id") in by_id:
            out = c.get("content")
            if isinstance(out, list):
                out = "\n".join(str(b.get("text", "")) for b in out if isinstance(b, dict))
            by_id[c["tool_use_id"]].update(out=str(out or ""), error=bool(c.get("is_error")))


def command(s):
    return str(s["input"].get("command", "")) if s["name"] == "Bash" else ""


def first(pred):
    return next((i for i, s in enumerate(steps) if pred(s)), None)


# --- Step 0: the board ------------------------------------------------------------------
if E("BOARD") == "1":
    started = [c for c in calls if c["tool"] == "hoopit-board" and c["argv"][:1] == ["start"]
               and "18161" in " ".join(c["argv"])]
    board_at = first(lambda s: re.search(r"\bhoopit-board\s+start\b", command(s)))
    wt_at = first(lambda s: re.search(r"worktree\s+add|create-worktree\.sh", command(s)))
    if not started:
        say(False, "board_started", "no hoopit-board start hoopit/api 18161")
    else:
        say(wt_at is None or (board_at is not None and board_at < wt_at), "board_started",
            "started after the worktree was made")

# --- Step 2: a worktree, the main checkout untouched -----------------------------------
worktrees = os.path.join(fixture, ".worktrees") + os.sep
outside = [c["toplevel"] for c in gate if not (c["toplevel"] + os.sep).startswith(worktrees)]
main_dirty = git("status", "--porcelain", "--untracked-files=no")
main_head = git("rev-parse", "HEAD")
say(not outside and not main_dirty and main_head == before["refs/heads/master"],
    "worktree", f"gate ran in {outside[0]}" if outside else
    "the main checkout has changes" if main_dirty else "the main checkout moved")

# --- Steps 3 and 4: red before the fix --------------------------------------------------
if E("RED") == "1":
    def edits_view(s):
        if s["name"] in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
            return str(s["input"].get("file_path", "")).endswith(VIEW)
        cmd = command(s)
        # The test module's name contains the view's: test_post_image_detail_view.py.
        return re.search(r"(?<!test_)post_image_detail_view\.py", cmd) \
            and re.search(r"sed -i|>\s*\S*(?<!test_)post_image_detail_view|python|perl|patch|git apply|tee", cmd) \
            and not re.search(r"\bgit\s+(stash|checkout|restore|show|diff|log)\b", cmd)
    # The fix is absent until the view is first edited, and again while it is stashed or
    # the view is put back from a ref; an edit after that puts it back.
    def reverts_view(cmd):
        return re.search(r"\bgit\s+(checkout|restore)\b[^\n;&|]*post_image_detail_view", cmd) or \
            re.search(r"\bgit\s+show\s+\S+:posts/views/post_image_detail_view\.py\s*>", cmd)
    fixed, absent, red, ran = False, False, False, False
    for s in steps:
        cmd = command(s)
        if re.search(r"\bgit\s+stash(\s+(push|save)\b|\s*($|[;&|]))", cmd) or reverts_view(cmd):
            absent = True
        if "pytest" in cmd:
            ran = True
            failed = re.search(r"\b\d+ failed\b|\bFAILED\b|DoesNotExist|AssertionError", s["out"])
            if failed and (not fixed or absent):
                red = True
        if re.search(r"\bgit\s+stash\s+(pop|apply)\b", cmd):
            absent = False
        elif edits_view(s) and not reverts_view(cmd):
            fixed, absent = True, False
    say(red, "red_before_fix", "no test run failed with the fix absent" if ran else "no pytest run")

# --- Step 5: create-pull-request loaded before the first commit ------------------------
if E("CPR_ORDER") == "1":
    cpr = first(lambda s: (s["name"] == "Skill" and "create-pull-request" in str(s["input"].get("skill", "")))
                or "create-pull-request/SKILL.md" in str(s["input"].get("file_path", "")) + command(s))
    commit = first(lambda s: re.search(r"\bgit\b[^\n;&|]*\bcommit\b", command(s)))
    if commit is None:
        say(False, "cpr_before_commit", "no commit")
    else:
        say(cpr is not None and cpr < commit, "cpr_before_commit",
            "loaded after the first commit" if cpr is not None else "never loaded")

# --- Step 6: the gate's handoff ---------------------------------------------------------
if not gate:
    say(False, "gate_ran", "review-gate never ran")
else:
    say(True, "gate_ran")
    one = gate[0]["inputs"]
    problems = [p for p, bad in [
        (f"SCOPE {one['scope']}", one["scope"] != "full"),
        ("no SPEC", not (one["spec"] or "").strip()),
        (f"SPEC does not match {E('SPEC')}", bool(E("SPEC") and (one["spec"] or "").strip()
                                                  and not re.search(E("SPEC"), one["spec"]))),
        ("no CHALLENGE", not (one["challenge"] or "").strip()),
    ] if bad]
    say(not problems, "gate_handoff", ", ".join(problems))
    dirty = [c["pass"] for c in gate if c["dirty"]]
    say(not dirty, "gate_on_commits", f"pass {dirty[0]} ran over uncommitted changes" if dirty else "")
    # Each later pass names its fixed point: REVIEWED_AT is where the pass before it
    # started, so a pass from the fix commit itself reviews nothing.
    later = []
    for prev, nxt in zip(gate, gate[1:]):
        i = nxt["inputs"]
        if i["scope"] == "light" and i["reviewed_at"] and nxt["head"].startswith(i["reviewed_at"]):
            later.append(f"pass {nxt['pass']} ran light from HEAD itself ({i['reviewed_at'][:10]}): "
                         f"an empty range, want {prev['head'][:10]}")
        if not (i["prior_rounds"] or "").strip():
            later.append(f"pass {nxt['pass']}: no PRIOR_ROUNDS")
    if E("ROUNDS"):
        want = int(E("ROUNDS"))
        say(len(gate) >= want and not later, "gate_rounds",
            "; ".join(later) or f"{len(gate)} passes, want {want} or more")

# --- Step 7: the push carries only what the gate reviewed -------------------------------------
now = dict(l.split() for l in git("--git-dir", origin, "for-each-ref", "--format=%(refname) %(objectname)",
                                   "refs/heads").splitlines())
pushed = {r: sha for r, sha in now.items() if before.get(r) != sha}
if E("BLOCKED") == "1":
    say(not pushed, "no_push_on_block", "pushed " + ", ".join(pushed))
    say(not state["creates"], "no_pr_on_block", "gh pr create ran")
    say(not monitor, "no_watch_on_block", "monitor-pr ran")
    # The ask after a hand-back cannot be graded: a `-p` run has no AskUserQuestion.
else:
    if len(pushed) != 1:
        say(False, "pushed", f"{len(pushed)} branches pushed")
    else:
        (ref, tip), = pushed.items()
        say(True, "pushed")
        # Every pushed commit sits in the range some pass reviewed, or is a text-only fix.
        seen = set()
        for c in gate:
            since = c["inputs"]["reviewed_at"] if c["inputs"]["scope"] == "light" and c["inputs"]["reviewed_at"] \
                else before["refs/heads/master"]
            seen |= set(git("rev-list", f"{since}..{c['head']}").split())
            if c["fix"] == "text-only":
                seen |= set(git("rev-list", f"{c['head']}..{c['after']}").split())
        unseen = [x for x in git("rev-list", f"{before['refs/heads/master']}..{tip}").split() if x not in seen]
        if E("FOOTER"):
            msgs = [m for m in git("--git-dir", origin, "log", "--format=%B%x00",
                                   f"{before['refs/heads/master']}..{tip}").split("\0") if m.strip()]
            bad = [m.strip().splitlines()[0] for m in msgs if not re.search(E("FOOTER"), m)]
            say(msgs and not bad, "commit_footer", f"{bad[0]!r} lacks {E('FOOTER')}" if bad else "no commits")
        say(not unseen, "push_reviewed",
            f"{len(unseen)} pushed commits no pass reviewed, first {unseen[-1][:10]} "
            f"{git('log', '-1', '--format=%s', unseen[-1])!r}" if unseen else "")
    n = len(state["creates"])
    say(n == 1, "pr_created", f"gh pr create ran {n} times")
    if n:
        body = state["body"] or ""
        missing = [w for w, rx in [("closes #18161", None), ("## Testing", r"(?m)^#+\s*Testing"),
                                   ("review-gate notes", r"(?i)review.gate")]
                   if (rx and not re.search(rx, body)) or (not rx and 18161 not in pr_state.closing_numbers(body))]
        say(not missing, "pr_body", "lacks " + ", ".join(missing))
        if E("SECTION"):
            say(re.search(E("SECTION"), body), "pr_caller_section", f"no {E('SECTION')} in the body")
    # --- Step 8: the watch ---------------------------------------------------------------
    if len(monitor) != 1:
        say(False, "monitor_handoff", f"monitor-pr armed {len(monitor)} times")
    else:
        argv = monitor[0]["argv"]
        problems = []
        if not any(PR in a for a in argv):
            problems.append(f"no PR {PR} in {' '.join(argv)}")
        if not any(a.startswith("--subagent") for a in argv):
            problems.append("no --subagent")
        if E("UNATTENDED") is not None and ("--unattended" in argv) != (E("UNATTENDED") == "1"):
            problems.append("--unattended dropped" if E("UNATTENDED") == "1" else "--unattended added")
        say(not problems, "monitor_handoff", ", ".join(problems))

# A probe of the CLI (`codex --version`) runs no reviewer; anything else went around the gate.
codex = [c for c in calls if c["tool"] == "codex"
         and not set(c["argv"]) <= {"--version", "-V", "--help", "-h", "login", "status"}]
say(not codex, "gate_not_bypassed", f"codex {' '.join(codex[0]['argv'])[:80]}" if codex else "")
