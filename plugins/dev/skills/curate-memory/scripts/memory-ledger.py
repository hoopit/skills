#!/usr/bin/env python3
"""Activity ledger for one project's agent memories.

Usage: memory-ledger.py [<memory-dir>]   (default: ./memory, else cwd)

Prints one row per memory: days idle, days old, how many sessions touched it,
type, created date, last-touched date, slug. Sorted most-idle first.

Signals: a memory is "touched" when a transcript line mentions `memory/<slug>.md`
(a read or an edit of the file) or `[[<slug>]]` (a link from another memory).
The MEMORY.md index line is deliberately not a touch - it is injected into every
session, so counting it would mark every memory as used today.

Scope: only this project's transcripts are scanned. A memory read from another
project's session does not register, so treat idle days as a floor.
"""
import datetime
import pathlib
import re
import sys

arg = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
memdir = arg / "memory" if (arg / "memory").is_dir() else arg
projdir = memdir.parent

files = sorted(p for p in memdir.glob("*.md") if p.name != "MEMORY.md")
if not files:
    sys.exit(f"no memory files in {memdir}")
slugs = {p.stem: p for p in files}

touch = re.compile(r"(?:memory/|\[\[)(" + "|".join(map(re.escape, slugs)) + r")(?:\.md|\]\])")
stamp = re.compile(r'"timestamp":"(\d{4}-\d\d-\d\d)T')

first, last, sessions = {}, {}, {}
for jl in projdir.glob("*.jsonl"):
    fallback = datetime.date.fromtimestamp(jl.stat().st_mtime).isoformat()
    with jl.open(errors="replace") as fh:
        for line in fh:
            hits = set(touch.findall(line))
            if not hits:
                continue
            m = stamp.search(line)
            ts = m.group(1) if m else fallback
            for slug in hits:
                first[slug] = min(ts, first.get(slug, ts))
                last[slug] = max(ts, last.get(slug, ts))
                sessions.setdefault(slug, set()).add(jl.stem)

today = datetime.date.today()
days = lambda d: (today - datetime.date.fromisoformat(d)).days

rows = []
for slug, path in slugs.items():
    text = path.read_text(errors="replace")
    mtype = (re.search(r"^\s*type:\s*(\S+)", text, re.M) or (None, "?"))[1]
    st = path.stat()
    born = getattr(st, "st_birthtime", st.st_ctime)
    created = min(first.get(slug, "9999"), datetime.date.fromtimestamp(born).isoformat())
    touched = max(last.get(slug, "0000"), datetime.date.fromtimestamp(st.st_mtime).isoformat())
    rows.append((days(touched), days(created), len(sessions.get(slug, ())), mtype, created, touched, slug))

rows.sort(reverse=True)
print(f"{len(rows)} memories in {memdir}  (idle days are a floor: this project's transcripts only)\n")
print(f"{'idle':>4} {'age':>4} {'sess':>4}  {'type':<9} {'created':<10} {'touched':<10} name")
for idle, age, n, mtype, created, touched, slug in rows:
    print(f"{idle:>4} {age:>4} {n:>4}  {mtype:<9} {created:<10} {touched:<10} {slug}")
