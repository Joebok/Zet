"""Command-line coordination for the scheduled Codex issue worker; no ZetApp startup."""
import argparse
import json
import sys
import time
from pathlib import Path

from zet.repositories.task_workflow_repository import TaskWorkflowRepository
from zet.services.codex_usage_service import CodexUsageService
from zet.services.github_client import GitHubClient
from zet.services.issue_worker_service import IssueWorkerService
from zet.services.task_report_service import validate_repository


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default="Joebok/Zet")
    parser.add_argument("--state-root", required=True)
    parser.add_argument("--reserve-percent", type=float)
    parser.add_argument("--trusted-user", action="append")
    sub = parser.add_subparsers(dest="action", required=True)
    claim = sub.add_parser("claim")
    claim.add_argument("--worktree", type=Path, default=Path.cwd())
    sub.add_parser("status")
    usage_command = sub.add_parser("usage")
    usage_command.add_argument("--input-file", type=Path, help="Import a just-read Codex app usage-limits result; never an estimated quota.")
    validation = sub.add_parser("validate")
    validation.add_argument("--token", required=True)
    check = sub.add_parser("checkpoint")
    check.add_argument("--token", required=True)
    check.add_argument("--state", required=True, choices=["in-progress", "needs-input", "needs-review", "stopped", "usage-wait"])
    check.add_argument("--message-file", type=Path)
    check.add_argument("--pr-number", type=int)
    recovery = sub.add_parser("recover")
    recovery.add_argument("--token", required=True)
    recovery.add_argument("--confirm-stopped", action="store_true", required=True)
    args = parser.parse_args()
    try:
        store = TaskWorkflowRepository(args.state_root)
        settings = store.get("settings", args.repository, {})
        reserve = args.reserve_percent if args.reserve_percent is not None else settings.get("reserve_percent", 10)
        trusted = args.trusted_user or settings.get("trusted_users", ["Joebok"])
        if not 0 <= reserve <= 100:
            raise ValueError("Reserve must be 0–100 percent.")
        github = GitHubClient(validate_repository(args.repository))
        usage = CodexUsageService(store, reserve)
        worker = IssueWorkerService(github, store, usage, trusted)
        if args.action == "claim":
            if not (args.worktree.resolve() / ".git").is_file():
                raise ValueError("Pickup requires an isolated Git worktree, not the development checkout or production release.")
            result = worker.claim(args.worktree.resolve())
        elif args.action == "usage":
            result = usage.import_reading(json.loads(args.input_file.read_text(encoding="utf-8"))) if args.input_file else usage.refresh()
        elif args.action == "status":
            result = {"claim": store.get("worker", args.repository), "worker": store.get("status", "worker"), "usage": store.get("status", "usage")}
        elif args.action == "recover":
            result = worker.recover(args.token)
        elif args.action == "validate":
            result = worker.validate(args.token)
        else:
            result = worker.checkpoint(args.token, args.state, args.message_file.read_text(encoding="utf-8") if args.message_file else "", args.pr_number)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        if "store" in locals():
            store.put("status", "worker", {"checked_at": time.time(), "state": "error", "error": str(exc)[:300]})
        print(json.dumps({"state": "error", "error": str(exc)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
