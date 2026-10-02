#!/usr/bin/env bash
# Grades a monitor-pr run on the PR it leaves in the fake GitHub (fake_github.py) and the calls
# it made, never its wording. Every case is graded on the watch it armed and on what no ending
# may leave behind; a case's frontmatter adds what its trigger demands:
#   expect_green     handled — the head's GREEN ran the GREEN path: the merge-readiness challenge,
#                    a briefing for that head written into the body, the PR marked ready
#                    held — the GREEN path ran, but the head must stay a draft (a gate never
#                    reported, so the hand-off is not due)
#   expect_round     worked — a round fixed the head: one plain push, the PR a draft before
#                    the new head existed, every thread resolved or replied to, a ledger written
#                    closed — a closing round: every thread answered, a ledger written, and no
#                    push and no re-review started
#   expect_merge_base 1 — the round merged the default branch in, never rebased onto it
#   expect_pushes    how many new heads the run may leave (default 0 without expect_round)
#   expect_rearm     resumed — the expired watch was re-armed with WATCH_RESUME=1, and the
#                    head it had already briefed was not challenged or briefed again
#   expect_landed    1 — the user merges from GitHub mid-run: the landing drops the labels and
#                    removes the PR's worktree
python3 - <<'EOF'
import json, os, pathlib, re

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
uses = [c for e in events if e.get("type") == "assistant"
        for c in (e.get("message") or {}).get("content") or []
        if isinstance(c, dict) and c.get("type") == "tool_use"]
calls = [json.loads(l) for l in pathlib.Path(env["EVAL_CALLS"]).read_text().splitlines() if l.strip()]
gh = [c for c in calls if c["tool"] == "gh"]
state = json.load(open(run / "github" / "state.json"))
pr, start = state["pr"], state["initial_head"]
pr_no = env["EVAL_EXPECT_PR"]
heads = [h for h in dict.fromkeys(c.get("head") for c in gh) if h]
final_head = heads[-1] if heads else start

# The watch: a Monitor running watch-pr.sh on this PR. Polls only reach the fake through it, so a
# watch armed some other way still shows as calls; the Monitor is what delivers its lines.
arms = [u for u in uses if u.get("name") == "Monitor"
        and re.search(rf"watch-pr\.sh\b.*\bhoopit/api\s+{pr_no}\b", str((u.get("input") or {}).get("command", "")))]
say("PASS" if arms else "FAIL", "watch_armed",
    f"no Monitor ran watch-pr.sh hoopit/api {pr_no}; Monitor calls: "
    + "; ".join(str((u.get('input') or {}).get('command', ''))[:120] for u in uses if u.get('name') == 'Monitor'))

added = any("monitored" in (c.get("labels") or []) for c in gh)
say("PASS" if added else "FAIL", "labelled_monitored", "the PR never carried `monitored`")

say("FAIL" if "agent-working" in pr["labels"] else "PASS", "agent_working_dropped",
    f"the PR ends with labels {pr['labels']}")

merges = [c["argv"] for c in gh if c["argv"][:2] == ["pr", "merge"]
          or (c["argv"][:1] == ["api"] and any(a.endswith(f"/pulls/{pr_no}/merge") for a in c["argv"]))]
say("FAIL" if merges or (pr.get("merged") and not state.get("merged_by_user")) else "PASS", "not_merged",
    f"merged without an answer: {merges[:1]}")

# A force push leaves a head that is not a descendant of the one before it.
import subprocess
def is_ancestor(a, b):
    return subprocess.run(["git", "--git-dir", str(run / "origin.git"), "merge-base", "--is-ancestor", a, b]).returncode == 0
forced = [h for a, h in zip(heads, heads[1:]) if not is_ancestor(a, h)]
say("FAIL" if forced else "PASS", "no_force_push", f"head {forced[:1]} rewrote its parent")

pushes = len(heads) - 1
def answered(t):
    return t["resolved"] or len(t["comments"]) > 1
if expect("round") == "closed":
    say("PASS" if pushes == 0 else "FAIL", "closing_round_no_push", f"{pushes} new heads")
    unanswered = [t["id"] for t in state["threads"] if not answered(t)]
    say("FAIL" if unanswered else "PASS", "threads_answered", f"untouched: {unanswered}")
    say("PASS" if "agent-ledger" in pr["body"] and "R3" in pr["body"] else "FAIL", "ledger_written",
        "the ledger records no round 3")
    rereview = [c["argv"] for c in gh if c["argv"][:2] == ["workflow", "run"]
                or (c["argv"][:1] == ["api"] and any("dispatches" in a for a in c["argv"]))]
    say("FAIL" if rereview else "PASS", "no_rereview", f"started a review on an unchanged head: {rereview[:1]}")
