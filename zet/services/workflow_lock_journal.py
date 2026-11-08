"""Recover a workflow record update using the matching SQLite receipt."""
import json
from uuid import uuid4

from zet.services.atomic_file_service import write_json_atomic


def recover(path, library, write):
    journal = path.with_suffix(".inventory-journal")
    if not journal.is_file():
        return
    pending = json.loads(journal.read_text(encoding="utf-8"))
    if library.publication_receipt(pending["operation_id"]):
        write(pending["record"])
    journal.unlink()


def commit(path, library, record, write, change):
    operation_id = uuid4().hex
    journal = path.with_suffix(".inventory-journal")

    def stage():
        write_json_atomic(journal, {"operation_id": operation_id, "record": record})

    try:
        change(operation_id, stage)
    finally:
        recover(path, library, write)
