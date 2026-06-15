---
name: setup-statusline
description: Install the team's custom Claude Code status line (directory, git status, model, effort, exact context usage, session token totals). Use when the user asks to set up, install, or fix the Hoopit status bar / statusline.
---

# Set up the Hoopit Claude Code status line

Installs a status line that shows, in order: truncated cwd, git branch + dirty/ahead/behind symbols, model name, effort level, **exact context usage**, and session token totals:

```
…/Hoopit/api master  Fable 5 [medium] (85k/1M) ↑72k ↓45k ↯2.6M
```

## Why a custom script

The `context_window` field Claude Code passes to statusline commands only counts **non-cached** input tokens, so it collapses to ~0 once prompt caching kicks in. This script instead reads the session transcript (`transcript_path` in the payload) and derives:

- **Context used** — `input + cache_read + cache_creation` of the most recent assistant message (the real size of the last request).
- **↑ sent** — session-cumulative *non-cached* input (`input + cache_creation`), i.e. what is billed at full/write price.
- **↓ received** — session-cumulative output tokens.
- **↯ cache** — session-cumulative cache reads (billed at ~10%). Grows very fast during active turns (every API call re-reads the whole context) — values in the millions are normal, not a bug.

Streaming writes several transcript entries per assistant message (same `message.id`, same usage), so the sums dedupe by message id.

> **Glyph width matters.** Keep the RENDER glyphs single-cell. `↯` (U+21AF) is used for cache instead of `⚡` (U+26A1) because `⚡` is **double-width**: terminals draw it 2 columns wide while Claude Code counts it as 1, which desyncs the status bar's redraw and leaves stale characters on screen when a value's length changes.

## Install steps

