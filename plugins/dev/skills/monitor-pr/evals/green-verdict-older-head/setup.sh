#!/usr/bin/env bash
# master moves on after the PR branched: another change touched the import the PR drops, so the
# head conflicts and the round has to push a new one. Committed on origin's master only.
set -euo pipefail
F=featureflags/tasks.py
tmp="$EVAL_RUN_DIR/master-wt"
git worktree add -q --detach "$tmp" "$(git rev-parse master)"
sed 's/^from typing import TYPE_CHECKING$/from typing import TYPE_CHECKING, Final/' "$tmp/$F" >"$tmp/$F.new"
mv "$tmp/$F.new" "$tmp/$F"
git -C "$tmp" diff --quiet && { echo "the import this case edits has moved" >&2; exit 1; }
when=$(( $(date +%s) - 20000 ))
git -C "$tmp" -c user.name="Ola Nordmann" -c user.email="ola@hoopit.io" commit -q -am "Type the flag prune constants" \
  --date="@$when"
git -C "$tmp" push -q origin HEAD:refs/heads/master
git worktree remove --force "$tmp"
