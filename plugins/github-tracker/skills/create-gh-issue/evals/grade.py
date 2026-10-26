#!/usr/bin/env python3
"""Grade one create-gh-issue run from the tracker calls it recorded in EVAL_CALLS.

Every check reads calls, never the agent's wording. A case states what it expects in its
frontmatter, which reaches here as EVAL_EXPECT_<NAME>:

    expect_issues       how many `gh issue create` calls the run should make: `1`, or `1-2`
    expect_types        comma-separated types every created issue may carry
    expect_gate         a PR number a live `Gate: deployed` line must name, or `none`
    expect_status       `backlog`: no created issue is moved to Ready
    expect_no_parent    `1`: no `sub_issues` write
    expect_names        text every created issue's body must contain
    expect_reads        an issue number some gh call must read
    expect_resolve      a Sentry short id the run must resolve with the `sentry` CLI
    expect_effort       comma-separated Efforts the created issue may carry
    expect_proposals    `backlog`: every created issue but the Ops one stays out of Ready
    expect_dropped      a word no created issue's title may contain: the item the change settled
    expect_decision     `1`: an issue goes in as `Needs decision`, its body naming the decision
                        under a `## The decision` heading

setup.sh's gh wrapper answers the first `gh issue create` with #19600 and each later one with
the next number, so a created issue's number is its place among the creates.
"""
import json, os, re

E = {k[len("EVAL_EXPECT_"):].lower(): v for k, v in os.environ.items() if k.startswith("EVAL_EXPECT_")}
calls = []
with open(os.environ["EVAL_CALLS"]) as fh:
    for line in fh:
        try:
            calls.append(json.loads(line))
        except ValueError:
            pass


def out(status, name, reason=""):
    print(f"{status} {name} {reason}".rstrip())


def opt(argv, *names):
    """Every value of a flag, as `--flag v`, `--flag=v` or `-f v`."""
    vals = []
    for i, a in enumerate(argv):
        for n in names:
            if a == n and i + 1 < len(argv):
                vals.append(argv[i + 1])
            elif n.startswith("--") and a.startswith(n + "="):
                vals.append(a[len(n) + 1:])
    return vals


def body_of(idx, call):
    """The body a gh call carries: inline, on stdin, or from the file the gh-body record caught."""
    argv = call["argv"]
    inline = opt(argv, "--body", "-b")
    inline += [v.split("=", 1)[1] for v in opt(argv, "-f", "--raw-field", "-F", "--field")
               if v.startswith("body=") and not v.startswith("body=@")]
    if inline:
        return inline[-1]
    files = opt(argv, "--body-file") + (opt(argv, "-F") if argv[:1] == ["issue"] else [])
    files += [v[len("body=@"):] for v in opt(argv, "-F", "--field") if v.startswith("body=@")]
    if not files:
        return None
    if files[-1] == "-":
        return call.get("stdin") or ""
    for prev in reversed(calls[:idx]):
        if prev["tool"] == "gh-body" and prev["argv"] == argv:
            return prev["files"].get(files[-1]) or ""
    return ""


creates, bodies, types = [], {}, {}
for i, c in enumerate(calls):
    if c["tool"] != "gh":
        continue
    argv = c["argv"]
    if argv[:2] == ["issue", "create"]:
        n = 19600 + len(creates)
        creates.append((i, n, argv))
        bodies[n] = body_of(i, c) or ""
        types[n] = (opt(argv, "--type") or [None])[-1]
        continue
    # A later edit replaces the body or the type the create gave.
    target = None
    if argv[:2] == ["issue", "edit"] and len(argv) > 2:
        target = argv[2]
    elif argv[:1] == ["api"] and ("PATCH" in opt(argv, "-X", "--method")):
        m = re.search(r"repos/[^/\s]+/[^/\s]+/issues/(\d+)$", " ".join(a for a in argv if "/issues/" in a))
        target = m.group(1) if m else None
    m = re.search(r"(\d+)$", target or "")
    if m and int(m.group(1)) in bodies:
        n = int(m.group(1))
        b = body_of(i, c)
        if b is not None:
            bodies[n] = b
        t = opt(argv, "--type") + [v.split("=", 1)[1] for v in opt(argv, "-f", "-F", "--field", "--raw-field")
                                   if v.startswith("type=")]
        if t:
            types[n] = t[-1]

