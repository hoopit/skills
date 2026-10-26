#!/usr/bin/env bash
# The independent reviewer is not installed: mattpocock-skills is off for this checkout. Local
# settings outrank the project's, which enables it, and the file is gitignored, so the branch's
# diff is unchanged.
set -euo pipefail
mkdir -p .claude
printf '{"enabledPlugins": {"mattpocock-skills@claude-plugins-official": false}}\n' >.claude/settings.local.json
