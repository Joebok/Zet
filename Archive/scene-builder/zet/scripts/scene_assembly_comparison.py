"""CLI for the isolated FirstDay scene assembly comparison."""
from __future__ import annotations

import argparse
import secrets
import sys

from zet.services.scene_assembly_experiment_service import (
    SceneAssemblyExperimentService,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the isolated FirstDay scene assembly experiment.")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("freeze", help="snapshot the accepted source inputs into a new run")
    create.add_argument("--run-id", default=None)
    for name in ("prepare", "approve-layouts", "compile", "sheets", "report", "review-help",
                 "export-review", "import-review", "letter", "letter-sheets"):
        command = sub.add_parser(name)
        command.add_argument("run_id")
    render = sub.add_parser("render", help="resume pending render jobs")
    render.add_argument("run_id")
    render.add_argument("--limit", type=int)
    render.add_argument("--smoke-only", action="store_true")
    review = sub.add_parser("review", help="open the local blinded visual-review page")
    review.add_argument("run_id")
    review.add_argument("--host", default="127.0.0.1")
    review.add_argument("--port", type=int, default=18547)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "freeze":
            run_id = args.run_id or secrets.token_hex(8)
            service = SceneAssemblyExperimentService(run_id)
            manifest = service.freeze()
            print(f"Frozen run {run_id} at {service.root}")
            print(f"Scenes: {', '.join(manifest['scenes'])}")
        else:
            service = SceneAssemblyExperimentService(args.run_id)
            if args.command == "review":
                from zet.scripts.scene_assembly_review_server import serve_review

                serve_review(args.run_id, host=args.host, port=args.port)
            elif args.command == "prepare":
                service.prepare()
                print(f"Prepared layouts under {service.root}")
            elif args.command == "approve-layouts":
                service.approve_layouts()
                print("All prepared layouts approved.")
            elif args.command == "compile":
                service.compile()
                print(f"Compiled 72 immutable workflows under {service.root}")
            elif args.command == "render":
                manifest = service.render(limit=args.limit, only_smoke=args.smoke_only)
                complete = sum(status == "COMPLETE" for scene in manifest["scenes"].values()
                               for arms in scene["arm_status"].values() for status in arms.values())
                print(f"Render jobs complete: {complete}/72")
            elif args.command == "sheets":
                for slug, path in service.sheets().items():
                    print(f"{slug}: {path}")
            elif args.command == "letter-sheets":
                for slug, path in service.letter_sheets().items():
                    print(f"{slug}: {path}")
            elif args.command == "report":
                report = service.report()
                print(f"Wrote {service.root / 'report.md'}")
                print(report["recommendation"])
            elif args.command == "review-help":
                print(service.review_help())
            elif args.command == "letter":
                print(service.letter_variants())
            elif args.command == "export-review":
                print(f"Wrote {service.export_review_csv()}")
            elif args.command == "import-review":
                print(f"Imported {service.import_review_csv()} criterion ratings")
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
