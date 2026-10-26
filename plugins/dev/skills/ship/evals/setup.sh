#!/usr/bin/env bash
# Shapes every ship fixture: api as it stood before hoopit/api#18161 was fixed, an origin
# that takes the push, the review-gate and monitor-pr stand-ins, and a test database of
# the run's own. A case's setup.sh then takes the run to where its prompt starts.
set -euo pipefail
cd "$EVAL_FIXTURE"

# The fix of hoopit/api#18161 (534b45c05a, PR #18164) and the master it landed on.
FIX=534b45c05a338323650455decd223ca3acc20e41
BASE=515fb743a8ae4281f0dec00851709438ef4b07b3
suite=$EVAL_SUITE_DIR
shims=$EVAL_RUN_DIR/shims

# --- api before the fix ----------------------------------------------------------------
# The runner's origin carries the fix and the dead push URL. This run's origin has master
# at BASE, every real branch name that does not carry the fix (Step 2 mirrors their
# shape), and takes the push. The fixture's own refs to the fix go too, so neither `git
# log --all` nor a fetch shows the agent the answer.
origin=$EVAL_RUN_DIR/origin.git
git clone -q --bare --shared "$EVAL_UPSTREAM" "$origin"
gone() {  # gone <git-dir> <ref>...: those that carry the fix, its squash or its PR's branch
  local dir=$1; shift
  { git --git-dir "$dir" for-each-ref --contains "$FIX" --format='delete %(refname)' "$@"
    git --git-dir "$dir" for-each-ref --format='delete %(refname)' "$@" | grep -i '18161' || true; } | sort -u
}
gone "$origin" refs/heads | git --git-dir "$origin" update-ref --stdin
git --git-dir "$origin" update-ref refs/heads/master "$BASE"
gone .git refs/remotes refs/heads/ | { grep -Ev ' refs/(heads/master|remotes/origin/HEAD)$' || true; } |
  git update-ref --stdin
git reset -q --hard "$BASE"
git update-ref refs/remotes/origin/master "$BASE"
git remote set-url origin "$origin"
git remote set-url --push origin "$origin"
git fetch -q origin
git --git-dir "$origin" for-each-ref --format='%(refname) %(objectname)' refs/heads >"$EVAL_RUN_DIR/origin-heads"

# --- gh: the PR's body kept, its closing references answered ---------------------------
# create-pull-request's suite owns the wrapper that copies every --body-file as the call is
# made and answers closingIssuesReferences from the body, the way GitHub would.
mv "$shims/gh" "$shims/gh.shim"
cat >"$shims/gh" <<PY
#!/usr/bin/env python3
import sys
sys.path.insert(0, "$suite/../../create-pull-request/evals")
import gh_wrap
gh_wrap.main("$EVAL_RUN_DIR", "$EVAL_CALLS", "$shims/gh.shim")
PY
chmod +x "$shims/gh"

# --- review-gate and monitor-pr stand in ------------------------------------------------
for s in review-gate-pass monitor-pr-arm; do
  printf '#!/usr/bin/env bash\nSHIP_EVAL_CALLS=%q SHIP_EVAL_CASE_DIR=%q exec python3 %q "$@"\n' \
    "$EVAL_CALLS" "$EVAL_CASE_DIR" "$suite/standins/$s" >"$shims/$s"
  chmod +x "$shims/$s"
done
# Neither is one of the runner's shims, and the real CLIs on this machine are signed in. A
# run that reaches codex went around the review-gate stand-in.
for tool in codex sentry; do
  cat >"$shims/$tool" <<PY
#!/usr/bin/env python3
import json, os, sys
with open("$EVAL_CALLS", "a") as fh:
    fh.write(json.dumps({"tool": "$tool", "argv": sys.argv[1:], "stdin": None, "cwd": os.getcwd()}) + "\\n")
sys.exit("$tool is disabled in this eval run")
PY
  chmod +x "$shims/$tool"
done
# The runner stages the plugin under test once per suite run, beside the run dirs.
plugin=$(dirname "$EVAL_RUN_DIR")/plugin/plugins/dev
[[ -f $plugin/skills/ship/SKILL.md ]] || { echo "no staged hoopit-dev at $plugin" >&2; exit 1; }
python3 "$suite/standins/install.py" "$plugin"

# --- a test database of the run's own ---------------------------------------------------
# A fresh api test database takes ~3.5 minutes to migrate, and concurrent runs on one branch
# name would share create-worktree's test_<branch>. So the first run builds a template at
# BASE, each run clones it (seconds), and a `uv` in front of the real one names the clone:
# the settings read TEST_DB_NAME from the environment before .envs/__worktree.env.
export PGHOST=127.0.0.1 PGPORT=5435 PGUSER=postgres PGPASSWORD=
template=test_ship_eval_${BASE:0:10}
db=test_ship_eval_$(basename "$EVAL_RUN_DIR" | tr -c 'a-zA-Z0-9\n' _ | tail -c 30)_$(md5sum <<<"$EVAL_RUN_DIR" | cut -c1-6)
echo "$db" >"$EVAL_RUN_DIR/test-db"
uv=$(command -v uv)
(
  flock 9
  if [[ -z $(psql -Atc "select 1 from pg_database where datname = '$template'") ]]; then
    TEST_DB_NAME=$template MISE_QUIET=1 "$uv" run pytest --create-db -q -p no:cacheprovider \
      posts/tests/test_app_api/test_post_image_detail_view.py >"$EVAL_RUN_DIR/template.log" 2>&1
  fi
  psql -qc "drop database if exists \"$db\"" -c "create database \"$db\" template \"$template\""
) 9>"$HOME/.cache/skill-evals/ship-test-db.lock"
printf '#!/usr/bin/env bash\nexport TEST_DB_NAME=%q\nexec %q "$@"\n' "$db" "$uv" >"$shims/uv"
chmod +x "$shims/uv"
# The user CLAUDE.md a run loads (hoopit/skills#88) points agents at `hoopit-pytest`, which
# starts uv in a systemd scope that drops TEST_DB_NAME. In front of it, the run's own uv.
printf '#!/usr/bin/env bash\nexec %q run pytest "$@"\n' "$shims/uv" >"$shims/hoopit-pytest"
chmod +x "$shims/hoopit-pytest"
