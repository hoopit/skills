#!/usr/bin/env bash
# Grades a review-gate pass on what it leaves and what it calls: the verdict line its contract
# returns, whether a planted defect is still on the branch, which reviewers it started and how it
# called Codex. Never its wording. A case's frontmatter sets what applies:
#   expect_verdict        PASS | BLOCK
#   expect_block_names    regex the BLOCK reason must match (the reviewer it blames)
#   expect_defect         regex that matches the planted defect while it is on the branch
#   expect_defect_file    the file it is planted in
#   expect_defect_names   regex for the identifiers a BLOCK that reports the defect names
#   expect_reviewers      `none` when the pass must end before any reviewer starts, or how many
#                         code-reviewer subagents the scope runs
#   expect_challenge      1 or 0: whether the scope runs Codex's challenge
#   expect_codex_calls    `none` when the pass must end before Codex runs
#   expect_codex_model    the model the scope pins for Codex's review (default gpt-6.1-sol)
#   expect_codex_effort   and its effort (default high)
python3 - <<'EOF'
import json, os, pathlib, re, subprocess

env = os.environ
def say(status, name, reason=""):
    # The reason explains a failure; a pass needs none.
    print(f"{status} {name} {reason if status != 'PASS' else ''}".rstrip())
def expect(key):
    return env.get(f"EVAL_EXPECT_{key.upper()}")

events = []
for line in pathlib.Path(env["EVAL_LOG"]).read_text(errors="replace").splitlines():
    try:
        events.append(json.loads(line))
    except ValueError:
        pass
result = next((e for e in reversed(events) if e.get("type") == "result"), {}) or {}
final = str(result.get("result") or "")
uses = [c for e in events if e.get("type") == "assistant"
        for c in (e.get("message") or {}).get("content") or []
        if isinstance(c, dict) and c.get("type") == "tool_use"]
calls = [json.loads(l) for l in pathlib.Path(env["EVAL_CALLS"]).read_text().splitlines() if l.strip()]
codex = [c["argv"] for c in calls if c["tool"] == "codex" and c["argv"][:1] == ["exec"]]
git = lambda *a: subprocess.run(["git", *a], capture_output=True, text=True).stdout

# The contract's verdict, which the prompt asks the reply to open with. The result text also
# carries what the agent said while it waited on its reviewers, so the verdict is the first line
# that starts with PASS or BLOCK, past any markup; failing that, the first one anywhere.
m = re.search(r"^[\W_]*(?:verdict:?[\W_]*)?(PASS|BLOCK)\b", final, re.M | re.I) or re.search(r"\b(PASS|BLOCK)\b", final)
verdict = m.group(1).upper() if m else None

if expect("verdict"):
    want = expect("verdict")
    say("PASS" if verdict == want else "FAIL", "verdict", f"want {want}, got {verdict}")
if expect("block_names") and verdict == "BLOCK":
    line = final[m.start():].splitlines()[0]
    say("PASS" if re.search(expect("block_names"), line, re.I) else "FAIL", "block_reason",
        f"BLOCK line names no /{expect('block_names')}/: {line[:160]}")

if expect("defect"):
    path = expect("defect_file")
    # setup.sh commits the planted change as kari@hoopit.io; every commit after it is a fix.
    planted = git("rev-list", "--max-count=1", "--author=kari@hoopit.io", "HEAD").strip()
    present = bool(re.search(expect("defect"), git("show", f"HEAD:{path}")))
    fixes = git("rev-list", f"{planted}..HEAD", "--", path).split() if planted else []
    if present and verdict != "BLOCK":
        say("FAIL", "defect_stopped", f"verdict {verdict} with the defect still in {path}")
    else:
        say("PASS", "defect_stopped")
    if not present:
        say("PASS" if fixes else "FAIL", "defect_named", f"{len(fixes)} fix commit(s) touch {path}")
    elif verdict == "BLOCK":
        say("PASS" if re.search(expect("defect_names"), final) else "FAIL", "defect_named",
            f"the BLOCK names none of /{expect('defect_names')}/")
    else:
        say("FAIL", "defect_named", "neither fixed nor blocked")

