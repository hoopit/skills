"""A stateful stand-in for GitHub behind the run's `gh`, for one PR; `setup.sh` installs it.

    python3 github.py init <pr.json> <state.json> <file>   resolve each comment's anchor to a line
    gh ...                                                  every other call, through the gh shim

The PR's threads, comments and reviews come from the case's `pr.json`. Reads answer from
the state as it stands, so a reply or a resolve shows in the next read, the way GitHub
would; writes land in the state for `check.py` to grade. Pagination follows GitHub's: a
GraphQL connection holds at most `first` nodes (100 at most), a REST list `per_page` (30 by
default, 100 at most), and only `--paginate` walks past the first page.

Every call is recorded in `EVAL_CALLS`. A call this file does not know fails with
`no mock for: <argv>`, as the runner's own shim does.
"""
import json, os, re, subprocess, sys
from urllib.parse import parse_qs, urlsplit, unquote

BOTS = {"coderabbitai[bot]", "chatgpt-codex-connector[bot]", "github-actions[bot]"}


# ---- state --------------------------------------------------------------------------

def init(pr_path, state_path, path_file):
    pr = json.load(open(pr_path))
    lines = open(path_file).read().splitlines()
    comments, threads = [], []
    for t in pr["threads"]:
        threads.append({"id": t["id"], "isResolved": t.get("resolved", False), "want": t.get("want")})
        for c in t["comments"]:
            line = c.get("line")
            if "anchor" in c:
                line = next(i for i, l in enumerate(lines, 1) if re.search(c["anchor"], l))
            comments.append({"id": c["id"], "in_reply_to_id": c.get("in_reply_to_id"), "user": c["user"],
                             "path": c.get("path", pr["path"]), "line": line, "body": c["body"],
                             "thread": t["id"], "created_at": c.get("created_at", "2026-10-10T09:00:00Z")})
    # Earlier rounds' threads, all resolved: the bulk a busy PR carries.
    for i in range(pr.get("filler_resolved", 0)):
        tid, cid = f"PRRT_kwDOFILL{i:04d}", 2_300_000_000 + i
        threads.insert(i, {"id": tid, "isResolved": True, "want": "untouched"})
        comments.insert(i, {"id": cid, "in_reply_to_id": None, "user": "coderabbitai[bot]", "path": pr["path"],
                            "line": 1 + i % len(lines), "body": f"_🧹 Nitpick_\n\nRound-{1 + i // 40} nit #{i}: tighten the wording here.",
                            "thread": tid, "created_at": "2026-10-01T09:00:00Z"})
    json.dump({**{k: v for k, v in pr.items() if k not in ("threads", "filler_resolved")},
               "threads": threads, "comments": comments, "labels": list(pr.get("labels", [])),
               "replies": [], "resolves": [], "dismissals": [], "workflow_runs": [],
               "label_ops": [], "draft_ops": [], "issue_comments": []},
              open(state_path, "w"), indent=1)


class State:
    def __init__(self, path):
        self.path = path
        self.d = json.load(open(path))

    def save(self):
        json.dump(self.d, open(self.path, "w"), indent=1)

    def root_of(self, comment_id):
        c = next((c for c in self.d["comments"] if c["id"] == comment_id), None)
        return c and next((r for r in self.d["comments"] if r["id"] == (c["in_reply_to_id"] or c["id"])), None)

    def reply(self, root_id, body, via):
        root = self.root_of(root_id)
        if not root:
            return None
        new = {"id": max(c["id"] for c in self.d["comments"]) + 1, "in_reply_to_id": root["id"],
               "user": "kate-bot", "path": root["path"], "line": root["line"], "body": body,
               "thread": root["thread"], "created_at": "2026-10-12T10:00:00Z"}
        self.d["comments"].append(new)
        self.d["replies"].append({"thread": root["thread"], "root": root["id"], "body": body, "via": via})
        return new


# ---- shapes ---------------------------------------------------------------------------

