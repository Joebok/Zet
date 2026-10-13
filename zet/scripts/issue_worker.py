"""Command-line coordination for the scheduled Codex issue worker; no ZetApp startup."""
import argparse
import base64
import json
import sys
import subprocess
import time
from pathlib import Path

from zet.repositories.task_workflow_repository import TaskWorkflowRepository
from zet.services.codex_usage_service import CodexUsageService
from zet.services.github_client import GitHubClient
from zet.services.issue_worker_service import IssueWorkerService
from zet.services.task_report_service import validate_repository
from zet.services.worker_bridge_client import WorkerBridgeClient


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
    context = sub.add_parser("context")
    context.add_argument("--token", required=True)
    evidence = sub.add_parser("evidence")
    evidence.add_argument("--token", required=True)
    evidence.add_argument("--url", required=True)
    evidence.add_argument("--output", type=Path, required=True)
    delivery = sub.add_parser("deliver")
    delivery.add_argument("--token", required=True)
    delivery.add_argument("--base", default="main")
    delivery.add_argument("--title", required=True)
    delivery.add_argument("--body-file", type=Path, required=True)
    ready = sub.add_parser("ready")
    ready.add_argument("--token", required=True)
    ready.add_argument("--pr-number", type=int, required=True)
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
        repository = validate_repository(args.repository)
        bridge = WorkerBridgeClient.discover(repository, store)
        github = bridge or GitHubClient(repository)
        if bridge:
            bridge.claim_token = getattr(args, "token", None)
        usage = CodexUsageService(store, reserve)
        if bridge:
            usage.read_account = lambda: bridge.request("usage")
        worker = IssueWorkerService(github, store, usage, trusted)
        if args.action == "claim":
            if not bridge:
                raise ValueError("Start the local Zet server with its authenticated worker bridge before pickup.")
            if not (args.worktree.resolve() / ".git").is_file():
                raise ValueError("Pickup requires an isolated Git worktree, not the development checkout or production release.")
            result = worker.claim(args.worktree.resolve())
        elif args.action == "usage":
            result = usage.import_reading(json.loads(args.input_file.read_text(encoding="utf-8"))) if args.input_file else usage.refresh()
        elif args.action == "status":
            result = {"claim": store.get("worker", args.repository), "worker": store.get("status", "worker"), "usage": store.get("status", "usage")}
        elif args.action == "recover":
            result = worker.recover(args.token)
        elif args.action in {"context", "evidence", "deliver", "ready"}:
            claim_record = store.get("worker", repository, {})
            if claim_record.get("token") != args.token:
                raise ValueError("This action does not own the issue claim.")
            if args.action == "context":
                number = claim_record["issue_number"]
                result = {"issue": github.repo_api(f"/issues/{number}"), "comments": github.repo_api(f"/issues/{number}/comments?per_page=100", paginate=True)}
            else:
                if not bridge:
                    raise ValueError("Delivery/evidence actions require the local authenticated Zet worker bridge.")
                payload = {"claim_token": args.token}
                if args.action == "deliver":
                    payload.update(base=args.base, title=args.title, body=args.body_file.read_text(encoding="utf-8-sig"))
                    root = Path(claim_record["worktree"])
                    revision = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
                    branch = subprocess.check_output(["git", "-C", str(root), "branch", "--show-current"], text=True).strip()
                    dirty = subprocess.check_output(["git", "-C", str(root), "status", "--porcelain"], text=True).strip()
                    if branch != claim_record["branch"] or dirty:
                        raise ValueError("Commit the scoped change on the claimed clean branch before draft delivery.")
                    bundle = root / "test-results" / "worker-delivery.bundle"
                    bundle.parent.mkdir(parents=True, exist_ok=True)
                    subprocess.run(["git", "-C", str(root), "bundle", "create", str(bundle), branch, "^origin/" + args.base], check=True)
                    payload.update(bundle=base64.b64encode(bundle.read_bytes()).decode(), revision=revision)
                elif args.action == "ready":
                    revision = subprocess.check_output(["git", "-C", claim_record["worktree"], "rev-parse", "HEAD"], text=True).strip()
                    dirty = subprocess.check_output(["git", "-C", claim_record["worktree"], "status", "--porcelain"], text=True).strip()
                    if dirty or not claim_record.get("validation", {}).get("passed") or revision != claim_record["validation"]["revision"]:
                        raise ValueError("Ready delivery requires the validated clean current revision.")
                    payload["pr_number"] = args.pr_number
                else:
                    payload["url"] = args.url
                result = bridge.request(args.action, payload)
                if args.action == "evidence":
                    output = args.output.resolve()
                    allowed = (Path(claim_record["worktree"]) / "test-results").resolve()
                    if allowed not in output.parents:
                        raise ValueError("Save worker evidence only under the claimed worktree's ignored test-results.")
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_bytes(base64.b64decode(result["content_base64"], validate=True))
                    result = {"path": str(output), "sha256": result["sha256"]}
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
