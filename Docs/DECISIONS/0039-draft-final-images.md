# 0039 - Independent Draft and Final image work
Status: accepted locally
Date: 2026-10-31

## Context
Creative workflows need inexpensive working images and separately selected final
outputs. Earlier images and published Inventory records must remain usable.

## Decision
Render requests freeze their quality, aspect ratio and dimensions. Draft and
Final boards, selections and locks are independent; legacy candidates are Draft.
Dependent requests prefer the requested mode and fall back to the other available
selection or lock. Draft locks are private, while supported Final view locks
publish through the existing Inventory transaction. Existing Inventory entries
are preserved.

Confirmed Draft cleanup clears the chosen workspace, batch or view, including
selected and locked Drafts, fences its matching work and removes owned outputs.
It preserves completed downstream results and independent Inventory copies.
The selective image copy discovers Inventory and locked Final images from
metadata, with confirmed Narrative lettering preferred, and retains the existing
Markdown/text scope.

## Rationale
Selections are useful as working references before final publication. Keeping
mode ownership and submitted inputs explicit permits independent iteration and
retry, while the Inventory catalog remains authoritative for saved images.

## Alternatives and tradeoffs
Inferring quality from filenames cannot establish selection, lock or Inventory
ownership. The selective copy is not a complete database or library backup.
Deleting a Draft used by future work can require a new source selection; already
completed downstream outputs and independently saved copies remain.

## Consequences
New producers must preserve frozen sizing and mode metadata; consumers must
resolve mode preference at handoff and retain frozen reference bytes. Cleanup
must fence late workers and respect ownership. The fast isolated scenarios and
disposable fixture checks cover integration, not live artistic quality.

## Related code and documentation
[Completed plan](../../plans/completed/draft-final-rendering.md),
[Local Characters](../COMPONENTS/LOCAL_CHARACTERS.md),
[Narrative](../COMPONENTS/NARRATIVE.md), [Library](../COMPONENTS/LIBRARY.md),
[Image sizing](../../zet/services/image_sizing_service.py),
[Character slots](../../zet/services/render_slot_service.py),
[Backup manifest](../../zet/scripts/backup_image_manifest.py).
