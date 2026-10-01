#!/usr/bin/env python3
"""Pins `skill-eval`'s fixture, isolation and grading. Run it by hand after editing either:

    python3 plugins/dev/tests/test_skill_eval.py

No network, no model and no pytest: a fake `claude` replays the `RUN:` lines of each
case's prompt as Bash tool calls and writes the stream-json log a real one would, so the
whole file runs offline in a few seconds.

What it guards is the runner's promises to whoever reads a score. The agent sees the
version under test and never the suite; the agent's writes stay out of the real repo
and off the real remote and tracker; and a run that times out, fails its setup or
reaches for the real repo is graded as such rather than as a pass.
"""
import json, os, pathlib, subprocess, sys, tempfile, textwrap

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "skills" / "skill-eval" / "scripts" / "skill-eval"

FAKE_CLAUDE = r'''#!/usr/bin/env python3
import json, subprocess, sys, time
args = sys.argv[1:]
prompt = args[args.index("-p") + 1]
emit = lambda e: print(json.dumps(e), flush=True)
emit({"type": "system", "subtype": "init", "model": "fake-model", "argv": args})
turns = 0
for line in prompt.splitlines():
    if line.startswith("RUN: "):
        cmd = line[5:]
        emit({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Bash", "input": {"command": cmd}}]}})
        p = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True)
        emit({"type": "user", "message": {"content": [
            {"type": "tool_result", "content": p.stdout + p.stderr}]}})
        turns += 1
    elif line.startswith("SLEEP: "):
        time.sleep(float(line[7:]))
emit({"type": "result", "subtype": "success", "is_error": False,
      "num_turns": turns, "total_cost_usd": 0.01})
'''

SUITE_CHECK = textwrap.dedent('''\
    #!/usr/bin/env bash
    cd "$EVAL_FIXTURE"
    if grep -q "$EVAL_EXPECT_VERSION" .claude/skills/demo/SKILL.md; then echo "PASS version"
    else echo "FAIL version got $(cat .claude/skills/demo/SKILL.md)"; fi
    if [ -e .claude/skills/demo/evals ]; then echo "FAIL evals_hidden"; else echo "PASS evals_hidden"; fi
    if git worktree list | grep -q '/.worktrees/feat-x '; then echo "PASS worktree"
    else echo "FAIL worktree none under .worktrees/"; fi
    if [ "$(git rev-parse origin/master)" = "$EVAL_BASE" ]; then echo "PASS origin_is_base"
    else echo "FAIL origin_is_base"; fi
    if [ "$EVAL_SLOW" = 1 ]; then echo "PASS slow_smoke"; else echo "SKIP slow_smoke not asked"; fi
''')


