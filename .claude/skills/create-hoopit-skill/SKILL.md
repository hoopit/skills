---
name: create-hoopit-skill
description: Conventions for authoring skills in the hoopit/skills repo — keep skills project-agnostic and keep the four sync points in lockstep. Use when adding, editing, or removing a skill in this repo.
---

# Authoring skills in hoopit/skills

This repo is a **distribution** of skills: one skill is installed into many
different Hoopit repos (`api`, `flutter-app`, …) via the `skills` CLI. A skill
written here runs in all of them, so it must not assume it's running in any one
of them.

> This skill itself is **not** distributed — it lives in `.claude/skills/`, not
> `skills/`, so the marketplace never picks it up. It exists only to guide
> authoring while working in this repo.

## Rule 1 — skills must be project-agnostic

**Never bake a project-specific term into a skill.** No repo slugs, service
names, env-file names, role names, paths, ticket prefixes, URLs, queue names —
nothing that is true for one repo but not another.

Instead:

- **Derive it at runtime** when you can. E.g. an org/repo that's already present
  in a URL or in `git remote` — parse it, don't hard-code it.
- **Defer to `CLAUDE.md`** otherwise. Anything project-specific the skill needs
  belongs in the `CLAUDE.md` of *every* repo the skill is installed into. The
  skill should say "check the current repo's `CLAUDE.md` for X" rather than
  naming X. Keeping those facts in `CLAUDE.md` is part of shipping the skill —
  if you add a skill that needs a new fact, add that fact to each target repo's
  `CLAUDE.md`.

❌ `The org/repo for this project is hoopit/api.`
✅ `Parse the org/repo from the URL; if absent, see the repo's CLAUDE.md.`

Skill content should read identically useful whether Claude is in `api`,
`flutter-app`, or a repo that doesn't exist yet.

## Rule 2 — keep the four sync points in lockstep

A skill is registered in **four** places. Adding or removing one means editing
all four (or the installer, picker, and docs drift out of sync):

1. **`skills/<name>/SKILL.md`** — the skill folder itself (plus any bundled
   resources alongside it). Flat layout: `skills/<name>/`, one folder per skill.
2. **`.claude-plugin/marketplace.json`** — add/remove `"./skills/<name>"` in the
   right plugin's `skills` array. This one file serves **two** consumers: the
   `skills` CLI (group headers in its picker) and Claude Code's **plugin
   marketplace**. Each plugin uses `"source": "./"` + `"strict": false` so its
   `skills` array is the authoritative, exhaustive list — only listed skills are
   exposed (nothing auto-discovered, so `.claude/skills/` stays private). Don't
   drop `owner`, `source`, or `strict`; Claude Code refuses to parse the file
   without them. Validate the JSON after editing.
3. **`install.sh`** — add/remove the bare skill name in the matching `GROUP_*`
   variable (`GROUP_ONBOARDING`, `GROUP_DEV`, `GROUP_MISC`). The installer expands
   these into `-s` flags; the CLI has no native group support, so this list must
   mirror the manifest.
4. **`README.md`** — the skills **table** (`| **group** | \`name\` | … |`).

If you add a whole new group, also add it to `ALL_GROUPS` in `install.sh` and add
a new plugin entry (with `source`/`strict`/`skills`) to the manifest's `plugins`.

## Checklist

- [ ] Skill body contains no project-specific terms (Rule 1)
- [ ] Any project-specific facts it relies on are added to each target repo's `CLAUDE.md`
- [ ] `skills/<name>/SKILL.md` created/removed
- [ ] `.claude-plugin/marketplace.json` updated + valid JSON
- [ ] `install.sh` `GROUP_*` (and `ALL_GROUPS` if a new group) updated
- [ ] `README.md` table updated