def rest_comment(c, s):
    return {"id": c["id"], "node_id": f"PRRC_{c['id']}", "in_reply_to_id": c["in_reply_to_id"],
            "pull_request_review_id": 4_000_000_000 + c["id"] % 1000,
            "user": {"login": c["user"], "type": "Bot" if c["user"] in BOTS else "User"},
            "path": c["path"], "line": c["line"], "original_line": c["line"], "side": "RIGHT",
            "body": c["body"], "diff_hunk": "@@ (omitted) @@", "created_at": c["created_at"],
            "updated_at": c["created_at"], "commit_id": s.d.get("head_sha", ""),
            "html_url": f"{pr_url(s)}#discussion_r{c['id']}",
            "url": f"https://api.github.com/repos/{s.d['repo']}/pulls/comments/{c['id']}"}


def rest_review(r, s):
    return {"id": r["id"], "node_id": f"PRR_{r['id']}", "user": {"login": r["user"], "type": "Bot" if r["user"] in BOTS else "User"},
            "state": r["state"], "body": r.get("body", ""), "submitted_at": r.get("submitted_at", "2026-10-10T09:00:00Z"),
            "commit_id": s.d.get("head_sha", ""), "html_url": f"{pr_url(s)}#pullrequestreview-{r['id']}"}


def pr_url(s):
    return f"https://github.com/{s.d['repo']}/pull/{s.d['number']}"


def rest_pr(s):
    owner, name = s.d["repo"].split("/")
    head = git("rev-parse", f"origin/{s.d['head_ref']}") or s.d.get("head_sha", "")
    return {"number": s.d["number"], "html_url": pr_url(s), "url": f"https://api.github.com/repos/{s.d['repo']}/pulls/{s.d['number']}",
            "state": "open", "draft": s.d.get("draft", False), "title": s.d["title"], "body": s.d.get("body", ""),
            "user": {"login": s.d.get("author", "kate-zublenko")},
            "head": {"ref": s.d["head_ref"], "sha": head, "repo": {"full_name": s.d["repo"]}},
            "base": {"ref": s.d.get("base_ref", "master"), "repo": {"full_name": s.d["repo"], "name": name, "owner": {"login": owner}}},
            "labels": [{"name": l} for l in s.d["labels"]], "mergeable": True, "mergeable_state": "blocked"}


