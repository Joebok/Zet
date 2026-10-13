"""CLI for the isolated layer-integration follow-up experiment."""
from __future__ import annotations

import argparse
import json
import secrets
import sys

from zet.services.scene_layer_integration_followup import SceneLayerIntegrationFollowup


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Repair and review layer integration in an isolated run.")
    subs = parser.add_subparsers(dest="command", required=True)
    create = subs.add_parser("freeze", help="copy and hash parent-run evidence")
    create.add_argument("--run-id", default=None)
    for name in ("prepare", "status"):
        cmd = subs.add_parser(name)
        cmd.add_argument("run_id")
    luna = subs.add_parser("luna", help="ask Luna to review one preparation bundle or final image")
    luna.add_argument("run_id")
    luna.add_argument("item_id", help="scene slug for preparation, or Scene-Slug:SEED for a final")
    review = subs.add_parser("review", help="start the local confirmation page")
    review.add_argument("run_id")
    review.add_argument("--host", default="127.0.0.1")
    review.add_argument("--port", type=int, default=18548)
    args = parser.parse_args(argv)
    try:
        run_id = getattr(args, "run_id", None) or f"layer-integration-v2-{secrets.token_hex(4)}"
        service = SceneLayerIntegrationFollowup(run_id)
        if args.command == "freeze":
            manifest = service.freeze()
            print(f"Frozen parent {manifest['parent_run_id']} as {run_id} at {service.root}")
        elif args.command == "prepare":
            for scene, path in service.prepare().items():
                print(f"{scene}: {path}")
        elif args.command == "status":
            print(json.dumps(service.status(), indent=2))
        elif args.command == "luna":
            print(json.dumps(service.luna_review(args.item_id), ensure_ascii=False, indent=2))
        elif args.command == "review":
            from zet.scripts.scene_layer_integration_review_server import serve
            serve(run_id, host=args.host, port=args.port)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

