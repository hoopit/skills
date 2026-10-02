"""A stateful `gh` for a monitor-pr eval run: one repo, one open PR. `setup.sh` installs it.

The watch, the round and the GREEN path all read back what they wrote — labels, the body's
ledger and briefing, draft — so static mocks would show the agent a PR that never changes.
This keeps the PR in `$EVAL_RUN_DIR/github/state.json` and answers from it:

- the head is whatever the run's origin (`$EVAL_RUN_DIR/origin.git`) has for the PR branch,
  so a push moves it, and the diff, files and commits come from git;
- checks and statuses are the case's for the head it was set up on, and `new_head_checks` /
  `new_head_statuses` for any head pushed after it;
- review threads resolve, labels come and go, the body and draft change, a merge closes it.

Every call is appended to `EVAL_CALLS` like the runner's shims do, with the head and draft as
they stood when the call was answered, and `"fake": "unhandled"` for a call it cannot answer.
"""
import fcntl, json, os, re, select, shutil, subprocess, sys, time

RUN_DIR = STATE = CALLS = None


def git(*args):
    return subprocess.run(["git", "--git-dir", os.path.join(RUN_DIR, "origin.git"), *args],
                          capture_output=True, text=True).stdout


class Fail(Exception):
    def __init__(self, msg, code=1):
        self.msg, self.code = msg, code


# ---- argv -------------------------------------------------------------------------------

VALUE_FLAGS = {"-X", "--method", "-H", "--header", "-f", "--raw-field", "-F", "--field", "-q", "--jq",
               "-t", "--template", "--input", "-R", "--repo", "--json", "-b", "--body", "--body-file",
               "--add-label", "--remove-label", "-T", "--title", "--color", "--description", "--subject",
               "--head", "-B", "--base", "--cache", "--hostname", "--preview", "-L", "--limit", "--state",
               "--author", "--search", "--ref", "--workflow", "--branch", "--event", "--match-head-commit"}


LIST_FLAGS = {"-H", "-s"}


def parse(argv):
    """Splits argv into positionals and (flag, value) pairs, gh's way: `--flag=value` too."""
    pos, flags, i = [], [], 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--") and "=" in a:
            k, v = a.split("=", 1)
            flags.append((k, v))
        elif (a in VALUE_FLAGS or (a in LIST_FLAGS and argv[:2] == ["pr", "list"])) and i + 1 < len(argv):
            flags.append((a, argv[i + 1]))
            i += 1
        elif a.startswith("-") and a != "-":
            flags.append((a, None))
        else:
            pos.append(a)
        i += 1
    return pos, flags


def flag(flags, *names):
    vals = [v for k, v in flags if k in names]
    return vals[-1] if vals else None


def has(flags, *names):
    return any(k in names for k, _ in flags)


def fields(flags):
    """`-f` / `-F` pairs. `-F` reads `@file` and types numbers and booleans, as gh does."""
    out = {}
    for k, v in flags:
        if k not in ("-f", "--raw-field", "-F", "--field") or v is None or "=" not in v:
            continue
        key, val = v.split("=", 1)
        if k in ("-F", "--field"):
            if val.startswith("@"):
                path = val[1:]
                val = sys.stdin.read() if path == "-" else open(path, errors="replace").read()
            elif re.fullmatch(r"-?\d+", val):
                val = int(val)
            elif val in ("true", "false"):
                val = val == "true"
            elif val == "null":
                val = None
        if key.endswith("[]"):
            out.setdefault(key[:-2], []).append(val)
        else:
            out[key] = val
    return out


# ---- the PR -----------------------------------------------------------------------------

def head_sha(s):
    return git("rev-parse", "--verify", "-q", f"refs/heads/{s['pr']['head_ref']}").strip() or s["initial_head"]


def base_sha(s):
    return git("rev-parse", "--verify", "-q", f"refs/heads/{s['base']}").strip()


def diff(s):
    return git("diff", f"{base_sha(s)}...{head_sha(s)}")


def changed(s):
    out = []
    for line in git("diff", "--numstat", f"{base_sha(s)}...{head_sha(s)}").splitlines():
        add, dele, path = line.split("\t", 2)
        out.append({"filename": path, "status": "modified", "additions": int(add or 0),
                    "deletions": int(dele or 0), "changes": int(add or 0) + int(dele or 0)})
    return out


def commits(s):
    out = []
    for line in git("log", "--reverse", "--format=%H%x09%an%x09%ae%x09%s", f"{base_sha(s)}..{head_sha(s)}").splitlines():
        sha, name, email, subject = line.split("\t", 3)
        out.append({"sha": sha, "commit": {"message": subject, "author": {"name": name, "email": email}}})
    return out