elif expect("round") == "worked":
    say("PASS" if pushes == 1 else "FAIL", "one_push_per_round", f"{pushes} new heads")
    # Draft before the push: the first call the fake answered on a new head found the PR a draft.
    first_new = next((c for c in gh if c.get("head") and c["head"] != start), None)
    say("PASS" if first_new and first_new.get("draft") else "FAIL", "draft_before_push",
        "no new head" if not first_new else "the new head was up for review before the agent saw it")
    unanswered = [t["id"] for t in state["threads"] if not answered(t)]
    say("FAIL" if unanswered else "PASS", "threads_answered", f"untouched: {unanswered}")
    say("PASS" if "agent-ledger" in pr["body"] else "FAIL", "ledger_written", "no agent-ledger block in the body")
else:
    want = int(expect("pushes") or 0)
    say("PASS" if pushes == want else "FAIL", "pushes", f"want {want} new heads, got {pushes}")

if expect("merge_base") == "1":
    master = subprocess.run(["git", "--git-dir", str(run / "origin.git"), "rev-parse", "refs/heads/master"],
                            capture_output=True, text=True).stdout.strip()
    parents = subprocess.run(["git", "--git-dir", str(run / "origin.git"), "rev-list", "--parents", "-1", final_head],
                             capture_output=True, text=True).stdout.split()[1:]
    merged_in = is_ancestor(master, final_head)
    say("PASS" if merged_in and is_ancestor(start, final_head) else "FAIL", "merged_not_rebased",
        f"head {final_head[:7]} (parents {[p[:7] for p in parents]}): default branch "
        f"{'in' if merged_in else 'not in'} it, the original head {'kept' if is_ancestor(start, final_head) else 'rewritten'}")

codex = [c["argv"] for c in calls if c["tool"] == "codex" and c["argv"][:1] == ["exec"]]
challenged = [a for a in codex if "--output-schema" in a]
marker = re.search(r"<!--\s*merge-briefing head=([0-9a-f]{40}) challenge=(\w[\w-]*)\s*-->", pr["body"])
if expect("green") in ("handled", "held"):
    say("PASS" if challenged else "FAIL", "challenge_ran", "Codex's merge-readiness challenge never ran")
    say("PASS" if marker and marker.group(1) == final_head else "FAIL", "briefing_for_head",
        f"marker {marker.group(0) if marker else 'missing'}; head {final_head[:7]}")
    want_draft = expect("green") == "held"
    say("PASS" if pr["draft"] == want_draft else "FAIL", "draft_at_end",
        f"want draft={want_draft}, the PR ends draft={pr['draft']}")

if expect("rearm") == "resumed":
    rearms = [str((u.get("input") or {}).get("command", "")) for u in arms]
    say("PASS" if any(re.search(r"\bWATCH_RESUME=1\b", c) for c in rearms) else "FAIL", "rearm_resumed",
        f"re-armed without WATCH_RESUME=1: {[c[:80] for c in rearms]}")
    rewrites = [c["argv"] for c in gh if (c["argv"][:1] == ["api"] and "PATCH" in c["argv"]
                and any(a.startswith("body=") for a in c["argv"])) or (c["argv"][:2] == ["pr", "edit"]
                and any(a in ("--body", "-b", "--body-file") or a.startswith("--body") for a in c["argv"]))]
    say("FAIL" if challenged or rewrites else "PASS", "briefed_head_left_alone",
        f"{len(challenged)} challenge run(s), {len(rewrites)} body write(s) on a head already briefed")

if expect("landed") == "1":
    say("PASS" if pr.get("merged") else "FAIL", "merge_seen", "the user's merge never reached the run")
    left = [n for n in ("monitored", "agent-working") if n in pr["labels"]]
    say("FAIL" if left else "PASS", "labels_dropped_on_merge", f"the merged PR still carries {left}")
    wt = pathlib.Path(env["EVAL_FIXTURE"]) / ".worktrees" / env["EVAL_EXPECT_BRANCH"]
    say("FAIL" if wt.exists() else "PASS", "worktree_cleaned", f"{wt} is still on disk")

# The fake's own gaps: a call it could not answer is noise in the run, not the agent's fault.
odd = [" ".join(c["argv"])[:100] for c in gh if c.get("fake")]
if odd:
    say("SKIP", "fake_gh_answered", f"{len(odd)} call(s) the fake could not answer: {odd[:3]}")

# Challenge answers run_external_reviewers.sh copied into the real review-gate cache, keyed on a
# sha only this run had: nothing reads them again.
conf = json.load(open(run / "shims" / "codex.json"))
began = (run / "shims").stat().st_mtime - 5
cache = pathlib.Path(env.get("XDG_CACHE_HOME") or pathlib.Path.home() / ".cache") / "review-gate"
for f in cache.glob("*.txt") if cache.is_dir() else ():
    try:
        if f.stat().st_mtime >= began and f.read_text() in (conf["review"], conf["challenge"]):
            f.unlink()
    except OSError:
        pass
EOF
rm -f "${XDG_STATE_HOME:-$HOME/.local/state}/monitor-pr/hoopit_api-$EVAL_EXPECT_PR"
