#!/usr/bin/env bash
#
# Enumerate everything that spends context in this Claude Code install and emit
# it as one JSON object on stdout. Used by reduce-context.sh and by the skill.
#
#   inventory.sh [--no-probe]
#
# --no-probe skips the two headless `claude` runs (each costs one trivial API
# call and a few seconds) and falls back to the on-disk sources only.

set -euo pipefail

SETTINGS="${CLAUDE_SETTINGS:-$HOME/.claude/settings.json}"
PLUGIN_REGISTRY="$HOME/.claude/plugins/installed_plugins.json"
PROBE=1
[[ "${1:-}" == "--no-probe" ]] && PROBE=0

command -v jq >/dev/null 2>&1 || { echo 'inventory.sh needs jq' >&2; exit 1; }
[[ -f "$SETTINGS" ]] || printf '{}\n' > "$SETTINGS"

# Skills Claude Code ships with, for builds or probes that under-report them.
# The probe is authoritative where the two disagree; this only adds names.
FALLBACK_BUNDLED=(
  artifact-design artifact-diagramming artifact-capabilities artifact-pr-review
  whiteboard workshop prototype dataviz claude-api cowork-plugin
  commit pr commit-push-pr init security-review keybindings-help claude-in-chrome
)

# probe [extra claude args] prints the session's init event, or nothing.
probe() {
  timeout 180 claude -p hi --output-format stream-json --verbose --max-turns 1 "$@" 2>/dev/null \
    | grep -m1 '"subtype":"init"' || true
}

INIT_EFFECTIVE='{}'
INIT_BARE='{}'
if (( PROBE )) && command -v claude >/dev/null 2>&1; then
  # What this machine currently loads, overrides and all.
  INIT_EFFECTIVE=$(probe); [[ -n "$INIT_EFFECTIVE" ]] || INIT_EFFECTIVE='{}'
  # With every settings source dropped, what is left is what ships in the binary,
  # including the skills the user has already switched off.
  INIT_BARE=$(probe --setting-sources ''); [[ -n "$INIT_BARE" ]] || INIT_BARE='{}'
fi

# frontmatter FILE KEY reads one frontmatter value.
frontmatter() {
  sed -n '1,20p' "$1" | grep -m1 "^$2:" | sed "s/^$2:[[:space:]]*//" | tr -d '"' || true
}

skill_rows() {  # dir-glob label -> {name, description, source} per SKILL.md
  local file name desc
  while IFS= read -r file; do
    [[ -n "$file" ]] || continue
    name=$(frontmatter "$file" name); [[ -n "$name" ]] || name=$(basename "$(dirname "$file")")
    desc=$(frontmatter "$file" description | cut -c1-120)
    jq -nc --arg n "$1$name" --arg d "$desc" --arg p "$file" --arg s "$2" \
      '{name: $n, description: $d, path: $p, source: $s}'
  done
}

# Bundled: probe with no settings sources, unioned with the fallback names.
BUNDLED=$(jq -nc --argjson init "$INIT_BARE" --args \
  '($init.skills // []) as $live
   | ($live + ($ARGS.positional - $live)) | unique
   | map({name: ., seen: (. as $n | $live | index($n) != null)})' \
  "${FALLBACK_BUNDLED[@]}")

# Account-synced skills, addressed as anthropic-skills:<name>.
SYNCED='[]'
if [[ -d "$HOME/.claude/skills/synced" ]]; then
  SYNCED=$(find "$HOME/.claude/skills/synced" -mindepth 3 -maxdepth 3 -name SKILL.md 2>/dev/null \
    | sort | skill_rows "anthropic-skills:" synced | jq -sc 'unique_by(.name)')
fi

# Installed plugins and the skills each one carries.
PLUGINS='[]'
PLUGIN_SKILLS='[]'
if [[ -f "$PLUGIN_REGISTRY" ]]; then
  PLUGINS=$(jq -c --slurpfile s "$SETTINGS" '
    ($s[0].enabledPlugins // {}) as $en
    | .plugins | keys | map(. as $k | {
        key: $k,
        enabled: (if $en | has($k) then $en[$k] else true end),
        explicit: ($en | has($k))
      })' "$PLUGIN_REGISTRY")
  while IFS= read -r key; do
    [[ -n "$key" ]] || continue
    enabled=$(jq -r --arg k "$key" 'if (.enabledPlugins // {}) | has($k) then .enabledPlugins[$k] else true end' "$SETTINGS")
    [[ "$enabled" == "false" ]] && continue
    short=${key%%@*}
    path=$(jq -r --arg k "$key" '.plugins[$k] | sort_by(.lastUpdated // .installedAt) | last | .installPath // empty' "$PLUGIN_REGISTRY")
    [[ -n "$path" && -d "$path" ]] || continue
    rows=$(find "$path" -maxdepth 4 -name SKILL.md 2>/dev/null | sort | skill_rows "$short:" "plugin $short" | jq -sc 'unique_by(.name)')
    PLUGIN_SKILLS=$(jq -nc --argjson a "$PLUGIN_SKILLS" --argjson b "$rows" '$a + $b')
  done < <(jq -r '.plugins | keys[]' "$PLUGIN_REGISTRY")
fi

# Skills you wrote yourself, user- and project-scoped.
OWN='[]'
for dir in "$HOME/.claude/skills" "$PWD/.claude/skills"; do
  [[ -d "$dir" ]] || continue
  rows=$(find "$dir" -maxdepth 2 -name SKILL.md 2>/dev/null | sort | skill_rows "" "${dir/#$HOME/~}" | jq -sc '.')
  OWN=$(jq -nc --argjson a "$OWN" --argjson b "$rows" '$a + $b')
done

# Custom subagents: their descriptions are listed to the model every turn.
AGENTS='[]'
for dir in "$HOME/.claude/agents" "$PWD/.claude/agents"; do
  [[ -d "$dir" ]] || continue
  rows=$(find "$dir" -maxdepth 1 -name '*.md' 2>/dev/null | sort \
    | while IFS= read -r f; do
        jq -nc --arg n "$(basename "$f" .md)" --arg p "$f" --arg d "$(frontmatter "$f" description | cut -c1-120)" \
          '{name: $n, path: $p, description: $d}'
      done | jq -sc '.')
  AGENTS=$(jq -nc --argjson a "$AGENTS" --argjson b "$rows" '$a + $b')
done

jq -n \
  --arg settings "$SETTINGS" \
  --argjson probed "$( (( PROBE )) && echo true || echo false )" \
  --argjson bundled "$BUNDLED" \
  --argjson synced "$SYNCED" \
  --argjson plugins "$PLUGINS" \
  --argjson pluginSkills "$PLUGIN_SKILLS" \
  --argjson own "$OWN" \
  --argjson agents "$AGENTS" \
  --argjson effective "$INIT_EFFECTIVE" \
  --slurpfile s "$SETTINGS" \
  '{
    settingsPath: $settings,
    probed: $probed,
    overrides: ($s[0].skillOverrides // {}),
    flags: ($s[0] | {enableArtifact, enableWorkflows, workflowKeywordTriggerEnabled,
                     disableAgentView, autoMemoryEnabled, disableBundledSkills}
            | with_entries(select(.value != null))),
    bundled: $bundled,
    synced: $synced,
    plugins: $plugins,
    pluginSkills: $pluginSkills,
    ownSkills: $own,
    agents: $agents,
    mcpServers: ($effective.mcp_servers // []),
    liveSkills: ($effective.skills // []),
    tools: ($effective.tools // []),
    version: ($effective.claude_code_version // null)
  }'
