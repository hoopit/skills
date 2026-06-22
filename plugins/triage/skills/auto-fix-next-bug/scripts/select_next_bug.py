#!/usr/bin/env python3
"""Deterministic selector + claimer for the auto-fix-next-bug loop.

Replaces the old haiku "selector" sub-agent: the selection has no judgment in it
(pick the highest AI: Priority Score, Agent-ready, open, unassigned, undispatched
bug and claim it), so it runs as a plain script — zero LLM tokens, fully testable,
and it prints a single line so the /loop orchestrator's context stays flat.

Multi-project: reads the central triage config (<repo-root>/.claude/triage-config.json,
created by setup-triage). With no --project it ranks agent-ready bugs across **every**
board in the config's `projects` map (one merged JQL, ordered by priority); with
--project <key> it scopes to that one project. Each candidate's branch/PR dedup check
runs in that project's sibling repo under $HOOPIT_ROOT.

Contract — prints EXACTLY ONE line to stdout (diagnostics go to stderr):
  KEY=<KEY> | SUMMARY=<summary> | PRIORITY=<priority>   a bug was claimed
  NONE                                                  nothing eligible right now
  ERROR: <reason>                                       could not select (e.g. auth)

Exit code: 0 for KEY/NONE, 1 for ERROR.

Eligibility: project bug, type=Bug, status=Open, unassigned, AI: Agent Suitability
= Agent-ready, AND not already in the dispatch log, AND no local/remote branch
`<KEY>/*`, AND no open PR with <KEY> in the title. Claim = transition to
"In Progress" + append a `dispatched` line to the dispatch log.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import subprocess
import sys
from datetime import UTC
from datetime import datetime

SKILL = "auto-fix-next-bug"


def warn(msg):
    print(msg, file=sys.stderr)


def emit(line, code=0):
    print(line)
    sys.exit(code)


def run(cmd, cwd=None):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)


def repo_root():
    cp = run(["git", "rev-parse", "--show-toplevel"])
    return cp.stdout.strip() if cp.returncode == 0 else os.getcwd()


def default_config_path(root):
    return os.path.join(root, ".claude", "triage-config.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", help="project key in the config's 'projects' map (e.g. api). "
                                      "Omit to select across ALL boards.")
    ap.add_argument("--config", help="central triage config (default: <repo-root>/.claude/triage-config.json)")
    ap.add_argument("--limit", type=int, default=25, help="max candidate rows to scan")
    ap.add_argument(
        "--dry-run", action="store_true", help="show the pick but do not claim (no transition, no log write)"
    )
    args = ap.parse_args()
    root = repo_root()
    hoopit_root = os.path.dirname(root)

    cfg_path = args.config or default_config_path(root)
    if not os.path.exists(cfg_path):
        emit(f"ERROR: triage config not found at {cfg_path} — run setup-triage first", 1)
    cfg = json.load(open(cfg_path))
    projects = cfg.get("projects") or {}

    # Which project blocks are in scope.
    if args.project:
        if args.project not in projects:
            emit(f"ERROR: project {args.project!r} not in config 'projects' (have: {sorted(projects)})", 1)
        selected = {args.project: projects[args.project]}
    else:
        selected = projects
    # jira project key -> the sibling repo dir its branches/PRs live in.
    prefix_to_repo = {}
    jira_keys = []
    for pkey, block in selected.items():
        jkey = (block or {}).get("jira_project")
        if not jkey:
            continue
        jira_keys.append(jkey)
        prefix_to_repo[jkey] = os.path.join(hoopit_root, pkey)
    if not jira_keys:
        emit("ERROR: no project in scope declares a jira_project — run setup-triage", 1)

    log_path = os.path.join(root, ".claude", "local", SKILL, "dispatched.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    dispatched = set()
    if os.path.exists(log_path):
        for ln in open(log_path):
            ln = ln.strip()
            if ln:
                dispatched.add(ln.split("\t")[0])

    project_clause = jira_keys[0] if len(jira_keys) == 1 else f"({', '.join(jira_keys)})"
    op = "=" if len(jira_keys) == 1 else "IN"
    jql = (
        f"project {op} {project_clause} AND type = Bug AND status = Open AND assignee IS EMPTY "
        f'AND "AI: Agent Suitability" = "Agent-ready" '
        f'ORDER BY "AI: Priority Score" DESC, created ASC'
    )
    cp = run(["acli", "jira", "workitem", "search", "--jql", jql, "--fields", "key,summary,priority", "--csv"])
    if cp.returncode != 0:
        emit(f"ERROR: acli search failed: {cp.stderr.strip()[:200]}", 1)

    rows = list(csv.DictReader(io.StringIO(cp.stdout)))
    if not rows:
        emit("NONE")

    # case-insensitive header lookup
    def col(row, name):
        for k, v in row.items():
            if k and k.strip().lower() == name:
                return (v or "").strip()
        return ""

    for row in rows[: args.limit]:
        key = col(row, "key")
        if not key or key in dispatched:
            continue
        prefix = key.split("-", 1)[0]
        target_repo = prefix_to_repo.get(prefix)
        if not target_repo or not os.path.isdir(target_repo):
            warn(f"skip {key}: no checked-out repo for project {prefix} (looked in {target_repo})")
            continue
        # existing branch?  (handle-jira-issue branches as <KEY>/bug/...)
        br = run(["git", "branch", "-a", "--list", f"{key}/*"], cwd=target_repo)
        if br.stdout.strip():
            warn(f"skip {key}: branch exists")
            continue
        # open PR with the key in the title?
        pr = run(["gh", "pr", "list", "--state", "open", "--search", f"{key} in:title", "--json", "number"], cwd=target_repo)
        if pr.returncode == 0 and pr.stdout.strip() and json.loads(pr.stdout):
            warn(f"skip {key}: open PR exists")
            continue

        # CLAIM (skipped on --dry-run)
        if args.dry_run:
            warn(f"(dry-run) would claim {key} — no transition, no log write")
            emit(f"KEY={key} | SUMMARY={col(row, 'summary')} | PRIORITY={col(row, 'priority')}")
        tr = run(["acli", "jira", "workitem", "transition", "--key", key, "--status", "In Progress", "--yes"])
        if tr.returncode != 0:
            warn(
                f"{key}: transition to In Progress failed (continuing; dispatch log is the backstop): {tr.stderr.strip()[:160]}"
            )
        ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(log_path, "a") as f:
            f.write(f"{key}\t{ts}\tdispatched\n")
        emit(f"KEY={key} | SUMMARY={col(row, 'summary')} | PRIORITY={col(row, 'priority')}")

    emit("NONE")


if __name__ == "__main__":
    main()
