#!/usr/bin/env bash
# Grades a merge-briefing run on the PR body it leaves in the fake GitHub, the Codex calls it
# made and the CHALLENGE line its contract returns, never its wording. A case's frontmatter sets
# what applies:
#   expect_outcome    briefed — one briefing block at the top of the body, the rest of the body as
#                     it was; held — `HELD:` returned and the body untouched
#   expect_challenge  ran — Codex was called for the challenge on this head, whether or not it
#                     answered; skipped — it must not be called
#   expect_marker     ran | not-run — the `challenge=` the block's marker must carry
#   expect_recommend  merge | hold — the block's recommendation
#   expect_risk       low | moderate | high | very high — the block's Merge risk, where the
#                     skill's table leaves one answer
#   expect_lane       auto | human — the block's Lane line
#   expect_line       regex the returned `CHALLENGE:` line must match
# No case expects `Lane: auto`: it also needs `Merge risk: low`, a judgement the table leaves open
# for any change small enough to be low, so an auto case would grade the agent's taste in risk.
# Every case's change sits on a guarded path, and `human` there is lane-gate.sh's to settle.
python3 - <<'EOF'
import json, os, pathlib, re, subprocess

env = os.environ
def say(status, name, reason=""):
    print(f"{status} {name} {reason if status != 'PASS' else ''}".rstrip())
def expect(key):
    return env.get(f"EVAL_EXPECT_{key.upper()}")

run = pathlib.Path(env["EVAL_RUN_DIR"])
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
bash = [str((u.get("input") or {}).get("command", "")) for u in uses if u.get("name") == "Bash"]
calls = [json.loads(l) for l in pathlib.Path(env["EVAL_CALLS"]).read_text().splitlines() if l.strip()]
gh = [c for c in calls if c["tool"] == "gh"]
challenges = [c for c in calls if c["tool"] == "codex" and c["argv"][:1] == ["exec"] and "--output-schema" in c["argv"]]
state = json.load(open(run / "github" / "state.json"))
pr, head = state["pr"], state["initial_head"]
was = json.load(open(run / "github" / "pr-before.json"))
body, before = pr["body"] or "", was["body"]

START, END = "<!-- agent-merge-briefing:start -->", "<!-- agent-merge-briefing:end -->"
def outside(text):
    """The body with any briefing block cut out, whitespace-normalised at the seams."""
    return re.sub(rf"{re.escape(START)}.*?{re.escape(END)}", "", text, flags=re.S).strip()

outcome = expect("outcome")
if outcome == "held":
    say("PASS" if re.search(r"^[\W_]*HELD:", final, re.M) else "FAIL", "held_returned", "no `HELD:` line in the reply")
    say("PASS" if body == before else "FAIL", "body_untouched", "the body changed on a head the challenge held")
