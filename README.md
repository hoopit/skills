# Hoopit — `setup`

Hoopit's **agent-skills distribution repo**. It carries Hoopit's own skills
(developer onboarding, etc.) and an installer that also pulls a **curated subset
of [mattpocock/skills](https://github.com/mattpocock/skills)** into your coding
agent — without surfacing all of his.

Everything here is installed and managed with the [`skills` CLI](https://skills.sh)
(`npx skills …`), the same tool the wider agent-skills ecosystem uses.

## Install

One command (installs the Matt subset **and** Hoopit's skills, globally):

```bash
curl -fsSL https://raw.githubusercontent.com/hoopit/setup/main/install.sh | bash
```

Prefer to run the steps yourself? They're just two `skills` invocations:

```bash
# 1. Curated subset of Matt Pocock's skills, pulled straight from his repo.
#    Listing them with -s skips the interactive picker — no manual selection,
#    and his other skills are never installed.
npx skills@latest add mattpocock/skills -s caveman,write-a-skill,zoom-out,grill-with-docs,handoff -g -a claude-code -y

# 2. Hoopit's own skills.
npx skills@latest add hoopit/setup -s '*' -g -a claude-code -y
```

> `hoopit/setup` is private — `skills` clones it over git, so make sure your
> GitHub credentials work for git (`gh auth setup-git`, or SSH). The onboarding
> skills below set this up.

### Choosing scope and agents

- **Scope:** `-g` installs globally (user-level, default). Use `-p` for the
  current project (`./.claude/…`). `install.sh` honors `SCOPE=-p`.
- **Agents:** the installer defaults to **`claude-code`** only. Override with
  `AGENTS`:
  ```bash
  AGENTS="claude-code,universal" ./install.sh   # also the generic ~/.config/agents/skills
  AGENTS="" ./install.sh                          # pick agents interactively (TTY only)
  ```

> **Why pin agents?** With `-y` and no `-a`, the CLI installs to **every detected
> agent** on your machine — which can sweep in agents you don't use and emit
> errors like *"PromptScript does not support global skill installation"* (some
> agents have no global skills dir). Pinning `-a` avoids that. To pick from a
> menu instead, drop **both** `-a` and `-y` — but note the interactive picker
> needs a real terminal, so it can't run through the `curl | bash` one-liner.

> **Agent-flag quirks:** `add -a` accepts a comma list (`-a claude-code,universal`).
> `remove -a` does **not** split commas — pass repeated flags
> (`-a junie -a pi`).

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
# Install named skills from a repo (deterministic, no picker)
npx skills@latest add mattpocock/skills -s caveman,handoff -g -y

# Install every skill a repo offers
npx skills@latest add hoopit/setup -s '*' -g -y

# Preview a repo's catalog without installing
npx skills@latest add mattpocock/skills -l

# Pick interactively (omit -s and -y)
npx skills@latest add mattpocock/skills -g
```

`add` is **additive and idempotent**:

- Installing more skills **never removes** ones you already have — to grab extra
  Matt skills later, just name the *new* ones (`-s prototype,diagnose`); you do
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

These five are installed; his other ~24 skills are intentionally left out. To
change the set, edit `MATT_SKILLS` in [`install.sh`](install.sh) (and the manual
command above).

| Skill | What it does |
|-------|--------------|
| `caveman` | Ultra-compressed, low-token communication mode |
| `write-a-skill` | Scaffold new agent skills properly |
| `zoom-out` | Ask the agent for higher-level / broader context |
| `grill-with-docs` | Stress-test a plan against the project's domain docs |
| `handoff` | Compact the current conversation into a handoff doc |

Why a fixed list instead of a "pre-checked" picker: the `skills` CLI can't
control another repo's interactive default selection, and there's no
transitive-dependency mechanism (installing `hoopit/setup` can't pull skills from
Matt's repo for you). Naming the subset with `-s` is the deterministic,
scriptable way to get exactly these and nothing else.

## Hoopit's own skills

Distributed from this repo (installed by step 2 above):

| Skill | Onboards | Files |
|-------|----------|-------|
| `flutter-onboarding` | `hoopit/flutter-app` | [SKILL.md](skills/flutter-onboarding/SKILL.md) · [ONBOARDING.md](skills/flutter-onboarding/ONBOARDING.md) |
| `api-onboarding` | `hoopit/api` | [SKILL.md](skills/api-onboarding/SKILL.md) · [ONBOARDING.md](skills/api-onboarding/ONBOARDING.md) |

Each onboarding skill takes a fresh machine to a working checkout of its project,
cloning the project repo as a **sibling** of wherever you run it
(`../flutter-app`, `../api`).

## Repository layout

```
setup/
├── install.sh                 # one-shot installer (Matt subset + Hoopit skills)
└── skills/                    # distribution layout — what `skills add` discovers
    ├── flutter-onboarding/
    │   ├── SKILL.md
    │   └── ONBOARDING.md
    └── api-onboarding/
        ├── SKILL.md
        └── ONBOARDING.md
```

Skills live under `skills/<name>/SKILL.md` (a layout the `skills` CLI discovers).
That's the *distribution* layout — distinct from the `.claude/skills/<name>/`
*installed* layout the CLI writes into on a consumer's machine.

## Adding a Hoopit skill

1. `mkdir skills/<name>` and write `skills/<name>/SKILL.md` (frontmatter `name` +
   `description`, then the instructions). Add reference files alongside if needed.
2. Commit and push. Users pick it up on their next `npx skills update`.

## Changing the Matt-Pocock subset

Edit `MATT_SKILLS` in [`install.sh`](install.sh) and the manual command in this
README. To preview Matt's full catalog: `npx skills add mattpocock/skills -l`.