numbers = sorted({n for _, n, _ in creates})
board = [c for c in calls if c["tool"] == "hoopit-board"]


def triage_flags(n):
    flags = {}
    for c in board:
        a = c["argv"]
        if a[:1] == ["triage"] and len(a) > 2 and re.search(rf"\b{n}$", f"{a[1]} {a[2]}"):
            for f in ("--priority", "--effort", "--autonomy"):
                for v in opt(a, f):
                    flags[f] = v
            if "--ready" in a:
                flags["--ready"] = True
        if a[:1] == ["ready"] and str(n) in " ".join(a[1:3]):
            flags["ready-cmd"] = True
    return flags


# ── the run's issue count ──────────────────────────────────────────────────────────────
if "issues" in E:
    lo, _, hi = E["issues"].partition("-")
    got = len(creates)
    ok = int(lo) <= got <= int(hi or lo)
    titles = "; ".join((opt(a, "--title", "-t") or ["?"])[-1][:70] for _, _, a in creates)
    out("PASS" if ok else "FAIL", "issues_filed", "" if ok else f"{got} created, want {E['issues']}: {titles}")

# ── what every created issue owes, whatever the case ───────────────────────────────────
if not creates:
    for name in ("searched_board_first", "assigned", "typed", "triaged"):
        out("SKIP", name, "nothing created")
else:
    first = creates[0][0]
    searched = any(c["tool"] == "hoopit-board" and c["argv"][:1] in (["open"], ["scan"]) or
                   c["tool"] == "gh" and (c["argv"][:2] in (["issue", "list"], ["search", "issues"]) or
                                          any("search/issues" in a for a in c["argv"]))
                   for c in calls[:first])
    out("PASS" if searched else "FAIL", "searched_board_first", "" if searched else "no board search before the first create")
    unassigned = [n for _, n, a in creates if not opt(a, "--assignee", "-a")]
    out("FAIL" if unassigned else "PASS", "assigned", f"#{unassigned[0]} has no --assignee" if unassigned else "")
    bad = [f"#{n}={types[n]}" for n in numbers if types[n] not in ("Bug", "Feature", "Task", "Ops")]
    out("FAIL" if bad else "PASS", "typed", ", ".join(bad))
    missing = []
    for n in numbers:
        f = triage_flags(n)
        lack = [x[2:] for x in ("--priority", "--effort", "--autonomy") if x not in f]
        if lack:
            missing.append(f"#{n} lacks {'/'.join(lack)}")
    out("FAIL" if missing else "PASS", "triaged", "; ".join(missing))

# ── per-case expectations ──────────────────────────────────────────────────────────────
if "types" in E:
    allowed = {t.strip() for t in E["types"].split(",")}
    if not creates:
        out("SKIP", "typed_on_deliverable", "nothing created")
    else:
        bad = [f"#{n}={types[n]}" for n in numbers if types[n] not in allowed]
        out("FAIL" if bad else "PASS", "typed_on_deliverable", f"{', '.join(bad)}; want {E['types']}" if bad else "")

FENCE = re.compile(r"```.*?```", re.S)
TICKS = re.compile(r"`[^`\n]*`")


def live_gates(body):
    text = TICKS.sub("", FENCE.sub("", body or ""))
    return re.findall(r"Gate:\s*deployed\s+(\S+)", text)