elif outcome == "briefed":
    starts, ends = body.count(START), body.count(END)
    say("PASS" if starts == ends == 1 else "FAIL", "one_block", f"{starts} start and {ends} end markers")
    say("PASS" if body.lstrip().startswith(START) else "FAIL", "block_at_top", f"body opens {body.lstrip()[:60]!r}")
    say("PASS" if outside(body) == outside(before) else "FAIL", "rest_of_body_kept",
        "the description outside the briefing block changed")
    block = body[body.find(START):body.find(END)] if starts else ""
    m = re.search(r"<!--\s*merge-briefing\s+head=(\S+)\s+challenge=(\S+)\s*-->", block)
    if not m:
        say("FAIL", "marker", "no `<!-- merge-briefing head=… challenge=… -->` in the block")
    else:
        bad = [f"head={m.group(1)[:12]}, want {head[:12]}"] if m.group(1) != head else []
        if expect("marker") and m.group(2) != expect("marker"):
            bad.append(f"challenge={m.group(2)}, want {expect('marker')}")
        if not block.split(START, 1)[-1].lstrip().startswith(m.group(0)):
            bad.append("not directly under the start marker")
        say("FAIL" if bad else "PASS", "marker", "; ".join(bad))
    h = re.search(r"^##[^\n]*Merge briefing[^\n]*?([0-9a-f]{7,40})", block, re.M)
    say("PASS" if h and head.startswith(h.group(1)) else "FAIL", "heading_names_head",
        f"heading names {h.group(1) if h else 'no sha'}, head is {head[:7]}")
    # The two ratings the reader sizes the read by, each on one of its fixed values.
    missing = [name for name, values in (("Warranted", "yes|larger than the issues|beyond the issues"),
                                          ("Merge risk", "low|moderate|high|very high"))
               if not re.search(rf"{name}\W+(?:{values})\b", block, re.I)]
    say("FAIL" if missing else "PASS", "ratings_present", f"no rated {' or '.join(missing)} line")
    if expect("risk"):
        r = re.search(r"Merge risk\W+(very high|low|moderate|high)\b", block, re.I)
        got = r.group(1).lower() if r else None
        say("PASS" if got == expect("risk") else "FAIL", "risk", f"want {expect('risk')}, got {got}")
    if expect("recommend"):
        # The recommendation's own line: the Lane line above it can name "a recommendation to merge".
        r = re.findall(r"^[\W_]*Recommend\w*\W+(?:[^\n]*?)\b(merge|hold)", block, re.I | re.M)
        got = r[-1].lower() if r else None
        say("PASS" if got == expect("recommend") else "FAIL", "recommendation", f"want {expect('recommend')}, got {got}")
    if expect("lane"):
        l = re.search(r"Lane\W+(?:[^\n]*?)\b(auto|human)\b", block, re.I)
        got = l.group(1).lower() if l else None
        say("PASS" if got == expect("lane") else "FAIL", "lane", f"want {expect('lane')}, got {got}")
        # lane-gate.sh is the one reader of the PR's files page by page.
        ran = any(c["argv"][:1] == ["api"] and "--paginate" in c["argv"] and any("/files" in a for a in c["argv"]) for c in gh)
        say("PASS" if ran else "FAIL", "lane_gate_ran", "no paginated read of the PR's files, as lane-gate.sh makes")

if expect("challenge") == "ran":
    on_head = [c for c in challenges if c.get("head") == head]
    say("PASS" if on_head else "FAIL", "challenge_ran",
        f"challenged {sorted({(c.get('head') or '?')[:7] for c in challenges})}, never the head {head[:7]}"
        if challenges else "no `codex exec --output-schema` call")
elif expect("challenge") == "skipped":
    say("FAIL" if challenges else "PASS", "challenge_skipped", f"{len(challenges)} challenge call(s) on a skipped head")

if expect("line"):
    lines = re.findall(r"CHALLENGE:\s*[^\n`]*", final)
    ok = any(re.search(expect("line"), l) for l in lines)
    say("PASS" if ok else "FAIL", "challenge_line", f"want /{expect('line')}/, got {lines or 'no CHALLENGE: line'}")

# Briefing is a read and a write to the body: it never merges, pushes, readies, labels, retitles
# or closes.
# The fake records the head at each call; the origin has the last word on a push made after them.
pushed = subprocess.run(["git", "--git-dir", str(run / "origin.git"), "rev-parse", f"refs/heads/{pr['head_ref']}"],
                        capture_output=True, text=True).stdout.strip()
heads = {c.get("head") for c in gh if c.get("head")} | {head, pushed}
merges = [c["argv"] for c in gh if c["argv"][:2] == ["pr", "merge"] or any(a.endswith("/merge") for a in c["argv"])]
bad = ([f"merged: {merges[0]}"] if merges or pr.get("merged") else []) + \
      ([f"{len(heads) - 1} new head(s)"] if len(heads) > 1 else []) + \
      (["readied"] if not pr["draft"] else []) + ([f"labels {pr['labels']}"] if pr["labels"] else []) + \
      [f"{k} {was.get(k)!r} -> {pr.get(k)!r}" for k in ("state", "title") if pr.get(k) != was.get(k)]
say("FAIL" if bad else "PASS", "body_only", "; ".join(bad))

# A checkout the challenge added beside the fixture is removed once it returns.
trees = [l for l in subprocess.run(["git", "worktree", "list", "--porcelain"], capture_output=True, text=True).stdout.splitlines()
         if l.startswith("worktree ")]
say("PASS" if len(trees) == 1 else "FAIL", "checkout_removed", f"left: {trees[1:]}")
EOF