1. Copy `statusline-command.sh` (in this skill's directory) to `~/.claude/statusline-command.sh` and `chmod +x` it.
2. Merge into `~/.claude/settings.json` (preserve existing keys):

   ```json
   "statusLine": {
     "type": "command",
     "command": "bash /home/<user>/.claude/statusline-command.sh"
   }
   ```

   Use the absolute home path, not `~`.
3. Verify dependencies: `jq`, GNU `tac`, GNU `date -d`, and `grep -P`. The bundled script targets **Linux**; for macOS or Windows apply the adjustments under "OS portability" below.
4. Smoke-test before telling the user it works:

   ```bash
   t=$(ls -t ~/.claude/projects/*/*.jsonl | head -1)
   echo "{\"workspace\":{\"current_dir\":\"$PWD\"},\"transcript_path\":\"$t\",\"context_window\":{\"context_window_size\":200000},\"model\":{\"display_name\":\"Test\"},\"effort\":{\"level\":\"medium\"}}" \
     | bash ~/.claude/statusline-command.sh
   ```

   Expect a single line ending with the `(used/max) ↑… ↓… ↯…` segments.
5. The status line appears on the next render — no restart needed if the session was launched after `settings.json` already had a `statusLine` entry; otherwise restart Claude Code.
6. **Final output (required).** After the install steps succeed, end your turn by printing the explanation block below verbatim — this is the only thing the user sees that tells them what each new segment in their status bar means, so do not skip it, summarize it, or fold it into other text. Print it after any other completion notes.

   ```
   Status line segments (left to right):
   - …/parent/dir — current working directory, truncated to the last two path segments (home shown as ~).
   -   branch — current git branch. Followed by status glyphs:
       ? untracked,   modified,   merge conflict, ⇡N ahead of upstream, ⇣N behind upstream.
   -  Model — the active Claude model's display name (e.g. Fable 5, Opus 4.8).
   - [effort] — reasoning effort level (low / medium / high / max).
   - (used/max) — real context usage of the last request: input + cache reads + cache writes,
     vs. the model's context window. Unlike Claude Code's built-in counter, this stays accurate
     after prompt caching kicks in.
   - ↑sent — session-cumulative non-cached input tokens (fresh input + cache writes).
     This is what you're billed at full/write price.
   - ↓recv — session-cumulative output tokens.
   - ↯cache — session-cumulative cache reads (billed at ~10%). Grows fast during active turns
     because every API call re-reads the whole cached context; millions are normal.
   ```

## Customising the look — DATA vs RENDER

`statusline-command.sh` is split into two blocks, separated by banner comments:

- **DATA** — computes every value (accurate context usage, session token totals, git facts) and exports them as shell variables. This is the reason the skill exists; **keep it verbatim**.
- **RENDER** — turns those variables into the displayed string (order, separators, colour, glyphs, truncation). Pure presentation.

To restyle the status line — e.g. to mirror your shell prompt — edit **only the RENDER block**. The DATA block already hands you everything as plain variables (the full contract is in the script header):

| Variable | Meaning |
|---|---|
| `cwd` | absolute current directory |
| `model` / `effort` | model display name / reasoning effort (may be `""`) |
| `ctx_used` / `ctx_max` | real context tokens of last request / context-window size |
| `tok_sent` / `tok_recv` / `tok_cache` | session cumulative sent / received / cache-read |
| `git_branch` | branch name / short SHA (`""` if not a repo) |
| `git_untracked` / `git_modified` / `git_conflict` | `0`/`1` flags |
| `git_ahead` / `git_behind` | integer commit counts |

`format_k` (defined in the RENDER block) formats an integer as `26k` / `1.2M`.

### Using the built-in `/statusline` agent to format

Claude Code's built-in `/statusline` generates a status line that mirrors your shell prompt. You can let it own the *formatting* while this skill owns the *data*:

1. Install this skill's script (Install steps above).
2. Run `/statusline` and instruct the agent:

   > Edit **only** the RENDER block of `~/.claude/statusline-command.sh` to match my shell prompt. Do not touch the DATA block. Read every value from the variables it exports (`cwd`, `git_branch`, `git_ahead`, `ctx_used`, `ctx_max`, `tok_sent`, `tok_recv`, `tok_cache`, …) — never recompute them, and never read context size from the raw payload, which is inaccurate under caching. Also render the token (`↑ ↓ ↯`) segments in a style consistent with the prompt, keeping every glyph single-cell (no double-width glyphs like `⚡`).

The agent rewrites presentation only; the accurate numbers still come from the untouched DATA block. Caveat: the agent won't invent the `↑ ↓ ↯` token segments on its own — your shell prompt has no equivalent — so the instruction above tells it to. That's the one thing the built-in formatter can't infer.

## OS portability

The script in this directory is written for **Linux** (GNU coreutils) — keep it that way. When installing on another OS, adjust the *installed copy* (`~/.claude/statusline-command.sh`), not the version in this skill.

### macOS

BSD userland lacks several GNU tools the script uses:

- `tac` — install `coreutils` (`brew install coreutils`) and substitute `gtac`, or replace `tac "$file"` with `tail -r "$file"`.
- `date -d "$ts" +%s` — substitute `gdate -d` (coreutils), or use BSD syntax: `date -j -f '%Y-%m-%dT%H:%M:%S' "${last_ts%%.*}" +%s`.
- `grep -qP` — BSD grep has no `-P`; the pattern (`^.M`) doesn't need PCRE, so change it to `grep -qE`.
- macOS ships bash 3.2; the script avoids 4+ features, so no change needed there. `jq` still needs installing (`brew install jq`).

### Windows

Claude Code on native Windows can't run a bash script directly. Two options:

- **Git Bash** (simplest): point the statusLine command at Git's bash with a Windows path, e.g.
  `"command": "C:\\Program Files\\Git\\bin\\bash.exe C:\\Users\\<user>\\.claude\\statusline-command.sh"`.
  Git Bash bundles GNU coreutils (`tac`, `date -d`) and grep with `-P`, but **not `jq`** — install it (e.g. `winget install jqlang.jq`) and make sure it's on PATH for non-interactive shells. The `transcript_path` in the payload is a Windows path (`C:\Users\...`); Git Bash usually handles it in `[ -f ... ]` and `jq` args as-is, but if not, convert it with `cygpath -u` right after extracting it.
- **WSL**: works unchanged (it's Linux), but only if Claude Code itself runs inside WSL. A native-Windows Claude Code calling into WSL bash will hand over Windows transcript paths that need `wslpath -u` conversion and adds noticeable per-render latency — prefer Git Bash for native installs.

In both cases the home-directory tilde shortening (`${dir/#$home/~}`) and the `…/` path truncation work on the POSIX-style paths bash sees; expect the directory segment to show a `/c/Users/...`-style prefix on Windows unless converted.

## Caveats

- **Never edit `~/.claude/statusline-command.sh` in place during a live session.** The status bar re-runs it every few seconds and will execute a half-written file, flashing garbage values. Build the new version in a temp file and `mv` it into place atomically.
- **Claude Code itself briefly paints low token values** right after a message is submitted from an idle state, before the next script render lands. This is harness-side (verified by logging every render — script output was always correct), self-corrects within seconds, and cannot be fixed in the script.
- The git status symbols include Nerd Font glyphs (` `, ` `). If the user's terminal font lacks them, substitute plain characters like `!` and `=`.
- The numbers measure different things and are **not** expected to satisfy `context = ↑ + ↓`. The useful invariant is roughly `context ≈ ↑ + prefix cached by an earlier session` (system prompt and project context are often cache-shared across sessions, so the first call reads tokens this session never paid to write).
