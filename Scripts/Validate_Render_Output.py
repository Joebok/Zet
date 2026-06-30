#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Advance body-reference jobs when expected render output exists.")
    parser.add_argument("--job-list", required=True)
    args = parser.parse_args(argv)
    path = Path(args.job_list).expanduser()
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = 0
    for job in data.get("jobs", []):
        if not isinstance(job, dict):
            continue
        if str(job.get("task") or job.get("Task") or "") != "body-reference":
            continue
        if str(job.get("status") or job.get("Status") or "").upper() != "READY_FOR_RENDER":
            continue
        expected = str(job.get("expected_output") or job.get("Expected Output") or "").strip()
        if expected and Path(expected).expanduser().exists():
            job["status"] = "READY_FOR_IMAGE_REVIEW"
            job["next_actor"] = "HUMAN"
            job["last_updated"] = now_iso()
            changed += 1
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Jobs advanced to image review: {changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