def git(*args):
    p = subprocess.run(["git", *args], capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else ""


def diff(s):
    base = s.d.get("base_ref", "master")
    return subprocess.run(["git", "diff", f"origin/{base}...origin/{s.d['head_ref']}"], capture_output=True, text=True).stdout


# ---- GraphQL --------------------------------------------------------------------------

def graphql(s, fields, query, paginate, slurp):
    vars_ = {k: v for k, v in fields.items() if k != "query"}
    if re.search(r"\bmutation\b", query):
        return mutation(s, query, vars_)
    if "reviewThreads" not in query and "pullRequest" not in query:
        return None
    pages, after = [], vars_.get("endCursor")
    while True:
        page, nxt = pull_request(s, query, vars_, after)
        pages.append(page)
        if not (paginate and "$endCursor" in query and nxt):
            break
        after = nxt
    return pages


def first_of(query, conn, vars_, default=None):
    m = re.search(conn + r"\s*\(([^)]*)\)", query)
    if not m:
        return default
    f = re.search(r"first:\s*(\$?\w+)", m.group(1))
    if not f:
        return default
    v = f.group(1)
    return int(vars_.get(v[1:], 100)) if v.startswith("$") else int(v)


def literal_after(query, conn, vars_, after):
    m = re.search(conn + r"\s*\(([^)]*)\)", query)
    a = m and re.search(r"after:\s*(\"[^\"]*\"|\$\w+|null)", m.group(1))
    if not a:
        return None
    v = a.group(1)
    if v == "null":
        return None
    return after if v == "$endCursor" else (vars_.get(v[1:]) if v.startswith("$") else v.strip('"'))


def pull_request(s, query, vars_, after):
    n = min(first_of(query, "reviewThreads", vars_, 100), 100)
    cursor = literal_after(query, "reviewThreads", vars_, after)
    start = int(cursor) if cursor else 0
    threads = s.d["threads"][start:start + n]
    k = first_of(query, r"comments", vars_, 100)
    nodes = []
    for t in threads:
        cs = [c for c in s.d["comments"] if c["thread"] == t["id"]]
        first = cs[0]
        nodes.append({"id": t["id"], "isResolved": t["isResolved"], "isOutdated": False, "isCollapsed": t["isResolved"],
                      "path": first["path"], "line": first["line"], "originalLine": first["line"],
                      "resolvedBy": {"login": "kate-zublenko"} if t["isResolved"] else None,
                      "comments": {"totalCount": len(cs), "nodes": [
                          {"id": f"PRRC_{c['id']}", "databaseId": c["id"], "body": c["body"], "path": c["path"],
                           "line": c["line"], "originalLine": c["line"], "author": {"login": c["user"]},
                           "url": f"{pr_url(s)}#discussion_r{c['id']}", "createdAt": c["created_at"],
                           "replyTo": {"databaseId": c["in_reply_to_id"]} if c["in_reply_to_id"] else None}
                          for c in cs[:k]]}})
    end = start + len(threads)
    has_next = end < len(s.d["threads"])
    pr = {"number": s.d["number"], "url": pr_url(s), "title": s.d["title"], "isDraft": s.d.get("draft", False),
          "headRefName": s.d["head_ref"], "baseRefName": s.d.get("base_ref", "master"), "state": "OPEN",
          "reviewDecision": "CHANGES_REQUESTED" if any(r["state"] == "CHANGES_REQUESTED" for r in s.d["reviews"]) else "REVIEW_REQUIRED",
          "reviewThreads": {"totalCount": len(s.d["threads"]), "nodes": threads and nodes,
                            "pageInfo": {"hasNextPage": has_next, "endCursor": str(end) if threads else None}},
          "reviews": {"nodes": [{"id": f"PRR_{r['id']}", "databaseId": r["id"], "state": r["state"],
                                 "author": {"login": r["user"]}, "body": r.get("body", "")} for r in s.d["reviews"]]}}
    return {"data": {"repository": {"pullRequest": pr}}}, (str(end) if has_next else None)


def mutation(s, query, vars_):
    def arg(name):
        m = re.search(name + r"\s*:\s*(\"[^\"]*\"|\$\w+|\d+)", query)
        if not m:
            return vars_.get(name)
        v = m.group(1)
        return vars_.get(v[1:]) if v.startswith("$") else v.strip('"')
    out = {}
    for op in re.findall(r"(\w+)\s*\(\s*input\s*:", query):
        if op in ("resolveReviewThread", "unresolveReviewThread"):
            tid = arg("threadId")
            t = next((t for t in s.d["threads"] if t["id"] == tid), None)
            if not t:
                return error(f"Could not resolve to a node with the global id of '{tid}'")
            t["isResolved"] = op == "resolveReviewThread"
            s.d["resolves"].append({"thread": tid, "op": op})
            out[op] = {"thread": {"id": tid, "isResolved": t["isResolved"]}}
        elif op == "addPullRequestReviewThreadReply":
            tid = arg("pullRequestReviewThreadId")
            root = next((c for c in s.d["comments"] if c["thread"] == tid), None)
            if not root:
                return error(f"Could not resolve to a node with the global id of '{tid}'")
            new = s.reply(root["id"], arg("body") or "", "graphql")
            out[op] = {"comment": {"id": f"PRRC_{new['id']}", "databaseId": new["id"]}}
        elif op == "dismissPullRequestReview":
            rid = str(arg("pullRequestReviewId") or "")
            r = next((r for r in s.d["reviews"] if f"PRR_{r['id']}" == rid or str(r["id"]) == rid), None)
            if not r:
                return error(f"Could not resolve to a node with the global id of '{rid}'")
            dismiss(s, r, arg("message") or "")
            out[op] = {"pullRequestReview": {"state": "DISMISSED"}}
        elif op in ("convertPullRequestToDraft", "markPullRequestReadyForReview"):
            s.d["draft"] = op == "convertPullRequestToDraft"
            s.d["draft_ops"].append(op)
            out[op] = {"pullRequest": {"isDraft": s.d["draft"]}}
        else:
            return None
    return [{"data": out}]


def error(msg):
    return [{"errors": [{"type": "NOT_FOUND", "message": msg}]}]


def dismiss(s, review, message):
    s.d["dismissals"].append({"review": review["id"], "user": review["user"], "message": message})
    review["state"] = "DISMISSED"


# ---- REST -----------------------------------------------------------------------------

def rest(s, method, endpoint, fields, headers, paginate):
    """(pages, status). `pages` is a list of JSON bodies, or a str for a raw body."""
    url = urlsplit(endpoint.lstrip("/"))
    path, qs = url.path, {k: v[-1] for k, v in parse_qs(url.query).items()}
    repo = re.escape(s.d["repo"])
    num = str(s.d["number"])
    m = lambda pat: re.fullmatch(rf"repos/{repo}/{pat}", path)

    if method == "GET" and m(rf"pulls/{num}"):
        if any("diff" in h for h in headers):
            return diff(s), 200
        return [rest_pr(s)], 200
    if method == "GET" and m(rf"pulls/{num}/comments"):
        return paged([rest_comment(c, s) for c in sorted(s.d["comments"], key=lambda c: c["id"])], qs, paginate), 200
    if method == "GET" and (g := m(r"pulls/comments/(\d+)")):
        c = next((c for c in s.d["comments"] if c["id"] == int(g.group(1))), None)
        return ([rest_comment(c, s)], 200) if c else not_found()
    if method == "POST" and m(rf"pulls/{num}/comments") and "in_reply_to" in fields:
        try:
            target = int(fields["in_reply_to"])
        except (TypeError, ValueError):
            return [{"message": "Invalid request.\n\nFor 'properties/in_reply_to', \"%s\" is not an integer." % fields["in_reply_to"],
                     "status": "422"}], 422
        new = s.reply(target, fields.get("body", ""), "rest")
        return ([rest_comment(new, s)], 201) if new else not_found()
    if method == "POST" and (g := m(rf"pulls/{num}/comments/(\d+)/replies")):
        new = s.reply(int(g.group(1)), fields.get("body", ""), "rest")
        return ([rest_comment(new, s)], 201) if new else not_found()
    if method == "GET" and m(rf"pulls/{num}/reviews"):
        return paged([rest_review(r, s) for r in s.d["reviews"]], qs, paginate), 200
    if method == "PUT" and (g := m(rf"pulls/{num}/reviews/(\d+)/dismissals")):
        r = next((r for r in s.d["reviews"] if r["id"] == int(g.group(1))), None)
        if not r:
            return not_found()
        if r["state"] != "CHANGES_REQUESTED":
            return [{"message": "Can not dismiss a review that is not CHANGES_REQUESTED", "status": "422"}], 422
        dismiss(s, r, fields.get("message", ""))
        return [rest_review(r, s)], 200
    if method == "GET" and m(rf"pulls/{num}/(files|commits)"):
        return [[]], 200
    if method == "GET" and m(rf"issues/{num}"):
        return [{"number": s.d["number"], "labels": [{"name": l} for l in s.d["labels"]], "pull_request": {"url": pr_url(s)}}], 200
    if m(rf"issues/{num}/labels"):
        if method == "GET":
            return [[{"name": l} for l in s.d["labels"]]], 200
        names = fields.get("labels", [])
        names = names if isinstance(names, list) else [names]
        for n in names:
            s.d["label_ops"].append("+" + n)
            if n not in s.d["labels"]:
                s.d["labels"].append(n)
        return [[{"name": l} for l in s.d["labels"]]], 200
    if method == "DELETE" and (g := m(rf"issues/{num}/labels/(.+)")):
        n = unquote(g.group(1))
        s.d["label_ops"].append("-" + n)
        if n not in s.d["labels"]:
            return not_found()
        s.d["labels"].remove(n)
        return [[{"name": l} for l in s.d["labels"]]], 200
    if m(rf"issues/{num}/comments"):
        if method == "GET":
            return paged([], qs, paginate), 200
        s.d["issue_comments"].append(fields.get("body", ""))
        return [{"id": 5_000_000_001, "body": fields.get("body", "")}], 201
    if method == "POST" and (g := m(r"actions/workflows/([^/]+)/dispatches")):
        s.d["workflow_runs"].append({"workflow": g.group(1), "inputs": fields.get("inputs", {})})
        return [""], 204
    if method == "GET" and m(rf"commits/[^/]+/(check-runs|status)"):
        return [{"total_count": 0, "check_runs": [], "statuses": [], "state": "pending"}], 200
    return None


def paged(items, qs, paginate):
    per = min(int(qs.get("per_page", 30)), 100)
    page = int(qs.get("page", 1))
    chunks = [items[i:i + per] for i in range(0, len(items), per)] or [[]]
    return chunks[page - 1:] if paginate else [chunks[page - 1] if page <= len(chunks) else []]


def not_found():
    return [{"message": "Not Found", "status": "404"}], 404


# ---- the gh command line --------------------------------------------------------------

VALUED = {"-f", "--raw-field", "-F", "--field", "-X", "--method", "-H", "--header", "-q", "--jq",
          "-t", "--template", "--input", "-p", "--preview", "--hostname", "--cache", "-R", "--repo",
          "--json", "-b", "--body", "--body-file", "--add-label", "--remove-label", "-r", "--ref"}


def parse(argv):
    flags, pos, i = [], [], 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--") and "=" in a:
            name, _, v = a.partition("=")
            flags.append((name, v))
        elif a in VALUED and i + 1 < len(argv):
            flags.append((a, argv[i + 1]))
            i += 1
        elif a.startswith("-") and a != "-":
            flags.append((a, True))
        else:
            pos.append(a)
        i += 1
    return flags, pos


def typed(v):
    if isinstance(v, str) and v.startswith("@"):
        return sys.stdin.read() if v == "@-" else open(v[1:]).read()
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    return {"true": True, "false": False, "null": None}.get(v, v)


def put(fields, key, value):
    if key.endswith("[]"):
        fields.setdefault(key[:-2], []).append(value)
    elif m := re.fullmatch(r"(\w+)\[(\w+)\]", key):
        fields.setdefault(m.group(1), {})[m.group(2)] = value
    else:
        fields[key] = value


def emit(bodies, jq, slurp):
    if isinstance(bodies, str):
        sys.stdout.write(bodies)
        return 0
    if slurp:
        bodies = [bodies]
    for b in bodies:
        if b == "":
            continue
        doc = json.dumps(b)
        if jq:
            p = subprocess.run(["jq", "-r", "-c", jq], input=doc, capture_output=True, text=True)
            sys.stdout.write(p.stdout)
            if p.returncode:
                sys.stderr.write(p.stderr)
                return p.returncode
        else:
            sys.stdout.write(doc + "\n")
    return 0


def api(s, argv):
    flags, pos = parse(argv[1:])
    if not pos:
        return None
    endpoint = pos[0].replace("{owner}/{repo}", s.d["repo"])
    fields, headers, method, jq = {}, [], None, None
    paginate = slurp = silent = False
    for name, v in flags:
        if name in ("-f", "--raw-field"):
            k, _, val = v.partition("=")
            put(fields, k, val)
        elif name in ("-F", "--field"):
            k, _, val = v.partition("=")
            put(fields, k, typed(val))
        elif name == "--input":
            fields.update(json.loads(sys.stdin.read() if v == "-" else open(v).read()))
        elif name in ("-X", "--method"):
            method = v.upper()
        elif name in ("-H", "--header"):
            headers.append(v.lower())
        elif name in ("-q", "--jq"):
            jq = v
        elif name == "--paginate":
            paginate = True
        elif name == "--slurp":
            slurp = True
        elif name == "--silent":
            silent = True
    if endpoint == "graphql":
        bodies = graphql(s, fields, fields.get("query", ""), paginate, slurp)
        if bodies is None:
            return None
        if any("errors" in b for b in bodies):
            sys.stdout.write(json.dumps(bodies[0]) + "\n")
            sys.stderr.write(f"gh: {bodies[0]['errors'][0]['message']}\n")
            return 1
        return 0 if silent else emit(bodies, jq, slurp)
    method = method or ("POST" if fields else "GET")
    got = rest(s, method, endpoint, fields, headers, paginate)
    if got is None:
        return None
    bodies, status = got
    if status >= 400:
        body = bodies[0]
        sys.stdout.write(json.dumps(body) + "\n")
        sys.stderr.write(f"gh: {body['message'].splitlines()[0]} (HTTP {status})\n")
        return 1
    return 0 if silent else emit(bodies, jq, slurp)


def pr_json(s, fields):
    r = rest_pr(s)
    full = {"number": s.d["number"], "url": pr_url(s), "title": s.d["title"], "body": s.d.get("body", ""),
            "state": "OPEN", "isDraft": s.d.get("draft", False), "headRefName": s.d["head_ref"],
            "headRefOid": r["head"]["sha"], "baseRefName": s.d.get("base_ref", "master"),
            "author": {"login": s.d.get("author", "kate-zublenko")}, "labels": [{"name": l} for l in s.d["labels"]],
            "reviewDecision": "CHANGES_REQUESTED" if any(x["state"] == "CHANGES_REQUESTED" for x in s.d["reviews"]) else "REVIEW_REQUIRED",
            "reviews": [{"id": f"PRR_{x['id']}", "author": {"login": x["user"]}, "state": x["state"], "body": x.get("body", "")} for x in s.d["reviews"]],
            "comments": [], "statusCheckRollup": [], "mergeable": "MERGEABLE", "mergeStateStatus": "BLOCKED"}
    return {k: full.get(k) for k in fields.split(",")}


def cli(s, argv):
    flags, pos = parse(argv)
    f = dict(flags)
    if argv[:1] == ["api"]:
        return api(s, argv)
    if pos[:2] == ["pr", "view"]:
        if "--json" in f:
            return emit([pr_json(s, f["--json"])], f.get("--jq") or f.get("-q"), False)
        sys.stdout.write(f"title:\t{s.d['title']}\nstate:\tOPEN\nurl:\t{pr_url(s)}\n\n{s.d.get('body', '')}\n")
        return 0
    if pos[:2] == ["pr", "diff"]:
        sys.stdout.write(diff(s))
        return 0
    if pos[:2] == ["pr", "checks"]:
        sys.stdout.write("no checks reported on the '%s' branch\n" % s.d["head_ref"])
        return 0
    if pos[:2] == ["pr", "ready"]:
        s.d["draft"] = "--undo" in f
        s.d["draft_ops"].append("pr ready --undo" if "--undo" in f else "pr ready")
        return 0
    if pos[:2] == ["pr", "edit"]:
        for name, v in flags:
            for n in v.split(",") if name in ("--add-label", "--remove-label") else ():
                s.d["label_ops"].append(("+" if name == "--add-label" else "-") + n)
                if name == "--add-label" and n not in s.d["labels"]:
                    s.d["labels"].append(n)
                if name == "--remove-label" and n in s.d["labels"]:
                    s.d["labels"].remove(n)
        sys.stdout.write(pr_url(s) + "\n")
        return 0
    if pos[:2] == ["pr", "comment"]:
        s.d["issue_comments"].append(f.get("--body") or f.get("-b") or "")
        return 0
    if pos[:2] == ["workflow", "run"] and len(pos) > 2:
        inputs = dict(v.partition("=")[::2] for n, v in flags if n in ("-f", "--raw-field", "-F", "--field"))
        s.d["workflow_runs"].append({"workflow": pos[2], "inputs": inputs})
        sys.stderr.write(f"✓ Created workflow_dispatch event for {pos[2]} at {s.d['head_ref']}\n")
        return 0
    if pos[:2] in (["run", "list"], ["pr", "list"]):
        sys.stdout.write("[]\n" if "--json" in f else "")
        return 0
    if pos[:2] == ["auth", "status"]:
        sys.stdout.write("github.com\n  ✓ Logged in to github.com account kate-zublenko (keyring)\n")
        return 0
    if pos[:2] == ["repo", "view"]:
        owner, name = s.d["repo"].split("/")
        if "--json" in f:
            return emit([{"nameWithOwner": s.d["repo"], "name": name, "owner": {"login": owner},
                          "defaultBranchRef": {"name": s.d.get("base_ref", "master")}}], f.get("--jq") or f.get("-q"), False)
        sys.stdout.write(s.d["repo"] + "\n")
        return 0
    return None


def main(state_path, calls):
    argv = sys.argv[1:]
    with open(calls, "a") as fh:
        fh.write(json.dumps({"tool": "gh", "argv": argv, "stdin": None, "cwd": os.getcwd()}) + "\n")
    s = State(state_path)
    code = cli(s, argv)
    if code is None:
        sys.exit(f"gh: no mock for: {' '.join(argv)}")
    s.save()
    sys.exit(code)


if __name__ == "__main__" and sys.argv[1:2] == ["init"]:
    init(*sys.argv[2:5])