if "gate" in E:
    gates = {n: live_gates(bodies[n]) for n in numbers}
    every = [g for gs in gates.values() for g in gs]
    if E["gate"] == "none":
        out("FAIL" if every else "PASS", "no_deploy_gate", f"live gate {every[0]}" if every else "")
    elif not creates:
        out("FAIL", "deploy_gate", "nothing created")
    else:
        pr = E["gate"]
        ok = any(re.fullmatch(rf"(?:hoopit/api)?#{pr}|https://github\.com/hoopit/api/pull/{pr}", g.rstrip(".,;)"))
                 for g in every)
        out("PASS" if ok else "FAIL", "deploy_gate", "" if ok else f"live gates {every or 'none'}; want one naming #{pr}")

if E.get("status") == "backlog":
    if not creates:
        out("SKIP", "left_in_backlog", "nothing created")
    else:
        ready = [n for n in numbers if triage_flags(n).get("--ready") or triage_flags(n).get("ready-cmd")]
        out("FAIL" if ready else "PASS", "left_in_backlog", f"#{ready[0]} moved to Ready" if ready else "")

if E.get("no_parent") == "1":
    subs = [" ".join(c["argv"]) for c in calls if c["tool"] == "gh" and any("sub_issues" in a for a in c["argv"])
            and ({"POST", "post"} & set(opt(c["argv"], "-X", "--method")) or opt(c["argv"], "-F", "-f", "--field"))]
    out("FAIL" if subs else "PASS", "not_a_sub_issue", subs[0][:120] if subs else "")

if "names" in E:
    if not creates:
        out("SKIP", "names_origin", "nothing created")
    else:
        miss = [n for n in numbers if E["names"] not in (bodies[n] or "")]
        out("FAIL" if miss else "PASS", "names_origin", f"#{miss[0]}'s body never names {E['names']}" if miss else "")

if "reads" in E:
    read = any(c["tool"] == "gh" and E["reads"] in " ".join(c["argv"]) for c in calls)
    out("PASS" if read else "FAIL", "read_covering_issue", "" if read else f"no gh call names #{E['reads']}")

if "resolve" in E:
    sentry = [" ".join(c["argv"]) for c in calls if c["tool"] == "sentry"]
    ok = any(E["resolve"] in s and "resolve" in s for s in sentry)
    out("PASS" if ok else "FAIL", "sentry_resolved", "" if ok else f"sentry calls: {sentry or 'none'}")

if E.get("decision") == "1":
    held = [n for n in numbers if triage_flags(n).get("--autonomy", "").strip("'\"") == "Needs decision"]
    if not held:
        out("FAIL", "decision_named", "no created issue is Needs decision" if creates else "nothing created")
    else:
        named = [n for n in held if re.search(r"(?im)^#{1,4}\s*The decision\b", bodies[n] or "")]
        out("PASS" if named else "FAIL", "decision_named", "" if named else f"#{held[0]} is Needs decision with no `## The decision` section")

if "effort" in E:
    allowed = {x.strip() for x in E["effort"].split(",")}
    if not creates:
        out("SKIP", "effort_prices_the_hunt", "nothing created")
    else:
        bad = [f"#{n}={triage_flags(n).get('--effort')}" for n in numbers if triage_flags(n).get("--effort") not in allowed]
        out("FAIL" if bad else "PASS", "effort_prices_the_hunt", f"{', '.join(bad)}; want {E['effort']}" if bad else "")

if E.get("proposals") == "backlog":
    rest = [n for n in numbers if (types[n] or "").strip("'\"") != "Ops"]
    if not rest:
        out("SKIP", "proposal_in_backlog", "no non-Ops issue created")
    else:
        ready = [n for n in rest if triage_flags(n).get("--ready") or triage_flags(n).get("ready-cmd")]
        out("FAIL" if ready else "PASS", "proposal_in_backlog", f"#{ready[0]} ({types[ready[0]]}) moved to Ready" if ready else "")

if "dropped" in E:
    hit = [(opt(a, "--title", "-t") or [""])[-1] for _, _, a in creates]
    hit = [t for t in hit if E["dropped"].lower() in t.lower()]
    out("FAIL" if hit else "PASS", "settled_item_dropped", f"filed: {hit[0][:80]}" if hit else "")