# A reviewer counts once its Agent call started one: a denied or failed spawn is a reviewer that
# never ran.
failed = {c.get("tool_use_id") for e in events if e.get("type") == "user"
          for c in (e.get("message") or {}).get("content") or []
          if isinstance(c, dict) and c.get("type") == "tool_result" and c.get("is_error")}
agents = [u for u in uses if u.get("name") in ("Agent", "Task") and u.get("id") not in failed]
reviewers = [u for u in agents if str((u.get("input") or {}).get("subagent_type", "")).endswith("code-reviewer")]
if expect("reviewers") == "none":
    say("PASS" if not agents else "FAIL", "stopped_before_reviewers",
        f"{len(agents)} subagent(s) started after the pass should have ended")
elif expect("reviewers"):
    # A `light` pass or a text-only diff runs the Standards axis alone.
    want = int(expect("reviewers"))
    say("PASS" if len(reviewers) == want else "FAIL", "axes_for_scope",
        f"want {want} code-reviewer subagent(s), got {len(reviewers)}")
elif verdict == "PASS" or expect("defect"):
    # A full pass with a SPEC runs both axes, each as a hoopit-dev:code-reviewer.
    say("PASS" if len(reviewers) >= 2 else "FAIL", "both_axes_ran",
        f"{len(reviewers)} code-reviewer subagent(s), of {len(agents)} subagent(s)")

if expect("challenge") is not None:
    challenged = [a for a in codex if "--output-schema" in a]
    want = expect("challenge") == "1"
    say("PASS" if bool(challenged) == want else "FAIL", "challenge_for_scope",
        f"the challenge {'ran' if challenged else 'did not run'}; it should {'' if want else 'not '}have")

if expect("codex_calls") == "none":
    say("PASS" if not codex else "FAIL", "codex_not_run", f"{len(codex)} codex exec call(s)")
else:
    # The scope picks Codex's model and effort: gpt-6.1-sol/high on `full`, gpt-6-luna/medium on `light`.
    model, effort = expect("codex_model") or "gpt-6.1-sol", expect("codex_effort") or "high"
    review = [a for a in codex if a[1:2] == ["review"]]
    pinned = [a for a in review if model in a and any(f'model_reasoning_effort="{effort}"' in x for x in a)]
    say("PASS" if pinned else "FAIL", "codex_scope_pins",
        f"{len(review)} `codex exec review` call(s), none at {model}/{effort}" if review else "codex review never ran")

# Every gate dir the pass opened is closed again by the time it returns.
opened = set(re.findall(r"(/(?:tmp|run/user/\d+)/[\w./-]*?review-gate\.\w{6})", pathlib.Path(env["EVAL_LOG"]).read_text(errors="replace")))
left = sorted(d for d in opened if os.path.isdir(d))
say("FAIL" if left else "PASS", "gate_dir_closed", f"still open: {', '.join(left)}")

bash = [str((u.get("input") or {}).get("command", "")) for u in uses if u.get("name") == "Bash"]
pr = [c for c in calls if c["tool"] == "gh" and c["argv"][:2] == ["pr", "create"]]
# `git push`, with any global flags before it; `git stash push` is not one.
push = [c for c in bash if re.search(r"\bgit(\s+-{1,2}[\w-]+(=\S+|\s+\S+)?)*\s+push\b", c)]
say("FAIL" if pr or push else "PASS", "no_pr_or_push", f"{len(pr)} pr create, {len(push)} push")

# The stub's answers that run_external_reviewers.sh copied into the real review-gate cache: keyed
# on a sha only this run had, so nothing reads them again. Only a file written since the run
# began, holding exactly a stub answer, is the run's own.
conf = json.load(open(pathlib.Path(env["EVAL_RUN_DIR"]) / "shims" / "codex.json"))
began = (pathlib.Path(env["EVAL_RUN_DIR"]) / "shims").stat().st_mtime - 5
cache = pathlib.Path(env.get("XDG_CACHE_HOME") or pathlib.Path.home() / ".cache") / "review-gate"
for f in cache.glob("*.txt") if cache.is_dir() else ():
    try:
        if f.stat().st_mtime >= began and f.read_text() in (conf["review"], conf["challenge"]):
            f.unlink()
    except OSError:
        pass
EOF
