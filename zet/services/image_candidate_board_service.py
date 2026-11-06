"""Mode-independent, eight-position working image board rules."""

SLOT_COUNT = 8


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
