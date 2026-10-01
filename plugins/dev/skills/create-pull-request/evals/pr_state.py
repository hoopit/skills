"""The PR a run left behind, read from the recorded `gh` calls.

`calls.jsonl` holds every shim call's argv and stdin. A `--body-file` names a file the
agent may delete afterwards, so `gh_wrap.py` copies each one into `gh-bodies.jsonl` as the
call is made; this module reads both and replays `gh pr create` and every later
`gh pr edit` into the title and body GitHub would show.
"""
import json, os, re

CLOSING = re.compile(r"(?i)\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?\s+(?:hoopit/api)?#(\d+)\b")
# A paragraph broken mid-sentence: a long line that does not end a sentence, followed by
# one that starts no Markdown block of its own.
BLOCK = re.compile(r"\s*([-*+]\s|\d+[.)]\s|#|>|\||```|~~~|<|---|===|\[[ xX]\])")


def _calls(path):
    out = []
    try:
        lines = open(path).read().splitlines()
    except OSError:
        return out
    for line in lines:
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out


def _flags(argv):
    """gh's flags as (name, value) pairs; a bare flag gets None."""
    takes = {"-t": "title", "--title": "title", "-b": "body", "--body": "body",
             "-F": "body-file", "--body-file": "body-file", "-B": "base", "--base": "base",
             "-H": "head", "--head": "head", "-l": "label", "--label": "label",
             "--add-label": "add-label", "-R": "repo", "--repo": "repo"}
    bare = {"-d": "draft", "--draft": "draft"}
    pairs, i = [], 0
    while i < len(argv):
        a = argv[i]
        name, _, inline = a.partition("=")
        if name in takes and inline:
            pairs.append((takes[name], inline))
        elif a in takes and i + 1 < len(argv):
            pairs.append((takes[a], argv[i + 1]))
            i += 1
        elif a in bare:
            pairs.append((bare[a], None))
        i += 1
    return pairs


def _body(call, flags, files):
    """The body a create or edit call set, or None when it set none."""
    for name, value in flags:
        if name == "body":
            return value
        if name == "body-file":
            if value == "-":
                return call.get("stdin") or ""
            kept = files.get(json.dumps(call["argv"]))
            return kept.pop(0) if kept else None
    return None


def load(run_dir, calls_path):
    files = {}
    for rec in _calls(os.path.join(run_dir, "gh-bodies.jsonl")):
        files.setdefault(json.dumps(rec["argv"]), []).append(rec["content"])
    state = {"creates": [], "title": None, "body": None, "flags": {}, "verified": False,
             "ready": False, "issues_created": 0, "edits": 0}
    for call in _calls(calls_path):
        if call.get("tool") != "gh":
            continue
        argv = call["argv"]
        line = " ".join(argv)
        flags = _flags(argv)
        if argv[:2] == ["pr", "create"]:
            state["creates"].append(call)
            state["flags"] = {n: v for n, v in flags}
            state["title"] = state["flags"].get("title")
            state["body"] = _body(call, flags, files)
        elif argv[:2] == ["pr", "edit"]:
            title, body = dict(flags).get("title"), _body(call, flags, files)
            if title is not None or body is not None:
                state["edits"] += 1
            state["title"] = title if title is not None else state["title"]
            state["body"] = body if body is not None else state["body"]
        elif argv[:2] == ["pr", "ready"] and "--undo" not in argv:
            state["ready"] = True
        elif argv[:2] == ["issue", "create"]:
            state["issues_created"] += 1
        if state["creates"] and "closingIssuesReferences" in line:
            state["verified"] = True
    return state


def closing_numbers(body):
    return sorted({int(n) for n in CLOSING.findall(body or "")})


def wrapped_lines(body):
    """Where a paragraph of the body was broken mid-sentence, outside code fences."""
    lines = (body or "").replace("\r\n", "\n").split("\n")
    fence, hits = False, []
    for a, b in zip(lines, lines[1:]):
        if re.match(r"\s*(```|~~~)", a):
            fence = not fence
            continue
        if fence or not b.strip() or BLOCK.match(b) or re.match(r"\s*[|#]", a):
            continue
        if len(a.rstrip()) >= 50 and not a.endswith(("  ", "\\")) \
                and re.search(r"[\w,;`)\]*_'\"-]$", a.rstrip()):
            hits.append(f"{a.rstrip()[-30:]!r} / {b.strip()[:20]!r}")
    return hits
