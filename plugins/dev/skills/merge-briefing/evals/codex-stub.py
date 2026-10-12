# Stands in for the Codex CLI in a merge-briefing eval run. setup.sh installs it as `codex` in the
# run's shim dir, ahead of the real CLI on the agent's PATH, with its answers in `codex.json` beside
# it. Every call is recorded to the run's EVAL_CALLS like the tracker shims' calls.
#
# Modes: `ran` answers with the review and challenge in codex.json, `fail` exits 1 the way an
# expired Codex login does. The real CLI would spend minutes and a Codex quota per run, and would
# answer differently run to run. Each suite keeps its own copy: the modes and what a call records
# are what that suite's checks grade.
import json, os, select, subprocess, sys

conf = json.load(open(os.path.realpath(__file__) + ".json"))
argv = sys.argv[1:]
# Read stdin only when it is already there or closes, as the tracker shims do: a call nobody
# pipes into must not hang on a pipe the agent's shell holds open.
stdin = None
if not sys.stdin.isatty() and select.select([sys.stdin], [], [], 1)[0]:
    stdin = sys.stdin.read()
# The commit Codex is pointed at, so a check can tell a challenge of the PR's head from one of
# whatever the session happened to have checked out.
where = argv[argv.index("--cd") + 1] if "--cd" in argv else os.getcwd()
head = subprocess.run(["git", "-C", where, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
with open(conf["calls"], "a") as fh:
    fh.write(json.dumps({"tool": "codex", "argv": argv, "stdin": (stdin or "")[:2000] or None,
                         "cwd": os.getcwd(), "head": head or None}) + "\n")

if argv[:1] in (["--version"], ["-V"]):
    print("codex-cli 0.159.3")
    sys.exit(0)
if argv[:1] != ["exec"]:
    sys.exit(f"codex: unsupported in this eval: {' '.join(argv)}")
if conf["mode"] == "fail":
    print("ERROR: unexpected status 401 Unauthorized: Your access token could not be refreshed "
          "because your refresh token has expired. Please log out and sign in again.", file=sys.stderr)
    sys.exit(1)

out = argv[argv.index("-o") + 1] if "-o" in argv else None
text = conf["challenge"] if "--output-schema" in argv else conf["review"]
if out:
    with open(out, "w") as fh:
        fh.write(text)
print(text)
