"""Resume a saved Local Body-Reference outside the web server."""

from __future__ import annotations

import argparse
from pathlib import Path

from zet.app import ZetApp
from zet.services.local_body_reference_service import LocalBodyReferenceService


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id")
    parser.add_argument("--config", default="config.toml")
    parser.add_argument("--recover-failed", action="store_true")
    parser.add_argument("--retry-failed-analyses", action="store_true")
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[2]
    app = ZetApp.from_config(project_root / args.config, validate_catalog=False)
    service = LocalBodyReferenceService(app, project_root)
    if args.recover_failed:
        service.recover_failed_batch(args.run_id)
    if args.retry_failed_analyses:
        service.retry_failed_analyses(args.run_id)
    service.execute_run(args.run_id)


if __name__ == "__main__":
    main()
