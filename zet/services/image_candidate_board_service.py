"""Mode-independent, eight-position working image board rules."""

from datetime import datetime, timezone
import math

SLOT_COUNT = 8


def record_render_start(candidate, started_at=None):
    """Begin timing the current render attempt on a persisted candidate."""
    candidate["render_started_at"] = started_at or datetime.now(timezone.utc).isoformat()
    candidate.pop("render_duration_seconds", None)


def record_render_completion(candidate, completed_at=None, duration_seconds=None):
    """Persist worker duration when available, otherwise local elapsed seconds."""
    try:
        if duration_seconds is not None:
            duration = float(duration_seconds)
            if math.isfinite(duration) and duration >= 0:
                candidate["render_duration_seconds"] = round(duration, 2)
                candidate.pop("render_started_at", None)
                return
    except (TypeError, ValueError, OverflowError):
        pass
    started_at = candidate.get("render_started_at")
    if not started_at:
        return
    try:
        started = datetime.fromisoformat(started_at)
        completed = datetime.fromisoformat(completed_at) if completed_at else datetime.now(timezone.utc)
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        if completed.tzinfo is None:
            completed = completed.replace(tzinfo=timezone.utc)
        candidate["render_duration_seconds"] = round(max(0, (completed - started).total_seconds()), 2)
        candidate.pop("render_started_at", None)
    except (TypeError, ValueError):
        return


def allocate(slots, candidates, selected_id, count=1, slot=None, active=()):
    if len(slots) != SLOT_COUNT or type(count) is not int or not 1 <= count <= SLOT_COUNT:
        raise ValueError("Choose between one and eight images on an eight-slot board.")
    if slot is not None:
        if type(slot) is not int or not 1 <= slot <= SLOT_COUNT or count != 1:
            raise ValueError("Choose a slot from 1 to 8.")
        positions = [slot - 1]
    else:
        positions = [index for index, item in enumerate(slots) if item is None][:count]
    if len(positions) != count:
        raise ValueError("Not enough empty slots. Clear a slot to make room.")
    for index in positions:
        item = slots[index]
        if item:
            candidate = candidates[item]
            if candidate.get("status") in active:
                raise ValueError("Wait for this image to finish before replacing it.")
            if candidate.get("locked") or item == selected_id:
                raise ValueError("Clear the protected image with confirmation before replacing it.")
    return positions


def validate_membership(slots, candidates, candidate_id):
    """Return a candidate only when it is still owned by a physical board slot."""
    candidate = candidates.get(candidate_id)
    if candidate is None or candidate_id not in slots:
        raise ValueError("Candidate is no longer in a slot.")
    return candidate


def select(record, candidate_id):
    candidate = validate_membership(record["slots"], record["candidates"], candidate_id)
    locked_id = next((cid for cid in record["slots"] if cid and record["candidates"][cid].get("locked")), None)
    if locked_id and locked_id != candidate_id:
        raise ValueError("Unlock the current image before selecting another candidate.")
    record["selected_id"] = candidate_id
    return candidate


def unselect(record, candidate_id):
    candidate = validate_membership(record["slots"], record["candidates"], candidate_id)
    if candidate.get("locked"):
        raise ValueError("Unlock the current image before deselecting it.")
    if record.get("selected_id") != candidate_id:
        raise ValueError("Only the selected image can be deselected.")
    record["selected_id"] = None
    return candidate


def lock(record, candidate_id):
    candidate = validate_membership(record["slots"], record["candidates"], candidate_id)
    locked_id = next((cid for cid in record["slots"] if cid and record["candidates"][cid].get("locked")), None)
    if locked_id and locked_id != candidate_id:
        raise ValueError("Unlock the current image before locking another candidate.")
    for cid in record["slots"]:
        if cid:
            record["candidates"][cid]["locked"] = cid == candidate_id
    record["selected_id"] = candidate_id
    return candidate


def unlock(record, candidate_id):
    candidate = validate_membership(record["slots"], record["candidates"], candidate_id)
    candidate["locked"] = False
    record["selected_id"] = candidate_id
    return candidate


def remove(record, candidate_id):
    candidate = validate_membership(record["slots"], record["candidates"], candidate_id)
    record["slots"][record["slots"].index(candidate_id)] = None
    del record["candidates"][candidate_id]
    if record["selected_id"] == candidate_id:
        record["selected_id"] = None
    return candidate


def cleanup(root, pending):
    from pathlib import Path
    import shutil

    root = Path(root).resolve()
    for relative in pending:
        path = (root / relative).resolve()
        if path == root or not path.is_relative_to(root):
            raise ValueError("Invalid pending candidate cleanup path.")
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)


def retry_request(record, candidate_id, *, allow_legacy=False):
    candidate = validate_membership(record["slots"], record["candidates"], candidate_id)
    if candidate["status"] != "FAILED" or not (candidate.get("render_request") or
                                                 (allow_legacy and candidate.get("prompt"))):
        raise ValueError("Retry requires a failed candidate with its frozen request.")
    return candidate
