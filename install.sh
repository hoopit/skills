#!/usr/bin/env bash
#
# Hoopit skills installer.
#
# Installs the curated Hoopit skill set into your coding agent(s) using the
# Vercel `skills` CLI (https://skills.sh). It installs two things:
#
#   1. A curated subset of mattpocock/skills — pulled straight from his repo, so
#      `npx skills update` keeps them current automatically. His other skills are
#      intentionally NOT installed (no manual picker — the subset is fixed below).
#   2. Hoopit's own skills from hoopit/setup (onboarding, etc.).
#
# Re-run any time; it is safe to repeat. To update later: `npx skills update`.
#
# Usage:
#   ./install.sh                 # global install (default), auto-detects your agent
#   SCOPE=-p ./install.sh        # project-local install instead of global
#   curl -fsSL https://raw.githubusercontent.com/hoopit/setup/main/install.sh | bash
#
set -euo pipefail

# Install scope: -g (global, user-level) by default; set SCOPE=-p for project.
SCOPE="${SCOPE:--g}"

# --- Curated subset of mattpocock/skills -------------------------------------
# Edit this list to change which of Matt's skills the team gets. Listing them
# explicitly with `-s` skips the interactive picker entirely and never surfaces
# his other skills.
MATT_SKILLS="caveman,write-a-skill,zoom-out,grill-with-docs,handoff"

echo "==> Installing curated mattpocock skills: ${MATT_SKILLS}"
npx -y skills@latest add mattpocock/skills -s "${MATT_SKILLS}" "${SCOPE}" -y

echo "==> Installing Hoopit skills (hoopit/setup)"
npx -y skills@latest add hoopit/setup -s '*' "${SCOPE}" -y

echo
echo "Done. Manage your skills with:"
echo "  npx skills list           # see what's installed"
echo "  npx skills update         # refresh all skills to latest (prompts to remove any deleted upstream)"
echo "  npx skills remove <name>  # remove a skill"
