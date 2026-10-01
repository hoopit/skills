"""The checks behind check.sh. A case's `expect_*` frontmatter says what it wants:

    expect_branch    regex the pushed branch must match
    expect_title     regex the PR's final title must match
    expect_closes    the issue number the body must close
    expect_draft     1 when the PR must be born a draft, 0 when it must not
    expect_subject   regex every commit subject on the branch must match
    expect_link      text the body must contain, such as the Jira browse URL
    expect_keys      regex for the Jira-shaped keys allowed on the linked surfaces
    expect_followup  1 when the remainder of the issue must be filed as its own issue
"""
import os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pr_state

E = lambda k, d=None: os.environ.get(f"EVAL_EXPECT_{k}", d)
# The Jira projects GitHub-for-Jira acts on in Hoopit: a key of one of them on a linked
# surface moves that ticket.
JIRA_KEY = re.compile(r"(?<![\w/-])((?:BAC|PM|ITSM|WEB|FA)-\d+)\b")


def say(status, name, reason=""):
    print(f"{status} {name} {reason}".rstrip())


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout


run_dir, base = os.environ["EVAL_RUN_DIR"], os.environ["EVAL_BASE"]
push = os.path.join(run_dir, "push.git")
state = pr_state.load(run_dir, os.environ["EVAL_CALLS"])
title, body = state["title"] or "", state["body"]

n = len(state["creates"])
say("PASS" if n == 1 else "FAIL", "pr_created", "" if n == 1 else f"gh pr create ran {n} times")

pushed = [b for b in git("--git-dir", push, "for-each-ref", "--format=%(refname:short)", "refs/heads").split()
          if b != os.environ.get("EVAL_BRANCH", "master")]
branch = pushed[-1] if pushed else ""
if len(pushed) == 1:
    say("PASS", "pushed")
else:
    say("FAIL", "pushed", f"{len(pushed)} branches pushed: {' '.join(pushed)}")

if E("BRANCH"):
    if branch and re.search(E("BRANCH"), branch):
        say("PASS", "branch_name")
    else:
        say("FAIL", "branch_name", f"{branch or 'none'} does not match {E('BRANCH')}")

messages = [m.strip() for m in git("--git-dir", push, "log", "--format=%B%x00", f"{base}..{branch}").split("\0")
            if m.strip()] if branch else []
if E("SUBJECT"):
    bad = [m.splitlines()[0] for m in messages if not re.search(E("SUBJECT"), m.splitlines()[0])]
    if messages and not bad:
        say("PASS", "commit_subject")
    else:
        say("FAIL", "commit_subject", f"{bad[0]!r} does not match {E('SUBJECT')}" if bad else "no commits")

if not n:
    sys.exit(0)

if E("TITLE"):
    if re.search(E("TITLE"), title):
        say("PASS", "title")
    else:
        say("FAIL", "title", f"{title!r} does not match {E('TITLE')}")

if body is None:
    say("FAIL", "body_read", "no body on gh pr create, or a --body-file that was gone when it ran")
    body = ""

if E("CLOSES"):
    want = int(E("CLOSES"))
    if want in pr_state.closing_numbers(body):
        say("PASS", "closes")
    else:
        soft = re.search(rf"(?i)[^\n]{{0,25}}#{want}\b[^\n]{{0,25}}", body)
        say("FAIL", "closes", f"no closing keyword on #{want}" + (f": {soft.group(0)!r}" if soft else ""))
    say("PASS" if state["verified"] else "FAIL", "link_verified",
        "" if state["verified"] else "closingIssuesReferences never read after the PR opened")

if E("LINK"):
    say("PASS" if E("LINK") in body else "FAIL", "work_item_link",
        "" if E("LINK") in body else f"body lacks {E('LINK')}")

allowed = re.compile(E("KEYS", r"(?!)"))
surfaces = {"branch": branch, "commit": "\n".join(messages), "title": title, "body": body}
stray = sorted({f"{k} on the {where}" for where, text in surfaces.items()
                for k in JIRA_KEY.findall(text) if not allowed.fullmatch(k)})
say("FAIL" if stray else "PASS", "keys_allowed", ", ".join(stray))

flags = state["flags"]
if E("DRAFT") is not None:
    draft = "draft" in flags
    want = E("DRAFT") == "1"
    if draft != want:
        say("FAIL", "draft", "opened ready" if want else "opened as a draft")
    elif want and state["ready"]:
        say("FAIL", "draft", "marked ready after opening")
    else:
        say("PASS", "draft")

base_branch = flags.get("base")
if base_branch in (None, E("BASE", "master")):
    say("PASS", "base")
else:
    say("FAIL", "base", f"--base {base_branch}")

wrapped = pr_state.wrapped_lines(body)
say("FAIL" if wrapped else "PASS", "body_unwrapped",
    f"{len(wrapped)} broken paragraph lines, first {wrapped[0]}" if wrapped else "")

local = re.findall(r"(?:/home/|/tmp/|~/)[^\s`'\")]*", body)
say("FAIL" if local else "PASS", "body_paths_openable", ", ".join(local[:3]))

if E("FOLLOWUP") == "1":
    filed = state["issues_created"] > 0
    say("PASS" if filed else "FAIL", "followup_filed", "" if filed else "no gh issue create")
