---
name: merge-briefing
description: Brief a PR for whoever merges it. Use when asked how risky a PR is to merge, or what to read before merging it.
---

# Merge briefing

A merge asks someone to ship code they have not read, so the briefing is the read that
tells them how hard to look before they do. Eight lines, not a second PR description:

- what was wrong, and who felt it;
- what this changes, in a line;
- **Warranted: yes · larger than the issues · beyond the issues**, with the reason — the
  diff's size and reach weighed against the issues it closes, review rounds' additions
  included, since that is where scope grows;
- the decisions that could have gone the other way — the judgement rows of the
  `agent-ledger` block when the description carries one, read off it rather than
  re-derived;
- **Merge risk: low · moderate · high · very high**, with the reason;
- **Lane: auto · human**, with every reason (below);
- what to look at first, if they read one thing;
- anything else that moves the depth of that read — a check that passed on retry, an
  approval given on an earlier head, a challenge finding weighed and not held.

Then the **recommendation** — merge or hold — with its reason.

## Read the PR

The description, the whole diff, and the **issues** it closes — the ones its description
links (`closes #<n>`, the tracker section). A PR linking none is weighed against its
description, and the briefing says so. A caller that hands you the issues, facts for the
last line, or the recommendation has already done that part: take them as given.

```bash
gh api repos/<OWNER_REPO>/pulls/<PR> --jq '.body, .head.sha'
gh api repos/<OWNER_REPO>/pulls/<PR> -H "Accept: application/vnd.github.v3.diff"
```

## Rate the risk

On blast radius and reversibility, the two things a revert cannot fix:

| Risk | What puts it there |
| --- | --- |
| **Low** | Isolated or additive, a test went red on it, and a revert is a full undo. |
| **Moderate** | Changes behaviour on a path in use, or edits code others share — still fully revertible. |
| **High** | A revert alone no longer restores it: a data migration, a permissions or money path, a job whose runs land while it is live. |
| **Very high** | Effects land before anyone can react — a destructive migration, a send to users, a deletion sweep, a credential rotation. |

Risk is not a recommendation. A low-risk PR with a reviewer still owed recommends
holding; a very-high-risk PR that is green and challenged recommends merging.
The recommendation answers *may this merge*; the risk answers *how long to look first*.

With no recommendation handed to you, recommend merging when every check is green, no
review thread is unresolved and no reviewer is still owed on this head; otherwise hold,
naming what is owed.

## The lane

Whether this head could have merged with no human read. A record, on every briefing:
the merge question goes out the same whichever it says, and the answer to that question
is what merges. The record is what a later decision to merge unattended is measured
against.

The gate settles the mechanical half. Read **Guarded paths** from the repo's *Workflow
skills config* (`AGENTS.md` or `CLAUDE.md`) — the regexes naming what always takes a
human there: migrations, payment code, permission classes — and hand them to it:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/skills/merge-briefing/scripts/lane-gate.sh" <OWNER_REPO> <PR> '<guarded paths, comma-separated>'
```

**auto** needs all four: `gate=pass`, **Warranted: yes**, **Merge risk: low**, and a
recommendation to merge. Otherwise **human**. A config with no **Guarded paths** line is
`human — no guarded paths configured`: a repo opts in by naming them.

Done when the line reads `auto`, or `human` with every reason that put it there — the
gate's, then the briefing's own.

## Write it into the PR description

So whoever merges from GitHub reads what the chat got. A caller that owns the PR's rounds
has settled this; asked directly, print the briefing and offer the write.

It is a block of its own at the top of the body: a
`## 🤖 Merge briefing · <head sha, 7 chars>` heading, the eight lines, then the
recommendation, between `<!-- agent-merge-briefing:start -->` and
`<!-- agent-merge-briefing:end -->`. Read the body fresh at write time, so an edit made
meanwhile survives:

```bash
gh api repos/<OWNER_REPO>/pulls/<PR> --jq .body > body.md
# replace the region between the markers, or prepend the block when they are absent
gh api -X PATCH repos/<OWNER_REPO>/pulls/<PR> -F body=@body.md
```

Done when the body holds one briefing block, its heading names this head, and the rest of
the description reads as it did. A failed write is reported, never fatal.
