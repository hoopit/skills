#!/usr/bin/env bash
# Two shims beside the runner's, in the run's shims dir that leads the agent's PATH.
#
# gh: an issue's body is graded, and `--body-file` hands gh a path, not the text. A file in
# /tmp can be rewritten by a concurrent run or by the agent itself before check.sh reads it, so
# this wrapper records each file's text as the call happens (tool `gh-body`). `gh issue create`
# it answers itself, because a mock answers every call alike: the first create gets #19600 and
# each later one the next number, so two issues filed in one run are two issues. Every other
# call goes to the runner's gh shim unchanged.
#
# sentry: not one of the runner's shims, and the real CLI on this machine is signed in. Every
# call is recorded as tool `sentry`; resolving or viewing API-5KD answers, anything else fails.
set -euo pipefail
shims="$EVAL_RUN_DIR/shims"
mv "$shims/gh" "$EVAL_RUN_DIR/gh-recorder"

cat > "$shims/gh" <<EOF
#!/usr/bin/env python3
import json, os, sys
CALLS, REAL = "$EVAL_CALLS", "$EVAL_RUN_DIR/gh-recorder"
EOF
cat >> "$shims/gh" <<'EOF'
argv = sys.argv[1:]
paths = []
for i, a in enumerate(argv):
    nxt = argv[i + 1] if i + 1 < len(argv) else ""
    if a in ("--body-file", "-F") and argv[:1] == ["issue"]:
        paths.append(nxt)
    elif a.startswith("--body-file="):
        paths.append(a.split("=", 1)[1])
    elif a in ("-F", "-f", "--field", "--raw-field") and nxt.startswith("body=@"):
        paths.append(nxt[len("body=@"):])
    elif a.startswith(("--field=body=@", "-Fbody=@")):
        paths.append(a.split("body=@", 1)[1])
files = {}
for p in paths:
    if p and p != "-":
        try:
            files[p] = open(os.path.join(os.getcwd(), os.path.expanduser(p))).read()
        except OSError as e:
            files[p] = None
if files:
    with open(CALLS, "a") as fh:
        fh.write(json.dumps({"tool": "gh-body", "argv": argv, "files": files, "cwd": os.getcwd()}) + "\n")
if argv[:2] == ["issue", "create"]:
    import select
    stdin = None
    if not sys.stdin.isatty() and select.select([sys.stdin], [], [], 1)[0]:
        stdin = sys.stdin.read()
    with open(CALLS, "a") as fh:
        fh.write(json.dumps({"tool": "gh", "argv": argv, "stdin": stdin, "cwd": os.getcwd()}) + "\n")
    with open(CALLS) as fh:
        n = sum(1 for l in fh if l.startswith('{"tool": "gh", "argv": ["issue", "create"'))
    print(f"https://github.com/hoopit/api/issues/{19599 + n}")
    sys.exit(0)
os.execv(REAL, [REAL, *argv])
EOF
chmod +x "$shims/gh"

cat > "$shims/sentry" <<EOF
#!/usr/bin/env python3
import json, os, sys
CALLS = "$EVAL_CALLS"
EOF
cat >> "$shims/sentry" <<'EOF'
argv = sys.argv[1:]
with open(CALLS, "a") as fh:
    fh.write(json.dumps({"tool": "sentry", "argv": argv, "stdin": None, "cwd": os.getcwd()}) + "\n")
line = " ".join(argv)
if "API-5KD" in line and "resolve" in line:
    print("Resolved API-5KD: it reopens as a regression on the next matching event.")
elif "API-5KD" in line:
    print("API-5KD  TypeError: '<' not supported between instances of 'NoneType' and 'datetime.date'\n"
          "status: unresolved   events: 212   users: 64   last seen: 2026-10-01T06:41Z\n"
          "culprit: payments.models.payment_plan in _get_next_charge_date")
else:
    sys.exit(f"sentry: no answer for: {line}")
EOF
chmod +x "$shims/sentry"
