# Hoopit — `skills`

Hoopit's **agent-skills distribution repo**. It carries Hoopit's own skills
(developer onboarding, etc.) and an installer that also pulls a **curated subset
of [mattpocock/skills](https://github.com/mattpocock/skills)** into your coding
agent — without surfacing all of his.

Everything here is installed and managed with the [`skills` CLI](https://skills.sh)
(`npx skills …`), the same tool the wider agent-skills ecosystem uses.

## Install

Both commands install the curated Matt subset **and** Hoopit's skills globally
into Claude Code.

> `hoopit/skills` is **private**, so the installer is fetched with `gh`
> (authenticated) rather than a plain `curl` of the raw URL — an unauthenticated
> raw fetch returns `404` for private repos. Make sure `gh` is installed and
> you're logged in (`gh auth login`).

**All skills:**

```bash
gh api repos/hoopit/skills/contents/install.sh -H "Accept: application/vnd.github.raw" | bash
```

**Everything except the onboarding group:**

```bash
gh api repos/hoopit/skills/contents/install.sh -H "Accept: application/vnd.github.raw" | EXCLUDE_GROUPS=onboarding bash
```

(See [Skill groups](#skill-groups) for `SKILL_GROUPS` / `EXCLUDE_GROUPS`.)

Prefer to run the steps yourself? They're just two `skills` invocations:

```bash
# 1. Curated subset of Matt Pocock's skills, pulled straight from his repo.
#    Pass one -s per skill in MATT_SKILLS (see install.sh); -s skips the
#    interactive picker so his other skills are never installed.
npx skills@latest add mattpocock/skills -s <skill> [-s <skill> …] -g -a claude-code -y

# 2. Hoopit's own skills.
npx skills@latest add hoopit/skills -s '*' -g -a claude-code -y
```

> `hoopit/skills` is private — `skills` clones it over git, so make sure your
> GitHub credentials work for git (`gh auth setup-git`, or SSH). The onboarding
> skills below set this up.

### Choosing scope and agents

- **Scope:** `-g` installs globally (user-level, default). Use `-p` for the
  current project (`./.claude/…`). `install.sh` honors `SCOPE=-p`.
- **Agents:** the installer defaults to **`claude-code,universal`**. The
  `universal` target makes skills **symlinked** instead of copied — the CLI keeps
  one real copy in `~/.agents/skills` and points `~/.claude/skills/<skill>` at it
  (one update point, no duplication). With a single agent there's no shared
  store, so the CLI writes copies. Override with `AGENTS`:
  ```bash
  AGENTS="claude-code" ./install.sh               # Claude Code only — copies, no symlinks
  AGENTS="" ./install.sh                          # pick agents interactively (TTY only)
  ```

> **Why pin agents?** With `-y` and no `-a`, the CLI installs to **every detected
> agent** on your machine — which can sweep in agents you don't use and emit
> errors like *"PromptScript does not support global skill installation"* (some
> agents have no global skills dir). Pinning `-a` avoids that. To pick from a
> menu instead, drop **both** `-a` and `-y` — but note the interactive picker
> needs a real terminal, so it can't run through the `curl | bash` one-liner.

> **Agent-flag quirks:** neither `-a` nor `-s` splits a comma list anymore — a
> value like `claude-code,universal` is treated as one literal name and matches
> nothing (*"Invalid agents…"* / *"No matching skills…"*). Pass **repeated
> flags**: `-a claude-code -a universal -s caveman -s handoff`. `install.sh`
> expands its comma-separated `AGENTS`/skill lists into repeated flags for you.

## Managing skills — `add` / `remove` / `update`

All skill management goes through the [`skills` CLI](https://skills.sh). The
commands below assume `npx skills@latest …` (run without installing anything
globally). Common flags:

| Flag | Meaning |
|------|---------|
| `-g` | Global (user-level) scope — install/manage for your whole machine *(this repo's default)* |
| `-p` | Project scope — install/manage into the current repo's `./.claude/…` instead |
| `-y` | Skip all confirmation prompts (non-interactive) |
| `-s <a,b,c>` | Act on these specific skills by name (`-s '*'` = all) |
| `-a <agents>` | Target specific agents (`-a '*'` = all detected); default is auto-detect |
| `-l` | With `add`: list a repo's available skills without installing |

### `add` — install / refresh skills

```bash
# Install named skills from a repo (deterministic, no picker).
# Repeat -s per skill — one -s value is matched as a single skill name,
# so a comma/space list matches nothing.
npx skills@latest add mattpocock/skills -s caveman -s handoff -g -y

# Install every skill a repo offers
npx skills@latest add hoopit/skills -s '*' -g -y

# Preview a repo's catalog without installing
npx skills@latest add mattpocock/skills -l

# Pick interactively (omit -s and -y)
npx skills@latest add mattpocock/skills -g
```

`add` is **additive and idempotent**:

- Installing more skills **never removes** ones you already have — to grab extra
  Matt skills later, just name the *new* ones (`-s prototype -s diagnose`); you do
  **not** re-list your existing set.
- The interactive picker starts with **nothing pre-selected**, but that's safe:
  it only installs what you tick — *leaving a skill unchecked does not uninstall
  it*. So when adding more, select only the delta.
- Re-adding a skill you already have just refreshes it (overwrite, with a
  confirmation unless `-y`).

> Personal vs. team: `add`-ing extra skills onto your machine is a **local**
> change. To make the whole team get a skill, edit `MATT_SKILLS` in
> [`install.sh`](install.sh) (Matt's) or add a `skills/<name>/` dir (Hoopit's)
> and commit — see the sections below.

### `update` — refresh to latest upstream

```bash
npx skills update              # update everything in your lockfile
npx skills update caveman      # update specific skills
npx skills update -g           # global skills only   (-p for project only)
```

Re-clones each skill's source repo and refreshes its content. The Matt subset
updates **directly from his repo automatically** — no action needed on Hoopit's
side; Hoopit's own skills update from this repo.

**Propagating deletions:** when a skill is in your `skills-lock.json` but has been
**removed from its source repo**, `update` detects it and **prompts**
*"remove the local copies of these deleted skills?"*. So deleting a skill upstream
flows to users on their next `update`, with a confirmation. In non-interactive
mode (`-y` / piped) it warns but **skips** the deletion, by design.

### `remove` — uninstall skills

```bash
npx skills remove <name>       # remove one skill
npx skills remove a b c        # remove several
npx skills remove -s '*' -g -y # remove all global skills
```

### `list` — see what's installed

```bash
npx skills list                # installed skills + their source repo
npx skills list -g             # global only   (-p for project)
npx skills list --json         # machine-readable
```

## The curated Matt-Pocock subset

A fixed subset of [mattpocock/skills](https://github.com/mattpocock/skills) is
installed; the rest are intentionally left out. The set is defined by `MATT_SKILLS`
in [`install.sh`](install.sh) — edit it there to change what the team gets.

Why a fixed list instead of a "pre-checked" picker: the `skills` CLI can't
control another repo's interactive default selection, and there's no
transitive-dependency mechanism (installing `hoopit/skills` can't pull skills from
Matt's repo for you). Naming the subset with `-s` is the deterministic,
scriptable way to get exactly these and nothing else.

## Hoopit's own skills

Distributed from this repo under `skills/<name>/`, organized into **groups** (see
[Skill groups](#skill-groups)). For the live list and descriptions, browse
[`skills/`](skills/) or run `npx skills add hoopit/skills -l`. Each skill's purpose
is its `SKILL.md` `description`; the grouping lives in
[`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json).

Note: the onboarding skills clone their project repo as a **sibling** of wherever
you run them (e.g. `../api`, `../flutter-app`).

## Skill groups

Groups are declared in [`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json)
as plugins (`onboarding` / `dev` / `misc`). That one file serves both consumers:
the `skills` CLI reads it for the group headers in the **interactive** picker (run
`npx skills add hoopit/skills` with no `-s`/`-y` and toggle by group), and Claude
Code reads it as a **plugin marketplace** (`/plugin marketplace add hoopit/skills`,
then install `hoopit-onboarding` / `hoopit-dev` / `hoopit-misc`). Each plugin uses
`source: "./"` + `strict: false` so its `skills` array is the authoritative list —
no per-plugin directories or `plugin.json` files needed.

**The `skills` CLI has no native group flags** — there is no `--group` and no
`--exclude`; `-s` matches skill *names* only. So non-interactively you either
list skills by name, or use this repo's `install.sh`, which understands groups:

```bash
SKILL_GROUPS="onboarding" ./install.sh                # only the onboarding group
SKILL_GROUPS="onboarding,dev" ./install.sh            # several groups
EXCLUDE_GROUPS="misc" ./install.sh                    # all groups except misc
./install.sh                                          # all groups (default)
```

`install.sh` expands the selected groups into repeated `-s` flags. (The env var is
`SKILL_GROUPS`, not `GROUPS` — the latter is a reserved bash variable.) To do the
same with the raw CLI, name the group's skills yourself — one `-s` per skill.

> **Adding or removing a Hoopit skill?** When working in this repo, Claude has a
> project-local `create-hoopit-skill` skill (under `.claude/skills/`) that
> documents the procedure and the files to keep in sync.
