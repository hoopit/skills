#!/usr/bin/env bash
# Shapes every create-pull-request fixture: a push that lands, and a `gh` that keeps
# what the PR's body was. Each case's own setup.sh then leaves its change uncommitted.
set -euo pipefail
cd "$EVAL_FIXTURE"

# The runner kills the push URL; a branch that cannot be pushed stops the agent before the
# step under test. A bare clone sharing the fixture's objects takes the push instead.
git clone -q --bare --shared "$EVAL_FIXTURE" "$EVAL_RUN_DIR/push.git"
git remote set-url --push origin "$EVAL_RUN_DIR/push.git"

shims="$EVAL_RUN_DIR/shims"
mv "$shims/gh" "$shims/gh.shim"
python=$(head -1 "$shims/gh.shim" | sed 's/^#!//')
cat >"$shims/gh" <<PY
#!$python
import sys
sys.path.insert(0, "$EVAL_SUITE_DIR")
import gh_wrap
gh_wrap.main("$EVAL_RUN_DIR", "$EVAL_CALLS", "$shims/gh.shim")
PY
chmod +x "$shims/gh"