def merged_state(s):
    pr = s["pr"]
    return "MERGED" if pr.get("merged") else ("CLOSED" if pr["state"] == "closed" else "OPEN")


def initial(s):
    return head_sha(s) == s["initial_head"]


def check_runs(s, sha):
    runs = s["checks"] if sha == s["initial_head"] else s.get("new_head_checks", [])
    out = []
    for i, c in enumerate(runs):
        done = c.get("status", "completed") == "completed"
        out.append({"id": 9000 + i, "name": c["name"], "head_sha": sha,
                    "status": c.get("status", "completed"),
                    "conclusion": c.get("conclusion", "success") if done else None,
                    "started_at": c.get("started_at", s["started_at"]),
                    "completed_at": s["started_at"] if done else None,
                    "html_url": f"https://github.com/{s['repo']}/runs/{9000 + i}",
                    "details_url": f"https://github.com/{s['repo']}/runs/{9000 + i}",
                    "output": {"title": c.get("title", ""), "summary": c.get("summary", "")},
                    "app": {"slug": "github-actions"}})
    return out


def statuses(s, sha):
    rows = s["statuses"] if sha == s["initial_head"] else s.get("new_head_statuses", [])
    rows = rows + [st for st in s.get("posted_statuses", []) if st["sha"] == sha]
    return [{"context": st["context"], "state": st["state"], "description": st.get("description", ""),
             "target_url": st.get("target_url", f"https://github.com/{s['repo']}/actions"),
             "updated_at": st.get("updated_at", s["started_at"]), "created_at": s["started_at"]}
            for st in rows]


def combined(sts):
    states = [x["state"] for x in sts]
    return "failure" if {"failure", "error"} & set(states) else ("pending" if "pending" in states or not states else "success")


def review_comments(s):
    out = []
    for t in s["threads"]:
        root = t["comments"][0]["id"]
        for c in t["comments"]:
            out.append({"id": c["id"], "node_id": f"PRRC_{c['id']}", "in_reply_to_id": None if c["id"] == root else root,
                        "user": {"login": c["author"], "type": "Bot" if c["author"].endswith("[bot]") else "User"},
                        "path": t["path"], "line": t.get("line"), "original_line": t.get("line"),
                        "side": "RIGHT", "body": c["body"], "commit_id": s["initial_head"],
                        "original_commit_id": s["initial_head"], "diff_hunk": t.get("diff_hunk", ""),
                        "created_at": c.get("created_at", s["started_at"]), "updated_at": s["started_at"],
                        "html_url": f"https://github.com/{s['repo']}/pull/{s['pr']['number']}#discussion_r{c['id']}",
                        "pull_request_review_id": 7000 + root % 1000})
    return out


def issue_comments(s):
    """`{CURRENT_HEAD}` in a comment reads as the head now: CodeRabbit re-reviews each push."""
    h = head_sha(s)
    return [{**c, "body": c["body"].replace("{CURRENT_HEAD}", h)} for c in s["issue_comments"]]


def review_count(s):
    return sum(len(t["comments"]) for t in s["threads"])


def pr_rest(s):
    pr, h = s["pr"], head_sha(s)
    files = changed(s)
    return {
        "number": pr["number"], "id": 1_000_000 + pr["number"], "node_id": f"PR_kwDOEval{pr['number']}",
        "html_url": f"https://github.com/{s['repo']}/pull/{pr['number']}",
        "url": f"https://api.github.com/repos/{s['repo']}/pulls/{pr['number']}",
        "state": "closed" if pr["state"] == "closed" else "open", "merged": bool(pr.get("merged")),
        "merged_at": pr.get("merged_at"), "draft": pr["draft"], "title": pr["title"], "body": pr["body"],
        "user": {"login": pr.get("author", "ezet"), "type": "User"},
        "labels": [{"name": n} for n in pr["labels"]],
        "head": {"ref": pr["head_ref"], "sha": h, "label": f"{s['repo'].split('/')[0]}:{pr['head_ref']}",
                 "repo": {"full_name": s["repo"], "fork": False}},
        "base": {"ref": s["base"], "sha": base_sha(s),
                 "repo": {"full_name": s["repo"], "default_branch": s["base"], "name": s["repo"].split("/")[1]}},
        "mergeable": False if s.get("conflicting") and initial(s) else (None if pr["state"] == "closed" else True),
        "mergeable_state": "dirty" if s.get("conflicting") and initial(s) else ("draft" if pr["draft"] else "clean"),
        "review_comments": review_count(s), "comments": len(s["issue_comments"]),
        "updated_at": s["updated_at"], "created_at": s["started_at"],
        "additions": sum(f["additions"] for f in files), "deletions": sum(f["deletions"] for f in files),
        "changed_files": len(files), "commits": len(commits(s)),
        "requested_reviewers": [], "requested_teams": [],
        "auto_merge": None, "maintainer_can_modify": True,
    }


