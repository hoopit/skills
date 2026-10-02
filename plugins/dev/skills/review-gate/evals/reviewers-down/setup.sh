#!/usr/bin/env bash
# No reviewer subagent can run: the Agent tool is denied, the way a spend limit kills every
# subagent before it reports. What is left is the session's own read of its own diff, which the
# gate never counts as independent review. Local settings are gitignored, so the branch's diff is
# unchanged.
set -euo pipefail
mkdir -p .claude
printf '{"permissions": {"deny": ["Agent", "Task"]}}\n' >.claude/settings.local.json
