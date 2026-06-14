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
#   ./install.sh                                  # Claude Code, global (defaults)
#   AGENTS="claude-code,universal" ./install.sh   # also the generic ~/.config/agents/skills
#   AGENTS="" ./install.sh                         # pick agents interactively (TTY only)
#   SCOPE=-p ./install.sh                          # project-local instead of global
#   curl -fsSL https://raw.githubusercontent.com/hoopit/setup/main/install.sh | bash
#
set -euo pipefail

# Install scope: -g (global, user-level) by default; set SCOPE=-p for project.
SCOPE="${SCOPE:--g}"

# Agent target(s). Default: Claude Code only.
#   - Override with a comma-separated list of agent keys, e.g.
#       AGENTS="claude-code,universal"   (valid keys: see `npx skills add <repo> -h`)
#   - Set AGENTS="" to choose interactively. NOTE: an interactive picker needs a
#     real terminal, so it does NOT work through the `curl | bash` one-liner —
#     use a pinned list (or run install.sh from a checkout) in that case.
# Using `${AGENTS-claude-code}` (single dash) so an explicit empty value is kept
# as "interactive", while leaving it unset falls back to the default.
AGENTS="${AGENTS-claude-code}"

# --- Curated subset of mattpocock/skills -------------------------------------
# Edit this list to change which of Matt's skills the team gets. Listing them
# explicitly with `-s` skips the interactive picker entirely and never surfaces
# his other skills.
MATT_SKILLS="caveman,write-a-skill,zoom-out,grill-with-docs,handoff"

# add_skills <package> <comma,separated,skills|*>
add_skills() {
	local pkg="$1" skills="$2"
	if [ -n "$AGENTS" ]; then
		# Deterministic: fixed agents, no prompts.
		npx -y skills@latest add "$pkg" -s "$skills" "$SCOPE" -a "$AGENTS" -y
	else
		# Interactive agent selection. Scope (-g/-p) and skills (-s) stay fixed,
		# so the only prompt is which agents to install to.
		npx -y skills@latest add "$pkg" -s "$skills" "$SCOPE"
	fi
}

echo "==> Agents: ${AGENTS:-<interactive>}   Scope: ${SCOPE}"
echo "==> Installing curated mattpocock skills: ${MATT_SKILLS}"
add_skills mattpocock/skills "$MATT_SKILLS"

echo "==> Installing Hoopit skills (hoopit/setup)"
add_skills hoopit/setup '*'

echo
echo "Done. Manage your skills with:"
echo "  npx skills list           # see what's installed and where"
echo "  npx skills update         # refresh all skills to latest (prompts to remove any deleted upstream)"
echo "  npx skills remove <name>  # remove a skill"
