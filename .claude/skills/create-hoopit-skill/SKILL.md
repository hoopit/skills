---
name: create-hoopit-skill
description: Conventions for authoring skills in the hoopit/skills repo — keep skills project-agnostic and put each skill in the right plugin directory. Use when adding, editing, or removing a skill in this repo.
---

# Authoring skills in hoopit/skills

This repo is a **distribution** of skills, shipped as a Claude Code plugin
marketplace: one skill is installed into many different Hoopit repos (`api`,
`flutter-app`, …). A skill written here runs in all of them, so it must not assume
it's running in any one of them.

Layout: each plugin is a self-contained directory `plugins/<group>/` with its own
`.claude-plugin/plugin.json` and a `skills/` folder. A skill lives at
`plugins/<group>/skills/<name>/SKILL.md`. Skills are auto-discovered from the
plugin's own `skills/` folder, so a plugin exposes exactly the skills in its
directory — **never** point multiple plugins at one shared `skills/` folder, or
every plugin leaks every skill.

> This skill itself is **not** distributed — it lives in the repo's `.claude/skills/`,
> which no plugin's `source` points at, so the marketplace never picks it up. It
> exists only to guide authoring while working in this repo.

## Rule 1 — skills must be project-agnostic

**Never bake a project-specific term into a skill.** No repo slugs, service
names, env-file names, role names, paths, ticket prefixes, URLs, queue names —
nothing that is true for one repo but not another.

Instead:

- **Derive it at runtime** when you can. E.g. an org/repo that's already present
  in a URL or in `git remote` — parse it, don't hard-code it.
- **Defer to `AGENTS.md`** otherwise. Anything project-specific the skill needs
  belongs in the `AGENTS.md` of *every* repo the skill is installed into. The
  skill should say "check the current repo's `AGENTS.md` for X" rather than
  naming X. Keeping those facts in `AGENTS.md` is part of shipping the skill —
  if you add a skill that needs a new fact, add that fact to each target repo's
  `AGENTS.md`.

❌ `The org/repo for this project is hoopit/api.`
✅ `Parse the org/repo from the URL; if absent, see the repo's AGENTS.md.`

Skill content should read identically useful whether Claude is in `api`,
`flutter-app`, or a repo that doesn't exist yet.

## Rule 2 — put the skill in the right plugin

Because skills are auto-discovered from each plugin's `skills/` folder, the common
cases are simple:

- **Add a skill to an existing group**: create
  `plugins/<group>/skills/<name>/SKILL.md` (plus any bundled resources). That's
  it — no `marketplace.json` edit, it's auto-discovered.
- **Remove a skill**: delete its directory.
- **Move a skill between groups**: move its directory to the other plugin's
  `skills/`.

`marketplace.json` only changes when the set of **plugins (groups)** changes. To
add a new group:

1. Create `plugins/<group>/.claude-plugin/plugin.json` (`name` + `description`)
   and a `plugins/<group>/skills/` folder with the skills.
2. Add a plugin entry to `.claude-plugin/marketplace.json` — `name` +
   `"source": "./plugins/<group>"`. Don't drop the top-level `owner`; Claude Code
   refuses to parse the file without it. Validate the JSON.
3. Add a row to the README's hand-maintained **Plugins** table.

The README's **"Skills by plugin"** block (one table per plugin) is **generated** —
never hand-edit between its `<!-- BEGIN/END generated skills -->` markers.
[`scripts/gen-skills-readme.sh`](../../../scripts/gen-skills-readme.sh) builds it from
each plugin's `SKILL.md` frontmatter and `marketplace.json`. A `pre-commit` hook and a
CI workflow regenerate it, so editing a skill's `name`/`description`/
`disable-model-invocation` reflows the README automatically — just run the script (or
`pre-commit run`) if you want to see the change locally before committing.

Every plugin in this marketplace is a **local directory** (`"source":
"./plugins/<group>"`). Third-party skills are not re-packaged here — install them from
their own marketplace (e.g. `mattpocock-skills@claude-plugins-official`) so updates
come straight from upstream.

## Bundled scripts are reached through `${CLAUDE_PLUGIN_ROOT}`

A skill that ships a script invokes it as
`bash "${CLAUDE_PLUGIN_ROOT}/skills/<skill>/scripts/<name>.sh"`, giving the plugin directory the
session actually loaded — the only copy that matches the skill text running. A `find` over
`~/.claude/plugins` picks an arbitrary installed commit, so the skill silently runs a months-old
script.

**It is a text substitution, not a shell variable**, so write the token exactly: the harness
rewrites the literal `${CLAUDE_PLUGIN_ROOT}` before the body reaches the model, and any
decoration — `:?`, `:-`, a default — takes the string out of the matched set and leaves it to a
shell that has no such variable. It is substituted in **skill bodies, command bodies and agent
definitions** — all three confirmed in the loader — and nowhere else: a reference doc opened with `Read`, or a bundled script, gets the
raw bytes, so those take the path from whoever called them. A path that still reads
`${CLAUDE_PLUGIN_ROOT}` when you go to run it is the tell that you are not in a substituted
context — stop rather than run it.

## Checklist

- [ ] Skill body contains no project-specific terms (Rule 1)
- [ ] Any project-specific facts it relies on are added to each target repo's `AGENTS.md`
- [ ] Skill lives at `plugins/<group>/skills/<name>/SKILL.md`
- [ ] Bundled scripts invoked as `${CLAUDE_PLUGIN_ROOT}/skills/<name>/scripts/…`
- [ ] `marketplace.json` touched only if a plugin/group was added or removed (valid JSON)
