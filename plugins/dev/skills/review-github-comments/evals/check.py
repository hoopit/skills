"""The checks `check.sh` runs. A case's frontmatter sets what applies:

    expect_mode        standalone | caller: who owns the label, the push and the re-review
    expect_fixed       1 when the planted defect must be gone from the branch
    expect_push        1 when the fix must reach origin, 0 when the branch there must not move
    expect_commits     0 when the round commits nothing, 1 when it commits
    expect_workflow    1 when the round must start the Codex re-review, 0 when it must not: a
                       round that pushed, a caller-owned one and a closing round never do
    expect_dismissed   review ids that must end dismissed
    expect_dismissal   regex the dismissal message must match
    expect_kept        review ids that must not be dismissed

Each thread in the case's pr.json carries `want`: `resolved` (replied to and resolved), `open`
(replied to and left unresolved) or `untouched` (an earlier round's thread: neither replied to
nor resolved again).
"""
import json, os, re, subprocess

env = os.environ
expect = lambda k: env.get(f"EVAL_EXPECT_{k.upper()}")
def say(ok, name, reason=""):
    print(f"PASS {name}" if ok else f"FAIL {name} {reason}")
def git(*a):
    return subprocess.run(["git", *a], capture_output=True, text=True).stdout.strip()

run = env["EVAL_RUN_DIR"]
s = json.load(open(os.path.join(run, "github.json")))
calls = [json.loads(l) for l in open(env["EVAL_CALLS"]) if l.strip()]
branch, path = s["head_ref"], s["path"]
pr_head = s["head_sha"]
origin = git("--git-dir", os.path.join(run, "origin.git"), "rev-parse", f"refs/heads/{branch}")
standalone = expect("mode") == "standalone"

# Threads: each one this round decides is answered and left as its decision says, and every
# settled one is left alone.
replied = {r["thread"] for r in s["replies"]}
touched = replied | {r["thread"] for r in s["resolves"]}
for want, name in (("resolved", "threads_handled"), ("open", "open_thread_left_open"),
                   ("untouched", "settled_threads_untouched")):
    threads = [t for t in s["threads"] if t["want"] == want]
    if not threads:
        continue
    if want != "untouched":
        bad = [t["id"] for t in threads if t["id"] not in replied or t["isResolved"] != (want == "resolved")]
        say(not bad, name, f"not replied to and {want}: " + ", ".join(
            f"{t} ({'no reply' if t not in replied else 'resolved' if want == 'open' else 'unresolved'})" for t in bad))
    else:
        bad = [t["id"] for t in threads if t["id"] in touched or not t["isResolved"]]
        say(not bad, name, f"{len(bad)} settled thread(s) replied to or resolved again: {', '.join(bad[:3])}")

def fixed(rev):
    """`_is_org_admin` compares against the root, however the fix spells it."""
    src = git("show", f"{rev}:{path}")
    body = re.search(r"def _is_org_admin\b[\s\S]*?(?=\n    def |\Z)", src)
    return bool(body) and "filter(pk=group.pk)" not in body.group() and "get_root()" in body.group()

if expect("fixed") == "1":
    say(fixed("HEAD"), "defect_fixed", f"HEAD's {path} still compares against group.pk")

if expect("push") == "1":
    say(origin != pr_head and fixed(origin), "fix_pushed",
        "origin's branch never moved" if origin == pr_head else "origin's branch lacks the fix")
    say(not git("rev-list", f"{origin}..HEAD"), "nothing_left_unpushed",
        f"{git('rev-list', '--count', f'{origin}..HEAD')} commit(s) on HEAD not on origin")
elif expect("push") == "0":
    say(origin == pr_head, "not_pushed", f"origin's branch moved {pr_head[:8]} → {origin[:8]}")

new = git("rev-list", "--count", f"{pr_head}..HEAD") or "0"
if expect("commits") == "0":
    dirty = git("status", "--porcelain", "--untracked-files=no")
    say(new == "0" and not dirty, "committed_nothing", f"{new} commit(s), tracked changes: {dirty[:120]}")
elif expect("commits") == "1":
    say(new != "0", "committed", "no commit on the PR branch")

runs = [r for r in s["workflow_runs"] if "codex-review" in r["workflow"]]
if expect("workflow") == "1":
    say(any(str(r["inputs"].get("pr")) == str(s["number"]) for r in runs), "rereview_triggered",
        f"codex re-review runs: {runs}")
elif expect("workflow") == "0":
    say(not runs, "no_rereview", f"{len(runs)} codex re-review run(s)")

# Step 5b runs in both modes: a caller-owned round skips 1a, 1b, 5a and the push, not 5b.
dismissed = {d["review"] for d in s["dismissals"]}
want = {int(x) for x in (expect("dismissed") or "").split()}
if want:
    say(want <= dismissed, "coderabbit_dismissed", f"not dismissed: {sorted(want - dismissed)}")
if expect("dismissal"):
    msgs = [d["message"] for d in s["dismissals"] if d["review"] in want]
    say(msgs and all(re.search(expect("dismissal"), m, re.I) for m in msgs), "dismissal_says_why",
        f"messages {msgs} do not match /{expect('dismissal')}/")
kept = {int(x) for x in (expect("kept") or "").split()}
if kept:
    say(not kept & dismissed, "human_review_kept", f"dismissed a human's review: {sorted(kept & dismissed)}")
say(dismissed <= want, "no_other_dismissal", f"dismissed {sorted(dismissed - want)}")

if standalone:
    say("+agent-working" in s["label_ops"] and "agent-working" not in s["labels"], "label_cleared",
        f"label ops {s['label_ops']}, labels at the end {s['labels']}")
else:
    say(not s["label_ops"], "labels_left_to_caller", f"label ops {s['label_ops']}")

say(not s["draft_ops"], "draft_state_untouched", f"draft ops {s['draft_ops']}")
creates = [c for c in calls if c["argv"][:2] == ["pr", "create"]]
say(not creates, "no_pr_created", f"{len(creates)} pr create call(s)")