def sh(*args, cwd=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    subprocess.run(args, cwd=cwd, env=env, check=True, capture_output=True)


def write(path, text, mode=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    if mode:
        path.chmod(mode)


def case(evals, name, prompt, meta="", check=None, setup=None, mocks=None):
    write(evals / name / "prompt.md", f"---\nexpect_version: v2-working-tree\n{meta}---\n\n{prompt}\n")
    if check:
        write(evals / name / "check.sh", check)
    if setup:
        write(evals / name / "setup.sh", setup)
    for tool, answers in (mocks or {}).items():
        write(evals / name / "mocks" / f"{tool}.json", json.dumps(answers))


def build(tmp):
    """A source repo whose `demo` skill has an uncommitted edit, and a suite for it."""
    src = tmp / "src"
    skill = src / ".claude" / "skills" / "demo"
    write(skill / "SKILL.md", "---\nname: demo\n---\nv1-committed\n")
    evals = skill / "evals"
    write(evals / "check.sh", SUITE_CHECK)
    case(evals, "creates", "RUN: git worktree add -q -b feat/x .worktrees/feat-x")
    case(evals, "idle", "RUN: true", meta="effort: high\n")
    case(evals, "leaks", f"RUN: git -C {src} branch leaked-branch")
    case(evals, "pushes", "RUN: git push origin HEAD:refs/heads/pushed-branch")
    case(evals, "isolated", "RUN: gh issue view 1\nRUN: env\nRUN: hoopit-board config\nRUN: git status | tail -1\n"
         "RUN: cat \"$CLAUDE_CONFIG_DIR/.claude.json\"",
         check=textwrap.dedent('''\
            #!/usr/bin/env bash
            grep -q 'gh is disabled in a skill-eval run' "$EVAL_LOG" && echo "PASS gh_shimmed" || echo "FAIL gh_shimmed"
            grep -q 'hoopit-board is disabled in a skill-eval run' "$EVAL_LOG" \\
              && echo "PASS board_shimmed" || echo "FAIL board_shimmed"
            grep -q '"argv": \\["issue", "view", "1"\\]' "$EVAL_CALLS" \\
              && echo "PASS unmocked_recorded" || echo "FAIL unmocked_recorded"
            grep -q 'GH_TOKEN=' "$EVAL_LOG" && echo "FAIL token_scrubbed" || echo "PASS token_scrubbed"
            grep -q "CLAUDE_CONFIG_DIR=$EVAL_RUN_DIR/claude-config" "$EVAL_LOG" \\
              && echo "PASS own_config" || echo "FAIL own_config"
            grep -q "$EVAL_FIXTURE"'\\\\"\\{1,\\}: *{\\\\"\\{1,\\}hasTrustDialogAccepted' "$EVAL_LOG" \\
              && echo "PASS fixture_trusted" || echo "FAIL fixture_trusted"
            grep -q 'DISABLE_AUTOUPDATER=1' "$EVAL_LOG" && echo "PASS no_autoupdate" || echo "FAIL no_autoupdate"
         '''))
    # What Claude does to the plugin store as it runs: a project entry per fixture, an
    # auto-update that installs a new version, a marketplace refresh.
    plugins = '"$CLAUDE_CONFIG_DIR/plugins"'
    case(evals, "plugin-store",
         f"RUN: cat {plugins}/installed_plugins.json {plugins}/known_marketplaces.json\n"
         f"RUN: echo '{{\"plugins\": {{}}}}' > {plugins}/installed_plugins.json\n"
         f"RUN: echo changed >> {plugins}/cache/demo-market/demo-plugin/1/plugin.txt\n"
         f"RUN: mkdir -p {plugins}/cache/demo-market/demo-plugin/2 && touch {plugins}/cache/demo-market/demo-plugin/2/new\n"
         f"RUN: rm {plugins}/known_marketplaces.json",
         check=textwrap.dedent('''\
            #!/usr/bin/env bash
            own="$EVAL_RUN_DIR/claude-config/plugins"
            grep -q "$own/cache/demo-market/demo-plugin/1" "$EVAL_LOG" \\
              && echo "PASS install_path_own" || echo "FAIL install_path_own"
            grep -q "$own/cache/demo-market/unrelated/2" "$EVAL_LOG" \\
              && echo "PASS dead_path_rerooted" || echo "FAIL dead_path_rerooted"
            grep -q "$own/marketplaces/demo-market" "$EVAL_LOG" \\
              && echo "PASS marketplace_own" || echo "FAIL marketplace_own"
            grep -q 'autoUpdate[^,}]*false' "$EVAL_LOG" && echo "PASS marketplace_frozen" || echo "FAIL marketplace_frozen"
            grep -q "$SKILL_EVAL_HOME/claude-config/plugins" "$EVAL_LOG" \\
              && echo "FAIL shared_unnamed" || echo "PASS shared_unnamed"
         '''))
    # A session that began in a sibling repo: the agent starts there and reaches the fixture as ../src.
    case(evals, "elsewhere",
         "RUN: pwd\nRUN: cat \"$CLAUDE_CONFIG_DIR/.claude.json\"\n"
         "RUN: test -f ../src/.claude/skills/demo/SKILL.md && echo reaches-fixture",
         meta="cwd: api\n", setup="#!/usr/bin/env bash\ngit init -q \"$EVAL_RUN_DIR/api\"\n",
         check=textwrap.dedent('''\
            #!/usr/bin/env bash
            exec python3 - <<'PY'
            import json, os
            env = os.environ
            out = [c["content"] for e in map(json.loads, open(env["EVAL_LOG"])) if e.get("type") == "user"
                   for c in e["message"]["content"]]
            start = os.path.join(env["EVAL_RUN_DIR"], "api")
            say = lambda ok, name, why="": print(f"PASS {name}" if ok else f"FAIL {name} {why}")
            say(out and out[0].strip() == start, "started_in_cwd", out[:1])
            say(env["EVAL_CWD"] == start, "eval_cwd", env["EVAL_CWD"])
            say(os.getcwd() == env["EVAL_FIXTURE"], "checks_in_fixture", os.getcwd())
            trusted = json.loads(out[1])["projects"] if len(out) > 1 else {}
            say(all(trusted.get(d, {}).get("hasTrustDialogAccepted") for d in (start, env["EVAL_FIXTURE"])),
                "cwd_trusted", trusted)
            say(len(out) > 2 and "reaches-fixture" in out[2], "sibling_fixture", out[2:])
            PY
         '''))
    case(evals, "cwd-missing", "RUN: true", meta="cwd: nowhere\n")
    case(evals, "mocked",
         "RUN: printf 'Adds x.\\n\\ncloses #3\\n' | gh pr create --title 'BAC-12 Add x' --body-file -\n"
         "RUN: gh issue view 9\nRUN: hoopit-board triage hoopit/api 3",
         mocks={"gh": [{"match": "^pr create .*--title BAC-", "stdout": "https://github.com/o/r/pull/7\n"},
                       {"match": "^pr create", "stderr": "title lacks the key\n", "exit": 1}]},
         check=textwrap.dedent('''\
            #!/usr/bin/env bash
            exec python3 - <<'PY'
            import json, os
            calls = [json.loads(l) for l in open(os.environ["EVAL_CALLS"])]
            pr = [c for c in calls if c["tool"] == "gh" and c["argv"][:2] == ["pr", "create"]]
            ok = pr and pr[0]["argv"][pr[0]["argv"].index("--title") + 1].startswith("BAC-12")
            print("PASS pr_title" if ok else f"FAIL pr_title {calls}")
            ok = pr and "closes #3" in (pr[0]["stdin"] or "").splitlines()
            print("PASS closes_line" if ok else f"FAIL closes_line {calls}")
            ok = pr and pr[0]["cwd"] == os.environ["EVAL_FIXTURE"]
            print("PASS call_cwd" if ok else f"FAIL call_cwd {calls}")
            print("PASS board_recorded" if any(c["tool"] == "hoopit-board" for c in calls)
                  else f"FAIL board_recorded {calls}")
            log = open(os.environ["EVAL_LOG"]).read()
            print("PASS answered" if "pull/7" in log else "FAIL answered")
            print("PASS unmatched_visible" if "no mock for: issue view 9" in log else "FAIL unmatched_visible")
            print("PASS unmocked_tool_fails" if "hoopit-board: no mock for: triage" in log
                  else "FAIL unmocked_tool_fails")
            print("FAIL token_scrubbed" if "secret-must-not-leak" in json.dumps(calls) + log
                  else "PASS token_scrubbed")
            PY
         '''))
    case(evals, "slow", "SLEEP: 30", meta="timeout_seconds: 2\n")
    case(evals, "bad-setup", "RUN: touch should-not-run", setup="#!/usr/bin/env bash\nexit 3\n")
    sh("git", "init", "-q", "-b", "master", cwd=src)
    sh("git", "add", "-A", cwd=src)
    sh("git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init", cwd=src)
    write(skill / "SKILL.md", "---\nname: demo\n---\nv2-working-tree\n")
    return src, skill


PLUGIN_CHECK = textwrap.dedent('''\
    #!/usr/bin/env bash
    exec python3 - <<'PY'
    import json, os, pathlib, subprocess
    env = os.environ
    git = lambda *a: subprocess.run(["git", *a], capture_output=True, text=True).stdout.strip()
    say = lambda ok, name, why="": print(f"PASS {name}" if ok else f"FAIL {name} {why}")
    init = next(e for e in map(json.loads, open(env["EVAL_LOG"])) if e.get("subtype") == "init")
    argv = init["argv"]
    plugin = pathlib.Path(argv[argv.index("--plugin-dir") + 1])
    skill = (plugin / "skills" / "pskill" / "SKILL.md").read_text()
    say(env["EVAL_EXPECT_VERSION"] in skill, "plugin_version", skill)
    say((plugin / ".claude-plugin" / "plugin.json").is_file(), "plugin_whole")
    say(not list(plugin.rglob("evals")), "plugin_evals_hidden", list(plugin.rglob("evals")))
    settings = json.loads(pathlib.Path(argv[argv.index("--settings") + 1]).read_text())
    off = {"demo-plugin@demo-market": False, "demo-plugin@other-market": False}
    say(settings.get("enabledPlugins") == off, "installed_disabled", settings)
    say(pathlib.Path("product.txt").is_file() and not pathlib.Path("plugins").exists(), "fixture_is_product")
    say(git("rev-parse", "HEAD") == env["EVAL_BASE"] == git("-C", env["EVAL_SOURCE"], "rev-parse", "master"),
        "nothing_committed_over")
    PY
''')


def build_plugin(tmp):
    """A skills repo whose plugin skill `pskill` has an uncommitted edit, and a product repo."""
    repo = tmp / "skills"
    plugin = repo / "plugins" / "demo"
    write(repo / ".claude-plugin" / "marketplace.json", '{"name": "demo-market"}')
    write(plugin / ".claude-plugin" / "plugin.json", '{"name": "demo-plugin"}')
    write(plugin / "skills" / "other" / "SKILL.md", "---\nname: other\n---\n")
    write(plugin / "skills" / "other" / "evals" / "check.sh", "#!/usr/bin/env bash\n")
    skill = plugin / "skills" / "pskill"
    write(skill / "SKILL.md", "---\nname: pskill\n---\nv1-committed\n")
    write(skill / "evals" / "check.sh", PLUGIN_CHECK)
    case(skill / "evals", "loads", "RUN: true")
    product = tmp / "product"
    write(product / "product.txt", "the product\n")
    for src in (repo, product):
        sh("git", "init", "-q", "-b", "master", cwd=src)
        sh("git", "add", "-A", cwd=src)
        sh("git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init", cwd=src)
    write(skill / "SKILL.md", "---\nname: pskill\n---\nv2-working-tree\n")
    return product, skill


def eval_config(tmp):
    """What `setup` leaves behind: the template every run's own config is cut from.

    `unrelated` is installed through another run's config path, as a run that rewrote
    the shared store leaves it.
    """
    config = tmp / "home" / "claude-config"
    write(config / "settings.json", "{}")
    write(config / ".claude.json", '{"projects": {}}')
    cache = config / "plugins" / "cache" / "demo-market"
    write(cache / "demo-plugin" / "1" / "plugin.txt", "v1\n")
    write(cache / "unrelated" / "2" / "plugin.txt", "v2\n")
    write(config / "plugins" / "installed_plugins.json", json.dumps({"plugins": {
        "demo-plugin@other-market": [],
        "demo-plugin@demo-market": [{"scope": "user", "installPath": str(cache / "demo-plugin" / "1")}],
        "unrelated@demo-market": [{"scope": "user", "installPath":
            str(tmp / "home" / "gone-run" / "case-1" / "claude-config" / "plugins" / "cache" / "demo-market" / "unrelated" / "2")}]}}))
    write(config / "plugins" / "known_marketplaces.json", json.dumps({"demo-market": {
        "installLocation": str(config / "plugins" / "marketplaces" / "demo-market"), "autoUpdate": True}}))
    write(config / "plugins" / "marketplaces" / "demo-market" / "marketplace.json", '{"name": "demo-market"}')
    return config / "plugins"


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() if p.is_file() else None for p in sorted(root.rglob("*"))}


def run(tmp, *args, cwd=None):
    fake = tmp / "claude"
    write(fake, FAKE_CLAUDE, 0o755)
    eval_config(tmp)
    # GIT_INDEX_FILE is what git exports to a hook, so every run here is a run from inside
    # pre-commit: the runner has to keep it away from the fixtures' git.
    env = {**os.environ, "SKILL_EVAL_HOME": str(tmp / "home"), "SKILL_EVAL_CLAUDE": str(fake),
           "CLAUDE_CODE_OAUTH_TOKEN": "fake-token", "GH_TOKEN": "secret-must-not-leak",
           "GIT_INDEX_FILE": ".git/index"}
    return subprocess.run([sys.executable, str(SCRIPT), *args], env=env, cwd=cwd, capture_output=True, text=True)


def first_init(record):
    return next(json.loads(l) for l in open(record["log"]) if '"init"' in l)


def runs(out):
    recs = [json.loads(p.read_text()) for p in (out / "runs").glob("*.json")]
    return {(r["case"], r["run"]): {c["name"]: c for c in r["checks"]} | {"_": r} for r in recs}


def main():
    failures = []

    def expect(ok, what):
        print(("ok    " if ok else "FAIL  ") + what)
        if not ok:
            failures.append(what)

    with tempfile.TemporaryDirectory() as t:
        tmp = pathlib.Path(t)
        src, skill = build(tmp)
        out = tmp / "cand"
        store = snapshot(eval_config(tmp))
        p = run(tmp, "run", str(skill), "--runs", "2", "--concurrency", "4", "--out", str(out))
        expect(p.returncode == 1, f"a suite with failing runs exits 1 (got {p.returncode}: {p.stderr[-400:]})")
        r = runs(out)
        expect(len(r) == 22, f"11 cases x 2 runs recorded (got {len(r)})")
        expect(snapshot(tmp / "home" / "claude-config" / "plugins") == store,
               "a run's writes to its plugin store leave the shared store byte-identical")

        c = r[("creates", 1)]
        expect(c["_"]["passed"], "the passing case passes")
        expect(c["version"]["status"] == "PASS", "the fixture carries the working-tree SKILL.md")
        expect(c["evals_hidden"]["status"] == "PASS", "the fixture has no evals/ for the agent to read")
        expect(c["origin_is_base"]["status"] == "PASS", "origin and the local branch both carry the version under test")
        expect(c["slow_smoke"]["status"] == "SKIP", "slow checks skip unless --slow")
        expect(c["agent_finished"]["status"] == "PASS", "a clean result event is agent_finished")
        expect(c["_"]["metrics"]["model"] == "fake-model", "the model is read from the log")
        expect(c["_"]["effort"] == "medium" and "'--effort', 'medium'" in str(first_init(c["_"])),
               "the agent runs at medium effort by default, and the record says so")
        idle = r[("idle", 1)]["_"]
        expect(idle["effort"] == "high" and "'--effort', 'high'" in str(first_init(idle)),
               "a case's effort: frontmatter sets the agent's effort")
        expect(pathlib.Path(c["_"]["fixture"]).name == "src",
               "the fixture is named after the repo")
        log = pathlib.Path(c["_"]["log"])
        expect(log.is_file() and log.is_relative_to(out) and "feat/x" in log.read_text(),
               "the run's log is kept with its results after the fixture is gone")

        expect(r[("idle", 1)]["worktree"]["status"] == "FAIL", "a missing worktree fails the check")

        leak = r[("leaks", 1)]["source_repo_untouched"]
        expect(leak["status"] == "FAIL" and "leaked-branch" in leak["reason"],
               "a branch the agent made in the real repo fails source_repo_untouched")
        sh("git", "branch", "-D", "leaked-branch", cwd=src)

        heads = subprocess.run(["git", "for-each-ref", "refs/heads"], cwd=src, capture_output=True, text=True).stdout
        expect("pushed-branch" not in heads, "a push from the fixture never reaches the real repo")
        expect(r[("pushes", 1)]["source_repo_untouched"]["status"] == "PASS", "a refused push leaves the real repo untouched")

        iso = r[("isolated", 1)]
        expect(iso["gh_shimmed"]["status"] == "PASS", "gh is shimmed to fail")
        expect(iso["board_shimmed"]["status"] == "PASS", "hoopit-board is shimmed to fail")
        expect(iso["unmocked_recorded"]["status"] == "PASS", "a case without mocks/ still records its calls")
        expect(iso["token_scrubbed"]["status"] == "PASS", "GH_TOKEN never reaches the agent")
        expect(iso["own_config"]["status"] == "PASS", "the agent runs under a config dir of its own run")
        expect(iso["fixture_trusted"]["status"] == "PASS", "that config trusts the run's fixture")
        expect(iso["no_autoupdate"]["status"] == "PASS", "the agent runs with auto-update off")
        ps = r[("plugin-store", 1)]
        for check, what in (("install_path_own", "an installed plugin loads from the run's own copy of the store"),
                            ("dead_path_rerooted", "a path through another run's config is re-rooted in the copy"),
                            ("marketplace_own", "a marketplace reads from the run's own copy"),
                            ("marketplace_frozen", "marketplace auto-update is off in the copy"),
                            ("shared_unnamed", "the run's store never names the shared one")):
            expect(ps[check]["status"] == "PASS", what)
        expect(iso["_"]["metrics"]["masked_exit"] == 1, "a `| tail` without pipefail is counted")

        el = r[("elsewhere", 1)]
        for check, what in (("started_in_cwd", "a case's cwd: starts the agent in that dir under the run dir"),
                            ("eval_cwd", "the scripts see the start dir as EVAL_CWD"),
                            ("checks_in_fixture", "check.sh still runs in the fixture"),
                            ("cwd_trusted", "the run's config trusts the start dir and the fixture"),
                            ("sibling_fixture", "the fixture sits next to the start dir under the repo's name")):
            got = el.get(check, {"status": "missing", "reason": ""})
            expect(got["status"] == "PASS", f"{what} ({got['reason'][:300]})")
        nowhere = r[("cwd-missing", 1)]
        expect(nowhere["setup"]["status"] == "FAIL" and "cwd: nowhere" in nowhere["setup"]["reason"]
               and "agent_finished" not in nowhere, "a cwd: setup never made fails the run without starting the agent")

        m = r[("mocked", 1)]
        for check, what in (("pr_title", "a check grades the title of a mocked `gh pr create`"),
                            ("closes_line", "a call's stdin is recorded for the checks"),
                            ("call_cwd", "a call's cwd is recorded"),
                            ("board_recorded", "hoopit-board calls are recorded"),
                            ("answered", "the matching mock answers the call"),
                            ("unmatched_visible", "an unmatched call fails with `no mock for` in the log"),
                            ("unmocked_tool_fails", "a tool with no mock file fails once the case has mocks/"),
                            ("token_scrubbed", "GH_TOKEN never reaches a mocked call")):
            expect(m[check]["status"] == "PASS", f"{what} ({m[check]['reason'][:300]})")
        expect(pathlib.Path(m["_"]["calls"]).is_file(), "the recorded calls are kept with the results")

        slow = r[("slow", 1)]["agent_finished"]
        expect(slow["status"] == "FAIL" and "timed out" in slow["reason"], "a run past timeout_seconds fails agent_finished")

        bad = r[("bad-setup", 1)]
        expect(bad["setup"]["status"] == "FAIL" and "agent_finished" not in bad,
               "a failing setup.sh fails the run without starting the agent")

        summary = json.loads((out / "summary.json").read_text())
        expect(summary["cases"]["creates"]["checks"]["worktree"] == {"pass": 2, "scored": 2, "reasons": []},
               "the summary counts passes per check")
        expect((summary["repo"], summary["model"], summary["effort"]) == ("src", "fake-model", "high, medium")
               and (summary["cases"]["idle"]["model"], summary["cases"]["idle"]["effort"]) == ("fake-model", "high"),
               f"the summary records the repo, and the model and effort per case (got {summary.get('effort')})")

        # Run from inside the source checkout, as `ab` is: its files must not stand in for the ref's.
        base = tmp / "base"
        p = run(tmp, "run", str(skill), "--ref", "HEAD", "--case", "creates", "--runs", "2", "--out", str(base), cwd=src)
        rb = runs(base)
        expect(rb.get(("creates", 1), {}).get("version", {}).get("status") == "FAIL",
               f"--ref HEAD measures the committed SKILL.md (got {p.stderr[-300:]})")

        p = run(tmp, "compare", str(base), str(out))
        expect("▲ 0/2 → 2/2  version" in p.stdout, f"compare marks a two-run improvement (got:\n{p.stdout})")
        expect(p.returncode == 0, "compare exits 0 when nothing got worse")
        p = run(tmp, "compare", str(out), str(base))
        expect("▼ 2/2 → 0/2  version" in p.stdout and p.returncode == 1, "compare marks a regression and exits 1")
        run(tmp, "run", str(skill), "--effort", "low", "--case", "creates", "--runs", "1", "--out", str(tmp / "low"))
        p = run(tmp, "compare", str(base), str(tmp / "low"))
        expect(p.returncode and "refusing" in p.stderr and "medium" in p.stderr and "low" in p.stderr,
               f"compare refuses two sets whose effort differs (got {p.returncode}: {p.stderr[-300:]})")

        # Run from a git worktree of the source, whose dir carries a branch slug.
        wt = tmp / "GH-1-some-branch"
        sh("git", "worktree", "add", "-q", "-b", "GH-1-some-branch", str(wt), cwd=src)
        wt_skill = wt / skill.relative_to(src)
        write(wt_skill / "SKILL.md", (skill / "SKILL.md").read_text())
        p = run(tmp, "run", str(wt_skill), "--case", "creates", "--runs", "1", cwd=wt)
        rec = [json.loads(f.read_text()) for f in (tmp / "home" / "results").glob("src/demo/*/runs/*.json")]
        expect(len(rec) == 1 and pathlib.Path(rec[0]["fixture"]).name == "src",
               f"a run from a worktree keeps the repo's name for its fixture and results (got {p.stdout[-300:]} {p.stderr[-600:]})")
        sh("git", "worktree", "remove", "--force", str(wt), cwd=src)

        # A branch about to get a PR has committed its edit, so the baseline's base trails HEAD.
        sh("git", "add", "-A", cwd=src)
        sh("git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "edit", cwd=src)
        p = run(tmp, "run", str(skill), "--ref", "HEAD~1", "--base", "HEAD~1", "--case", "creates",
                "--runs", "1", "--out", str(tmp / "committed"), cwd=src)
        got = runs(tmp / "committed").get(("creates", 1), {})
        expect(got.get("version", {}).get("status") == "FAIL" and got.get("agent_finished", {}).get("status") == "PASS",
               f"--ref runs from a branch that commits a skill edit (got {p.stderr[-300:]})")

        product, pskill = build_plugin(tmp)
        pout = tmp / "plugin-cand"
        p = run(tmp, "run", str(pskill), "--fixture", str(product), "--runs", "1", "--out", str(pout))
        pr = runs(pout).get(("loads", 1))
        expect(pr is not None, f"a plugin skill runs in a --fixture checkout (got {p.stdout[-400:]} {p.stderr[-400:]})")
        for check, what in (("plugin_version", "the agent loads the working-tree plugin"),
                            ("plugin_whole", "the whole plugin is staged, not only the skill"),
                            ("plugin_evals_hidden", "every evals/ in the staged plugin is removed"),
                            ("installed_disabled", "--settings disables the installed copy in every marketplace"),
                            ("fixture_is_product", "the fixture is the --fixture checkout"),
                            ("nothing_committed_over", "nothing is committed over the fixture's default branch")):
            got = (pr or {}).get(check, {"status": "missing", "reason": ""})
            expect(got["status"] == "PASS", f"{what} ({got['reason'][:300]})")
        p = run(tmp, "run", str(pskill), "--fixture", str(product), "--ref", "HEAD", "--runs", "1",
                "--out", str(tmp / "plugin-base"))
        got = runs(tmp / "plugin-base").get(("loads", 1), {}).get("plugin_version", {})
        expect(got.get("status") == "FAIL", "--ref HEAD with --fixture loads the committed plugin")

        left = [d for d in (tmp / "home").iterdir() if d.name not in ("results", "claude-config")]
        expect(not left, f"fixtures are removed after the run (left: {left})")

    print(f"\n{len(failures)} failed" if failures else "\nall passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
