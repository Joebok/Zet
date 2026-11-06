"""Mode-independent, eight-position working image board rules."""

SLOT_COUNT = 8


def allocate(slots, candidates, selected_id, count=1, slot=None, active=()):
    if len(slots) != SLOT_COUNT or count not in (1, 4):
        raise ValueError("Choose one or four images on an eight-slot board.")
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
