"""Put the stand-in review-gate and monitor-pr in the staged hoopit-dev every run of the
suite loads: `python3 install.py <staged plugin dir>`.

Each stand-in keeps the real skill's frontmatter and the part ship hands its inputs to (the
gate's Contract and Inputs, monitor-pr's flags), so what ship passes is graded against the
interface it reads in a real session. The steps are replaced by one command on the run's
PATH. The scripts behind the real steps are removed, so no run reaches Codex or GitHub's
watch through them. Runs install concurrently: every write is a rename, and a second
install changes nothing.
"""
import os, re, shutil, sys

MARK = "<!-- ship eval stand-in -->"
plugin = sys.argv[1]

GATE_STEPS = """## Steps

From inside the worktree under review, run the pass:

```bash
review-gate-pass --scope <full|light> [--reviewed-at <sha>] [--challenge-at <sha>] \\
  [--spec-file <file>] [--challenge-file <file>] [--prior-rounds-file <file>]
```

Hand it every input the caller set, and leave out the flag of each input left unset. A
`--*-file` holds that input's text as the caller gave it; `--spec`, `--challenge` and
`--prior-rounds` take the text inline instead. It runs the whole pass — Codex, both axes,
triage and the fix commits — and prints the verdict with its notes block. Return that
verdict as this pass's.
"""

MONITOR_STEPS = """## Step 1 — Arm the watch

```bash
monitor-pr-arm <PR url or number> [every flag you were given]
```

It arms the watch, and the rounds run elsewhere. Report the line it prints to your caller
and stop: in this run the skill's work ends once the watch is armed.
"""


def split(path):
    text = open(path).read()
    m = re.match(r"(---\n.*?\n---\n)(.*)", text, re.S)
    return m.group(1), m.group(2)


def section(body, start, end):
    m = re.search(rf"(?ms)^{re.escape(start)}.*?(?=^{re.escape(end)})", body)
    if not m:
        sys.exit(f"install.py: no '{start}' … '{end}' in the staged skill")
    return m.group(0).rstrip() + "\n"


def replace(path, text):
    tmp = f"{path}.{os.getpid()}"
    with open(tmp, "w") as fh:
        fh.write(text)
    os.replace(tmp, path)


def stand_in(name, build):
    skill = os.path.join(plugin, "skills", name)
    path = os.path.join(skill, "SKILL.md")
    if MARK in open(path).read():
        return
    front, body = split(path)
    replace(path, front + MARK + "\n\n" + build(body))
    for entry in os.listdir(skill):
        if entry.startswith("SKILL.md"):
            continue
        target = os.path.join(skill, entry)
        if os.path.isdir(target):
            shutil.rmtree(target, ignore_errors=True)
        else:
            try:
                os.remove(target)
            except FileNotFoundError:
                pass


stand_in("review-gate", lambda body: "# Review Gate\n\n"
         "In this run the reviewers are replaced by `review-gate-pass`. The Contract and Inputs "
         "below are the real gate's.\n\n" + section(body, "## Contract", "## Steps") + "\n" + GATE_STEPS)
stand_in("monitor-pr", lambda body: "# Monitor PR\n\n"
         "In this run the watch is `monitor-pr-arm`, and no rounds run here.\n\n"
         + section(body, "Flags:", "## Step 1") + "\n" + MONITOR_STEPS)
