#!/usr/bin/env bash
# master moves on after the PR branched: BAC-4398 rewrote the comment the PR rewrites, so the
# PR's head conflicts with the default branch. Committed on origin's master only — the fixture's
# own master and origin/master stay at the pin until the round fetches.
set -euo pipefail
F=payments/web/views/organization_bank_account_list_view.py
tmp="$EVAL_RUN_DIR/master-wt"
git worktree add -q --detach "$tmp" "$(git rev-parse master)"
python3 - "$tmp/$F" <<'PY'
import sys
p = sys.argv[1]; t = open(p).read()
old = ("        # Only org (root) admins see the account-level balance; same scope boundary as the\n"
       "        # enabled_for_count / default_for_subgroups_of_count narrowing in get_queryset.\n")
new = ("        # Only org (root) admins see the account-level balance (BAC-4398): a sub-group admin\n"
       "        # gets the narrowed list from get_queryset, and its export carries no balance column.\n")
assert old in t
open(p, "w").write(t.replace(old, new))
PY
when=$(( $(date +%s) - 20000 ))
git -C "$tmp" -c user.name="Ola Nordmann" -c user.email="ola@hoopit.io" commit -q -am "BAC-4398: Say why sub-group admins see no balance" \
  --date="@$when"
git -C "$tmp" push -q origin HEAD:refs/heads/master
git worktree remove --force "$tmp"