def touch(s):
    s["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + s.setdefault("bumps", 0)))
    s["bumps"] += 1


# ---- REST -------------------------------------------------------------------------------

def rest(s, method, path, body, accept):
    repo, prn = s["repo"], s["pr"]["number"]
    path = path.split("?", 1)[0].strip("/")
    path = path.replace("repos/{owner}/{repo}", f"repos/{repo}")
    if not path.startswith(f"repos/{repo}"):
        if path in ("user",):
            return {"login": "ezet", "type": "User"}
        if path == "rate_limit":
            return {"resources": {"core": {"limit": 5000, "remaining": 4900}, "graphql": {"limit": 5000, "remaining": 4900}}}
        raise Fail(f"gh: Not Found (HTTP 404)")
    rest_ = path[len(f"repos/{repo}"):].strip("/")
    parts = rest_.split("/") if rest_ else []
    pr = s["pr"]

    if not parts:
        return {"full_name": repo, "name": repo.split("/")[1], "default_branch": s["base"], "private": True,
                "allow_squash_merge": True, "allow_merge_commit": False, "allow_rebase_merge": False,
                "delete_branch_on_merge": True, "owner": {"login": repo.split("/")[0]}}

    if parts[:2] == ["pulls", str(prn)]:
        sub = parts[2:]
        if not sub:
            if method == "PATCH":
                for k in ("body", "title"):
                    if k in body:
                        pr[k] = body[k]
                if "state" in body:
                    pr["state"] = body["state"]
                touch(s)
                return pr_rest(s)
            if "diff" in (accept or ""):
                return Raw(diff(s))
            return pr_rest(s)
        if sub == ["files"]:
            return changed(s)
        if sub == ["commits"]:
            return commits(s)
        if sub == ["reviews"]:
            if method == "POST":
                return {"id": 8001, "state": body.get("event", "COMMENTED")}
            return s.get("reviews", [])
        if sub == ["requested_reviewers"]:
            return {"users": [], "teams": []}
        if sub == ["comments"]:
            if method == "POST":
                return reply(s, body.get("in_reply_to"), body.get("body", ""))
            return review_comments(s)
        if len(sub) == 3 and sub[0] == "comments" and sub[2] == "replies" and method == "POST":
            return reply(s, int(sub[1]), body.get("body", ""))
        if sub == ["merge"] and method == "PUT":
            return merge(s, body.get("merge_method", "merge"))
    if parts[:2] == ["pulls", "comments"] and len(parts) >= 3:
        cid = int(parts[2])
        if len(parts) == 4 and parts[3] == "replies" and method == "POST":
            return reply(s, cid, body.get("body", ""))
        found = [c for c in review_comments(s) if c["id"] == cid]
        if found:
            return found[0]
    if parts[:2] == ["issues", str(prn)]:
        sub = parts[2:]
        if not sub:
            return {"number": prn, "title": pr["title"], "body": pr["body"], "state": pr["state"],
                    "labels": [{"name": n} for n in pr["labels"]], "pull_request": {"url": pr_rest(s)["url"]}}
        if sub == ["labels"]:
            if method == "POST":
                for n in body.get("labels", []):
                    if n not in pr["labels"]:
                        pr["labels"].append(n)
                touch(s)
            elif method == "DELETE":
                pr["labels"] = []
            return [{"name": n} for n in pr["labels"]]
        if len(sub) == 2 and sub[0] == "labels" and method == "DELETE":
            from urllib.parse import unquote
            name = unquote(sub[1])
            if name not in pr["labels"]:
                raise Fail("gh: Label does not exist (HTTP 404)")
            pr["labels"].remove(name)
            touch(s)
            return [{"name": n} for n in pr["labels"]]
        if sub == ["comments"]:
            if method == "POST":
                c = {"id": 600000 + len(s["issue_comments"]), "user": {"login": "ezet"}, "body": body.get("body", ""),
                     "created_at": s["started_at"]}
                s["issue_comments"].append(c)
                touch(s)
                return c
            return issue_comments(s)
        if sub == ["timeline"] or sub == ["events"]:
            return []
    if parts[:1] == ["issues"] and len(parts) >= 2:
        n = int(parts[1])
        issue = s.get("issues", {}).get(str(n))
        if issue and len(parts) == 2:
            return {"number": n, "state": "open", "labels": [], **issue}
        if issue and parts[2:] == ["comments"]:
            return [] if method == "GET" else {"id": 1}
    if parts[:1] == ["commits"] and len(parts) >= 2:
        sha = resolve(s, parts[1])
        sub = parts[2:]
        if sub == ["check-runs"]:
            runs = check_runs(s, sha)
            return {"total_count": len(runs), "check_runs": runs}
        if sub == ["status"]:
            sts = statuses(s, sha)
            return {"state": combined(sts), "sha": sha, "total_count": len(sts), "statuses": sts}
        if sub == ["statuses"]:
            return statuses(s, sha)
        if sub == ["check-suites"]:
            return {"total_count": 0, "check_suites": []}
        if not sub:
            return {"sha": sha, "commit": {"message": git("log", "-1", "--format=%B", sha)}}
    if parts[:1] == ["statuses"] and len(parts) == 2 and method == "POST":
        s.setdefault("posted_statuses", []).append({"sha": resolve(s, parts[1]), "context": body.get("context", "default"),
                                                    "state": body.get("state", "pending"),
                                                    "description": body.get("description", "")})
        return {"state": body.get("state")}
    if parts[:2] == ["check-runs"] and len(parts) == 2:
        for r in check_runs(s, head_sha(s)) + check_runs(s, s["initial_head"]):
            if str(r["id"]) == parts[1]:
                return r
    if parts[:1] == ["branches"] and len(parts) >= 2:
        name = "/".join(parts[1:])
        if name.endswith("/protection"):
            return {"required_status_checks": {"contexts": s.get("required_checks", [])}}
        return {"name": name, "protected": name == s["base"],
                "commit": {"sha": base_sha(s) if name == s["base"] else head_sha(s)},
                "protection": {"enabled": name == s["base"],
                               "required_status_checks": {"contexts": s.get("required_checks", []) if name == s["base"] else []}}}
    if parts[:2] == ["rules", "branches"]:
        return []
    if parts[:1] == ["labels"]:
        if method == "POST":
            return {"name": body.get("name")}
        return [{"name": n} for n in s.get("repo_labels", [])]
    if parts[:2] == ["actions", "workflows"] and parts[-1] == "dispatches" and method == "POST":
        s.setdefault("dispatches", []).append({"workflow": parts[2], "inputs": body.get("inputs")})
        return Raw("")
    if parts[:2] == ["actions", "runs"] or parts[:2] == ["actions", "workflows"]:
        return {"total_count": 0, "workflow_runs": [], "workflows": []}
    if parts[:2] == ["git", "ref"] or parts[:2] == ["git", "refs"]:
        return {"ref": "refs/" + "/".join(parts[2:]), "object": {"sha": resolve(s, parts[-1])}}
    if parts[:1] == ["compare"]:
        return {"status": "ahead", "ahead_by": len(commits(s)), "behind_by": 0}
    raise Fail("gh: Not Found (HTTP 404)")


def resolve(s, ref):
    if re.fullmatch(r"[0-9a-f]{7,40}", ref):
        return git("rev-parse", "--verify", "-q", ref + "^{commit}").strip() or ref
    return git("rev-parse", "--verify", "-q", f"refs/heads/{ref}").strip() or ref


def reply(s, to, text):
    if to is None:
        raise Fail("gh: Validation Failed (HTTP 422)")
    to = int(to)
    for t in s["threads"]:
        if any(c["id"] == to for c in t["comments"]):
            c = {"id": 500000 + review_count(s), "author": "ezet", "body": text}
            t["comments"].append(c)
            touch(s)
            return [x for x in review_comments(s) if x["id"] == c["id"]][0]
    raise Fail("gh: Not Found (HTTP 404)")


def merge(s, method):
    pr = s["pr"]
    if pr["draft"]:
        raise Fail("GraphQL: Pull Request is still a draft (mergePullRequest)")
    pr.update(state="closed", merged=True, merged_at=s["started_at"], merge_method=method)
    touch(s)
    return {"merged": True, "sha": head_sha(s), "message": "Pull Request successfully merged"}


class Raw(str):
    pass


# ---- GraphQL ----------------------------------------------------------------------------

def thread_node(s, t):
    cs = [{"id": f"PRRC_{c['id']}", "databaseId": c["id"], "body": c["body"], "author": {"login": c["author"]},
           "path": t["path"], "line": t.get("line"), "originalLine": t.get("line"), "createdAt": s["started_at"],
           "url": f"https://github.com/{s['repo']}/pull/{s['pr']['number']}#discussion_r{c['id']}",
           "diffHunk": t.get("diff_hunk", "")} for c in t["comments"]]
    return {"id": t["id"], "isResolved": t["resolved"], "isOutdated": False, "path": t["path"], "line": t.get("line"),
            "originalLine": t.get("line"), "diffSide": "RIGHT", "resolvedBy": {"login": "ezet"} if t["resolved"] else None,
            "comments": {"totalCount": len(cs), "nodes": cs, "pageInfo": {"hasNextPage": False, "endCursor": None}}}


def pr_graph(s):
    pr = s["pr"]
    rest_ = pr_rest(s)
    return {
        "id": rest_["node_id"], "number": pr["number"], "title": pr["title"], "body": pr["body"], "url": rest_["html_url"],
        "state": merged_state(s), "isDraft": pr["draft"], "merged": bool(pr.get("merged")),
        "headRefName": pr["head_ref"], "headRefOid": head_sha(s), "baseRefName": s["base"],
        "mergeable": "CONFLICTING" if rest_["mergeable"] is False else "MERGEABLE",
        "mergeStateStatus": "DIRTY" if rest_["mergeable"] is False else ("DRAFT" if pr["draft"] else "CLEAN"),
        "reviewDecision": None, "author": {"login": pr.get("author", "ezet")},
        "labels": {"nodes": [{"name": n} for n in pr["labels"]]},
        "reviewThreads": {"totalCount": len(s["threads"]), "pageInfo": {"hasNextPage": False, "endCursor": None},
                          "nodes": [thread_node(s, t) for t in s["threads"]]},
        "closingIssuesReferences": {"totalCount": len(s.get("closing_issues", [])),
                                    "nodes": [{"number": n, "title": s.get("issues", {}).get(str(n), {}).get("title", ""),
                                               "url": f"https://github.com/{s['repo']}/issues/{n}",
                                               "repository": {"nameWithOwner": s["repo"], "name": s["repo"].split("/")[1],
                                                              "owner": {"login": s["repo"].split("/")[0]}}}
                                              for n in s.get("closing_issues", [])]},
        "commits": {"totalCount": len(commits(s))},
        "reviews": {"nodes": []}, "reviewRequests": {"nodes": []},
    }


def graphql(s, query, variables):
    q = " ".join(query.split())
    ids = re.findall(r"PRRT_\w+", q) + [v for v in variables.values() if isinstance(v, str) and v.startswith("PRRT_")]
    for verb, val in (("resolveReviewThread", True), ("unresolveReviewThread", False)):
        if verb in q and ids:
            for t in s["threads"]:
                if t["id"] in ids:
                    t["resolved"] = val
                    touch(s)
                    return {"data": {verb: {"thread": {"id": t["id"], "isResolved": val}}}}
            raise Fail(f"GraphQL: Could not resolve to a node with the global id of '{ids[0]}'")
    if "addPullRequestReviewThreadReply" in q and ids:
        body = variables.get("body") or (re.search(r'body:\s*"((?:[^"\\]|\\.)*)"', q) or [None, ""])[1]
        for t in s["threads"]:
            if t["id"] in ids:
                c = reply(s, t["comments"][0]["id"], body)
                return {"data": {"addPullRequestReviewThreadReply": {"comment": {"id": c["node_id"], "databaseId": c["id"]}}}}
    if "markPullRequestReadyForReview" in q:
        s["pr"]["draft"] = False
        touch(s)
        return {"data": {"markPullRequestReadyForReview": {"pullRequest": {"isDraft": False}}}}
    if "convertPullRequestToDraft" in q:
        s["pr"]["draft"] = True
        touch(s)
        return {"data": {"convertPullRequestToDraft": {"pullRequest": {"isDraft": True}}}}
    if "rateLimit" in q and "repository" not in q:
        return {"data": {"rateLimit": {"remaining": 4900, "limit": 5000, "resetAt": s["started_at"]}}}
    if "repository" in q:
        return {"data": {"repository": {"pullRequest": pr_graph(s), "nameWithOwner": s["repo"],
                                        "defaultBranchRef": {"name": s["base"]}}}}
    raise Fail("gh: this eval's GitHub cannot answer that query")


# ---- porcelain --------------------------------------------------------------------------

def pr_json(s, wanted):
    g = pr_graph(s)
    rollup = [{"__typename": "CheckRun", "name": r["name"], "status": r["status"].upper(),
               "conclusion": (r["conclusion"] or "").upper(), "detailsUrl": r["html_url"]} for r in check_runs(s, head_sha(s))] + \
             [{"__typename": "StatusContext", "context": x["context"], "state": x["state"].upper(),
               "targetUrl": x["target_url"]} for x in statuses(s, head_sha(s))]
    full = {**g, "labels": g["labels"]["nodes"], "closingIssuesReferences": g["closingIssuesReferences"]["nodes"],
            "statusCheckRollup": rollup, "comments": [{"author": {"login": c["user"]["login"]}, "body": c["body"]}
                                                      for c in issue_comments(s)],
            "reviews": [], "reviewRequests": [], "files": [{"path": f["filename"], "additions": f["additions"],
                                                            "deletions": f["deletions"]} for f in changed(s)],
            "additions": pr_rest(s)["additions"], "deletions": pr_rest(s)["deletions"],
            "changedFiles": pr_rest(s)["changed_files"], "commits": [{"oid": c["sha"]} for c in commits(s)],
            "baseRefOid": base_sha(s), "isCrossRepository": False, "autoMergeRequest": None,
            "mergedAt": s["pr"].get("merged_at"), "closed": s["pr"]["state"] == "closed",
            "headRepository": {"name": s["repo"].split("/")[1]}, "headRepositoryOwner": {"login": s["repo"].split("/")[0]}}
    return {k: full.get(k) for k in wanted.split(",")} if wanted else full


def bucket(state):
    return {"success": "pass", "pending": "pending", "skipped": "skipping", "neutral": "skipping",
            "cancelled": "cancel"}.get(state, "fail")


def pr_checks_rows(s):
    rows = []
    for r in check_runs(s, head_sha(s)):
        st = "pending" if r["status"] != "completed" else r["conclusion"]
        rows.append({"name": r["name"], "state": (st or "").upper(), "bucket": bucket(st), "link": r["html_url"],
                     "workflow": "", "description": ""})
    for x in statuses(s, head_sha(s)):
        rows.append({"name": x["context"], "state": x["state"].upper(), "bucket": bucket(x["state"]),
                     "link": x["target_url"], "workflow": "", "description": x["description"]})
    return rows


def pr_list(s, flags):
    pr = s["pr"]
    head = flag(flags, "-H", "--head")
    want = (flag(flags, "-s", "--state") or "open").lower()
    st = merged_state(s).lower()
    keep = (head in (None, pr["head_ref"])) and (want == "all" or want == st or (want == "closed" and st == "merged"))
    rows = [pr_json(s, None)] if keep else []
    wanted = flag(flags, "--json")
    if wanted is not None:
        return [{k: r.get(k) for k in wanted.split(",")} for r in rows]
    return Raw("".join(f"{r['number']}\t{r['title']}\t{r['headRefName']}\t{r['state']}\n" for r in rows))


def porcelain(s, cmd, pos, flags):
    pr = s["pr"]
    num = str(pr["number"])
    if cmd == "list":
        return pr_list(s, flags)
    url = f"https://github.com/{s['repo']}/pull/{num}"
    target = next((p for p in pos if p.isdigit() or p.startswith("http") or p == pr["head_ref"]), num)
    if target not in (num, url, pr["head_ref"]) and not target.endswith(f"/pull/{num}"):
        raise Fail(f"GraphQL: Could not resolve to a PullRequest with the number of {target}. (repository.pullRequest)")
    if cmd == "view":
        wanted = flag(flags, "--json")
        if wanted is not None:
            return pr_json(s, wanted)
        if has(flags, "-w", "--web"):
            return Raw("")
        return Raw(f"title:\t{pr['title']}\nstate:\t{merged_state(s)}\ndraft:\t{str(pr['draft']).lower()}\n"
                   f"number:\t{num}\nurl:\t{url}\nlabels:\t{', '.join(pr['labels'])}\n--\n{pr['body']}\n")
    if cmd == "ready":
        if pr["state"] == "closed":
            raise Fail(f"X Pull request {s['repo']}#{num} is closed. Only draft pull requests can be marked as \"ready for review\"")
        undo = has(flags, "--undo")
        if pr["draft"] == undo:
            return Raw(f"! Pull request {s['repo']}#{num} is already {'a draft' if undo else chr(34) + 'ready for review' + chr(34)}\n")
        pr["draft"] = undo
        touch(s)
        return Raw(f"✓ Pull request {s['repo']}#{num} is {'converted to draft' if undo else 'marked as ready for review'}\n")
    if cmd == "merge":
        method = next((m for m in ("squash", "merge", "rebase") if has(flags, f"--{m}", f"-{m[0]}")), None)
        if has(flags, "--auto"):
            pr["auto_merge"] = method
            return Raw(f"✓ Pull request {s['repo']}#{num} will be automatically merged when all requirements are met\n")
        merge(s, method or "merge")
        return Raw(f"✓ {'Squashed and merged' if method == 'squash' else 'Merged'} pull request {s['repo']}#{num} ({pr['title']})\n")
    if cmd == "edit":
        for k, v in flags:
            if k == "--add-label":
                for n in v.split(","):
                    if n and n not in pr["labels"]:
                        pr["labels"].append(n)
            elif k == "--remove-label":
                pr["labels"] = [n for n in pr["labels"] if n not in v.split(",")]
            elif k in ("-b", "--body"):
                pr["body"] = v
            elif k == "--body-file":
                pr["body"] = sys.stdin.read() if v == "-" else open(v, errors="replace").read()
            elif k in ("-t", "--title"):
                pr["title"] = v
        touch(s)
        return Raw(url + "\n")
    if cmd == "checks":
        rows = pr_checks_rows(s)
        wanted = flag(flags, "--json")
        if wanted is not None:
            return [{k: r.get(k) for k in wanted.split(",")} for r in rows]
        text = "".join(f"{r['name']}\t{r['bucket']}\t0\t{r['link']}\t\n" for r in rows)
        code = 8 if any(r["bucket"] == "pending" for r in rows) else (1 if any(r["bucket"] == "fail" for r in rows) else 0)
        if code:
            raise RawExit(text, code)
        return Raw(text)
    if cmd == "diff":
        if has(flags, "--name-only"):
            return Raw("".join(f["filename"] + "\n" for f in changed(s)))
        return Raw(diff(s))
    if cmd == "comment":
        text = flag(flags, "-b", "--body") or ""
        if flag(flags, "--body-file"):
            text = open(flag(flags, "--body-file"), errors="replace").read()
        s["issue_comments"].append({"id": 600000 + len(s["issue_comments"]), "user": {"login": "ezet"}, "body": text})
        touch(s)
        return Raw(url + "#issuecomment-1\n")
    if cmd == "close":
        pr["state"] = "closed"
        touch(s)
        return Raw(f"✓ Closed pull request {s['repo']}#{num}\n")
    raise Fail(f"gh pr {cmd}: unsupported in this eval")


class RawExit(Exception):
    def __init__(self, text, code):
        self.text, self.code = text, code


# ---- output -----------------------------------------------------------------------------

def emit(data, jq, paginate_slurp=False):
    if isinstance(data, Raw):
        sys.stdout.write(data)
        return 0
    if paginate_slurp:
        data = [data]
    text = json.dumps(data)
    if jq:
        p = subprocess.run(["jq", "-r", "-c", jq], input=text, capture_output=True, text=True)
        sys.stdout.write(p.stdout)
        if p.returncode:
            sys.stderr.write(p.stderr)
        return p.returncode
    sys.stdout.write(text + "\n")
    return 0


def run(s, argv, stdin):
    if not argv:
        raise Fail("gh: no command")
    pos, flags = parse(argv)
    jq = flag(flags, "-q", "--jq")
    if s["pr"].get("repo_flag_must_match", True):
        r = flag(flags, "-R", "--repo")
        if r and r.replace("https://github.com/", "") != s["repo"]:
            raise Fail(f"GraphQL: Could not resolve to a Repository with the name '{r}'. (repository)")
    cmd = pos[0]
    # The watch's poll is the one read whose jq builds the review marker. A case can have the
    # user merge the PR from GitHub after so many of them.
    if cmd == "api" and "review_comments | tostring" in (jq or ""):
        s["watch_polls"] = s.get("watch_polls", 0) + 1
        after = s.get("merge_after_polls")
        if after and s["watch_polls"] > after and s["pr"]["state"] == "open":
            s["pr"].update(draft=False)
            merge(s, "squash")
            s["merged_by_user"] = True
    if cmd == "api":
        path = pos[1] if len(pos) > 1 else ""
        body = fields(flags)
        inp = flag(flags, "--input")
        if inp:
            raw = stdin if inp == "-" else open(inp, errors="replace").read()
            try:
                body.update(json.loads(raw or "{}"))
            except ValueError:
                pass
        method = (flag(flags, "-X", "--method") or ("POST" if body and path != "graphql" else "GET")).upper()
        accept = " ".join(v for k, v in flags if k in ("-H", "--header") and v and v.lower().startswith("accept"))
        if path == "graphql":
            query = body.pop("query", "")
            data = graphql(s, query, body)
        else:
            data = rest(s, method, path, body, accept)
        if has(flags, "--silent"):
            return 0
        return emit(data, jq, has(flags, "--slurp"))
    if cmd == "pr" and len(pos) > 1:
        return emit(porcelain(s, pos[1], pos[2:], flags), jq)
    if cmd == "label":
        sub = pos[1] if len(pos) > 1 else ""
        if sub == "create":
            name = pos[2]
            if name in s.setdefault("repo_labels", []) and not has(flags, "-f", "--force"):
                raise Fail(f"label with name \"{name}\" already exists; use `--force` to update its color and description")
            if name not in s["repo_labels"]:
                s["repo_labels"].append(name)
            return emit(Raw(f"✓ Label \"{name}\" created in {s['repo']}\n"), None)
        if sub == "list":
            return emit(Raw("".join(f"{n}\t\t#ededed\n" for n in s.get("repo_labels", []))), None)
    if cmd == "workflow" and pos[1:2] == ["run"]:
        s.setdefault("dispatches", []).append({"workflow": pos[2] if len(pos) > 2 else None, "fields": fields(flags)})
        return emit(Raw(f"✓ Created workflow_dispatch event for {pos[2] if len(pos) > 2 else ''} at {s['pr']['head_ref']}\n"), None)
    if cmd == "repo" and pos[1:2] == ["view"]:
        wanted = flag(flags, "--json")
        data = {"nameWithOwner": s["repo"], "name": s["repo"].split("/")[1], "owner": {"login": s["repo"].split("/")[0]},
                "defaultBranchRef": {"name": s["base"]}, "url": f"https://github.com/{s['repo']}"}
        return emit({k: data.get(k) for k in wanted.split(",")} if wanted else Raw(s["repo"] + "\n"), jq)
    if cmd == "auth":
        return emit(Raw("github.com\n  ✓ Logged in to github.com account ezet (keyring)\n"), None)
    if cmd == "run" and pos[1:2] == ["list"]:
        return emit([] if flag(flags, "--json") is not None else Raw(""), jq)
    if cmd == "issue" and pos[1:2] == ["view"] and len(pos) > 2:
        n = pos[2].rstrip("/").split("/")[-1]
        issue = s.get("issues", {}).get(n)
        if issue:
            wanted = flag(flags, "--json")
            data = {"number": int(n), "state": "OPEN", "labels": [], **issue}
            return emit({k: data.get(k) for k in wanted.split(",")} if wanted else Raw(f"title:\t{issue.get('title')}\n--\n{issue.get('body', '')}\n"), jq)
    raise Fail(f"gh: unsupported in this eval: {' '.join(argv)}")


def main(run_dir, calls):
    global RUN_DIR, STATE, CALLS
    RUN_DIR, CALLS = run_dir, calls
    STATE = os.path.join(run_dir, "github", "state.json")
    argv = sys.argv[1:]
    stdin = None
    if not sys.stdin.isatty() and select.select([sys.stdin], [], [], 0.2)[0]:
        stdin = sys.stdin.read()
        sys.stdin = __import__("io").StringIO(stdin)
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE + ".lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        s = json.load(open(STATE))
        record = {"tool": "gh", "argv": argv, "stdin": (stdin or "")[:4000] or None, "cwd": os.getcwd(),
                  "t": round(time.time(), 2)}
        code, err = 0, None
        try:
            code = run(s, argv, stdin)
        except Fail as f:
            code, err = f.code, f.msg
            if "unsupported" in f.msg or "cannot answer" in f.msg or "Not Found" in f.msg:
                record["fake"] = "unhandled"
        except RawExit as r:
            sys.stdout.write(r.text)
            code = r.code
        except Exception as e:  # a bug here must read as a failed call, not hang the watch
            code, err = 1, f"gh: eval fake crashed: {type(e).__name__}: {e}"
            record["fake"] = "crashed"
        record.update(head=head_sha(s), draft=s["pr"]["draft"], labels=list(s["pr"]["labels"]),
                      state=merged_state(s), exit=code)
        tmp = STATE + ".tmp"
        json.dump(s, open(tmp, "w"), indent=1)
        os.replace(tmp, STATE)
        with open(CALLS, "a") as fh:
            fh.write(json.dumps(record) + "\n")
    if err:
        sys.stderr.write(err.rstrip("\n") + "\n")
    sys.exit(code)

