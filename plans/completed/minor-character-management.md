# Minor Character management controls
Status: active

## Goal
Expose Rename and Delete on the Minor Characters overview and Asset Container. Deleting a workspace retains published Inventory images and their references.

## Current behavior
Rename is supported through a name input inside collapsed Container Settings. `DELETE /api/minor-characters/{sid}` already deletes private files, but rejects published assets with recorded usage and archives published assets otherwise. The overview has no management actions.

## Implementation steps
### WP1 - Visible rename controls
- Dependencies: none.
- Files/interfaces: `minor_characters.js`, `index.html`, `minor_character_service.py`.
- Work: Provide a shared rename dialog on overview and container. Save through revision and template hash checked PATCH. Keep page route stable. Avoid invalidating image source prompts for name-only changes.
- Acceptance: Rename works from both entry points, handles duplicates, and refreshes names.
- Validation: Disposable browser journey and `node --check`.
- Status: complete.

### WP2 - Preserve Inventory publications
- Dependencies: none.
- Files/interfaces: `entity_library_service.py`, `minor_character_service.py`.
- Work: Stage each publication's verified bytes in Inventory storage and atomically detach its current lock owner while retaining its asset ID and associations.
- Acceptance: Published Inventory images resolve with their existing IDs after workspace deletion.
- Validation: Disposable catalog fixture including a recorded usage.
- Status: complete.

### WP3 - Preview and confirm deletion
- Dependencies: WP2.
- Files/interfaces: `minor_character_router.py`, `minor_character_service.py`, `minor_characters.js`, `index.html`.
- Work: Add a revision-fenced preview for each selected or locked image. Require approved effect IDs and token on delete. Refuse active work and stale approvals. Refresh overview after success.
- Acceptance: Cancellation leaves workspace intact. Stale approval fails with a fresh preview. Confirmed deletion removes workspace files and retains Inventory images.
- Validation: Disposable API and browser journey, including a failed publication staging operation.
- Status: complete. Stale revision and active-work checks are enforced server-side.

## Knowledge and validation
Update the Minor Character component, library component, code map, and approved testing notes with observed disposable and baseline validation. Do not add permanent scenarios.

## Final results
Visible Rename and Delete controls are available from the overview and container. Existing PATCH naming enforces uniqueness and revision/hash checks. Deletion requires a preview token and approval for each affected selection or lock, blocks active jobs, and retains published Inventory assets and references. Python compilation, JavaScript syntax, `git diff --check`, and the four approved E2E scenarios passed. The E2E baseline does not exercise these controls, and dedicated disposable API coverage of failure recovery remains unverified.
