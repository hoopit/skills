#!/usr/bin/env python3
"""Idempotent writer for the central triage config (<repo-root>/.claude/triage-config.json).

Merges three layers, **add-missing-only** (an existing non-empty value is NEVER overwritten):

    existing file   (highest priority — keep what's already there)
      ← discovered  (values setup-triage found by scanning repos / Sentry, via --values JSON)
      ← template    (org-level defaults + project skeletons, config.template.json)

"Missing" means absent OR empty (null / "" / []). Dicts are merged recursively; the `projects`
map is merged per project key, then per field. Then it validates required keys and prints a
report: what was added, what was kept, and what is still missing (needs user input).

Usage:
  python3 write_config.py [--out FILE] [--template FILE] [--values JSON] [--dry-run]
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import sys

REQUIRED_TOP = ["jira_base_url", "itsm_project", "sentry_org", "fields", "options", "projects"]
REQUIRED_PROJECT = ["jira_project", "repo", "default_branch"]  # sentry_* may stay null (flagged, not fatal)


def repo_root():
    cp = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    return cp.stdout.strip() if cp.returncode == 0 else os.getcwd()


def is_empty(v):
    return v is None or v == "" or v == [] or v == {}


def fill_missing(dst, src, added):
    """Recursively copy keys from src into dst only where dst is missing/empty. Records dotted paths
    of keys that got filled into `added`. Dicts merge; scalars/lists fill only when empty."""
    for k, sv in (src or {}).items():
        if isinstance(sv, dict):
            node = dst.get(k)
            if not isinstance(node, dict):
                node = {}
                dst[k] = node
            fill_missing(node, sv, added.setdefault(k, {}))
            if not added[k]:
                del added[k]
        else:
            if k not in dst or is_empty(dst.get(k)):
                if not is_empty(sv):
                    dst[k] = sv
                    added[k] = sv


def flatten(prefix, tree, out):
    for k, v in tree.items():
        path = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            flatten(path, v, out)
        else:
            out.append(f"{path} = {v!r}")


def still_missing(cfg):
    miss = []
    for k in REQUIRED_TOP:
        if k not in cfg or is_empty(cfg.get(k)):
            miss.append(k)
    for pkey, block in (cfg.get("projects") or {}).items():
        for k in REQUIRED_PROJECT:
            if k not in (block or {}) or is_empty(block.get(k)):
                miss.append(f"projects.{pkey}.{k}")
        # sentry is optional but worth flagging
        if is_empty((block or {}).get("sentry_project")):
            miss.append(f"projects.{pkey}.sentry_project (optional — Sentry triage skipped for this project)")
    return miss


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="config path (default: <repo-root>/.claude/triage-config.json)")
    ap.add_argument("--template", default=os.path.join(here, "..", "config.template.json"))
    ap.add_argument("--values", help="discovered values as a JSON object (merged above the template)")
    ap.add_argument("--dry-run", action="store_true", help="print the merged config + report, write nothing")
    args = ap.parse_args()

    out = args.out or os.path.join(repo_root(), ".claude", "triage-config.json")
    template = json.load(open(args.template))
    discovered = json.loads(args.values) if args.values else {}
    existing = json.load(open(out)) if os.path.exists(out) else {}

    result = copy.deepcopy(existing)
    added = {}
    fill_missing(result, discovered, added)   # discovered fills gaps in existing
    fill_missing(result, template, added)     # template fills the rest

    added_paths = []
    flatten("", added, added_paths)
    missing = still_missing(result)

    print(f"config: {out}{' (would create)' if not existing else ''}")
    print(f"added {len(added_paths)} key(s):" if added_paths else "added 0 keys (already complete)")
    for p in added_paths:
        print(f"  + {p}")
    if missing:
        print(f"still missing / needs input ({len(missing)}):")
        for m in missing:
            print(f"  ! {m}")

    if args.dry_run:
        print("\n--- merged config (dry-run, not written) ---")
        print(json.dumps(result, indent=2))
        return

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as fh:
        fh.write(json.dumps(result, indent=2) + "\n")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
