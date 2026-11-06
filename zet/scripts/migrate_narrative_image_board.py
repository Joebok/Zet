"""Dry-run by default; convert legacy Narrative target boards with backups."""
import argparse
from pathlib import Path
import shutil
from datetime import datetime, timezone

from zet.repositories.narrative_repository import NarrativeRepository
from zet.services.library_reference_service import read_library_json, write_library_json

ACTIVE = {"SUBMITTING", "QUEUED", "RUNNING", "DISPATCHING", "TRANSFERRING", "RECONCILING"}


def plan(record, references):
    candidates = record.get("candidates", {})
    ordered = []
    for cid in (record.get("final_selected_id"), record.get("selected_id")):
        if cid in candidates and cid not in ordered:
            ordered.append(cid)
    for mode in ("final", "draft"):
        for cid in record.get("final_slots" if mode == "final" else "slots", []):
            if cid in candidates and candidates[cid].get("locked") and cid not in ordered:
                ordered.append(cid)
    for cid in references:
        if cid in candidates and cid not in ordered:
            ordered.append(cid)
    if len(ordered) > 8:
        raise ValueError("More than eight selected, locked or referenced images.")
    for mode in ("final", "draft"):
        for cid in record.get("final_slots" if mode == "final" else "slots", []):
            if cid in candidates and cid not in ordered:
                ordered.append(cid)
    kept = ordered[:8]
    if any(job.get("status") in ACTIVE for job in record.get("jobs", {}).values()):
        raise ValueError("Active work must settle before conversion.")
    selected = next((cid for cid in (record.get("final_selected_id"), record.get("selected_id")) if cid in kept), None)
    locked = next((cid for cid in (record.get("final_selected_id"), record.get("selected_id")) if cid in kept and candidates[cid].get("locked")), None)
    if locked is None:
        locked = next((cid for cid in kept if candidates[cid].get("locked")), None)
    return kept, selected, locked


def migrate(library_root, apply=False):
    repo = NarrativeRepository(library_root)
    files = sorted(repo.root.glob("*/*/*/target.json"))
    if not files:
        raise ValueError(f"No Narrative target records under {repo.root}. Pass the universe folder, not its parent library folder.")
    reports = []
    with repo.lock():
        records = [(path, read_library_json(path, repo.library_root)) for path in files]
        serialized = {path: path.read_text(encoding="utf-8") for path in repo.root.rglob("*.json")}
        for path, record in records:
            if record.get("board_version") == 2:
                continue
            ids = set(record.get("candidates", {}))
            refs = {cid for cid in ids if any(cid in data for other, data in serialized.items() if other != path)}
            try:
                kept, selected, locked = plan(record, refs)
            except ValueError as exc:
                reports.append({"target": str(path.relative_to(repo.root)), "blocked": str(exc)})
                continue
            removed = sorted(ids - set(kept))
            reports.append({"target": str(path.relative_to(repo.root)), "kept": len(kept), "removed": len(removed)})
            if not apply:
                continue
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup = repo.library_root / "NarrativeBoardBackups" / stamp / path.relative_to(repo.root).parent
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(path.parent, backup)
            record["slots"] = kept + [None] * (8 - len(kept))
            record["selected_id"] = selected
            record.pop("final_slots", None)
            record.pop("final_selected_id", None)
            record["board_version"] = 2
            for index, cid in enumerate(kept, 1):
                record["candidates"][cid]["slot"] = index
                record["candidates"][cid]["locked"] = cid == locked
            removed_records = {cid: record["candidates"].pop(cid) for cid in removed}
            write_library_json(path, record, repo.library_root)
            for cid, candidate in removed_records.items():
                for relative in (candidate.get("image"), candidate.get("scene_text_final", {}).get("image")):
                    if relative:
                        file = (path.parent / relative).resolve()
                        if not file.is_relative_to(path.parent.resolve()):
                            raise ValueError("Invalid candidate image path.")
                        file.unlink(missing_ok=True)
                lettering = (path.parent / "lettering" / cid).resolve()
                if lettering.parent != (path.parent / "lettering").resolve():
                    raise ValueError("Invalid lettering artifact identity.")
                if lettering.is_dir():
                    shutil.rmtree(lettering)
    return reports


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("library_root", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        reports = migrate(args.library_root, args.apply)
    except ValueError as exc:
        parser.exit(1, f"Conversion stopped: {exc}\n")
    if reports:
        for report in reports:
            print(report)
    else:
        print("No legacy Narrative targets need conversion.")
