"""The checks `check.sh` runs. A case's frontmatter sets what applies:

    expect_mode        standalone | caller: who owns the label, the push and the re-review
    expect_fixed       1 when the planted defect must be gone from the branch
    expect_push        1 when the fix must reach origin, 0 when the branch there must not move
    expect_commits     0 when the round commits nothing, 1 when it commits
    expect_workflow    1 when the round must start the Codex re-review (a standalone round that
                       pushed nothing), 0 when it must not (one that pushed, or a caller-owned one)
    expect_dismissed   review ids that must end dismissed
    expect_dismissal   regex the dismissal message must match, or `commit`: it names a commit
                       this round made, by a sha of 7 or more characters
    expect_kept        review ids that must not be dismissed

Each thread in the case's pr.json carries `want`: `resolved` (replied to and resolved), `open`
(replied to and left unresolved) or `untouched` (an earlier round's thread: neither replied to
nor resolved again).
"""
import ast, json, os, re, subprocess

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

def calls_root(node):
    return any(isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "get_root" for n in ast.walk(node))


def is_pk(v):
    return isinstance(v, ast.Attribute) and v.attr in ("pk", "id")


def roots(fn):
    """The names `fn` binds to the root group, and the names it binds to the root's pk."""
    groups, pks = set(), set()
    for n in ast.walk(fn):
        if isinstance(n, (ast.Assign, ast.AnnAssign)) and n.value is not None and calls_root(n.value):
            targets = n.targets if isinstance(n, ast.Assign) else [n.target]
            (pks if is_pk(n.value) else groups).update(t.id for t in targets if isinstance(t, ast.Name))
    return groups, pks


def unfixed(rev):
    """Why `_is_org_admin` at `rev` is still wrong, or None: every `pk=` or `id=` it filters on
    must be the root's, the `.pk` or `.id` of a `get_root()` call or of a name bound to one,
    or a name bound to that pk."""
    try:
        tree = ast.parse(git("show", f"{rev}:{path}"))
    except SyntaxError as e:
        return f"{path} does not parse: {e}"
    fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_is_org_admin"), None)
    if fn is None:
        return f"{path} has no _is_org_admin"
    groups, root_pks = roots(fn)
    pks = [k.value for n in ast.walk(fn) if isinstance(n, ast.Call) for k in n.keywords if k.arg in ("pk", "id")]
    def is_root(v):
        if isinstance(v, ast.Name):
            return v.id in root_pks
        return is_pk(v) and (calls_root(v.value) or (isinstance(v.value, ast.Name) and v.value.id in groups))
    if not pks:
        return "_is_org_admin filters on no pk"
    wrong = [ast.unparse(v) for v in pks if not is_root(v)]
    return f"_is_org_admin filters on {', '.join(wrong)}, not the root's pk" if wrong else None

if expect("fixed") == "1":
    why = unfixed("HEAD")
    say(not why, "defect_fixed", f"at HEAD: {why}")

if expect("push") == "1":
    why = "origin's branch never moved" if origin == pr_head else unfixed(origin)
    say(not why, "fix_pushed", f"on origin: {why}")
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
want_dismissed = {int(x) for x in (expect("dismissed") or "").split()}
if want_dismissed:
    say(want_dismissed <= dismissed, "coderabbit_dismissed", f"not dismissed: {sorted(want_dismissed - dismissed)}")
if expect("dismissal"):
    msgs = [d["message"] for d in s["dismissals"] if d["review"] in want_dismissed]
    if expect("dismissal") == "commit":
        made = git("rev-list", f"{pr_head}..HEAD").split()
        names = lambda m: any(made_sha.startswith(w.lower()) for w in re.findall(r"\b[0-9a-fA-F]{7,40}\b", m)
                              for made_sha in made)
        say(msgs and all(names(m) for m in msgs), "dismissal_says_why",
            f"messages {msgs} name none of this round's commits {[c[:8] for c in made]}")
    else:
        say(msgs and all(re.search(expect("dismissal"), m, re.I) for m in msgs), "dismissal_says_why",
            f"messages {msgs} do not match /{expect('dismissal')}/")
kept = {int(x) for x in (expect("kept") or "").split()}
if kept:
    say(not kept & dismissed, "human_review_kept", f"dismissed a human's review: {sorted(kept & dismissed)}")
say(dismissed <= want_dismissed, "no_other_dismissal", f"dismissed {sorted(dismissed - want_dismissed)}")

if standalone:
    say("+agent-working" in s["label_ops"] and "agent-working" not in s["labels"], "label_cleared",
        f"label ops {s['label_ops']}, labels at the end {s['labels']}")
else:
    say(not s["label_ops"], "labels_left_to_caller", f"label ops {s['label_ops']}")

say(not s["draft_ops"], "draft_state_untouched", f"draft ops {s['draft_ops']}")
creates = [c for c in calls if c["argv"][:2] == ["pr", "create"]]
say(not creates, "no_pr_created", f"{len(creates)} pr create call(s)")
