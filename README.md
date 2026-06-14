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
npx skills@latest add mattpocock/skills -s caveman,write-a-skill,zoom-out,grill-with-docs,handoff -g -y

# 2. Hoopit's own skills.
npx skills@latest add hoopit/setup -s '*' -g -y
```

> `hoopit/setup` is private — `skills` clones it over git, so make sure your
> GitHub credentials work for git (`gh auth setup-git`, or SSH). The onboarding
> skills below set this up.

> Use `-p` instead of `-g` to install into the current project (`./.claude/…`)
> rather than globally. Drop `-y` to confirm each step interactively.

## Update & remove (the bits you asked about)

```bash
npx skills update          # refresh every installed skill to its latest upstream
npx skills list            # show what's installed and where it came from
npx skills remove <name>   # remove one skill
```

- **Updating** re-clones each source repo and refreshes the skill content. The
  Matt subset updates **directly from his repo**, automatically — no action
  needed on Hoopit's side. Hoopit's own skills update from this repo.
- **Removing skills we delete from the repo:** `npx skills update` detects skills
  that are in your local `skills-lock.json` but **gone from the source repo** and
  offers to delete the local copies. This is **interactive** — it prompts
  *"remove the local copies of these deleted skills?"*. In non-interactive mode
  (`-y` / piped) it warns but skips deletion, by design. So deleting a skill from
  a source repo *propagates* to users on their next `skills update`, with a
  confirmation.

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
