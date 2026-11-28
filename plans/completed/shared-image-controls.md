# Consistent image reference and zoom controls
Status: complete
Related request: fullscreen zoom and reference-input glyph consistency.

## Goal and current behavior
Fullscreen zoom and some reference inputs are inferred as Information by
`image_card_ui.js`. Candidate Board review uses text Zoom In, Zoom Out and Reset
Zoom buttons. `image_input.js` already owns acquisition controls; Inventory is
available only when a workflow supplies an adapter. Narrative, Minor Character
and reconstruction have separate Inventory actions or source controls.

## Impact and constraints
Presentation owners: `image_card_ui.js`, `image_input.js`, `review_image_zoom.js`,
Candidate Board, dashboard shell, and active workflow adapters. Documentation:
Dashboard UI, UI style guide and code map. Keep persistence, universe ownership,
explicit imports and Save element behavior. No production writes, dependencies,
permanent scenarios, retired workflows or task-evidence Inventory linking.
Preserve the earlier local reference-thumbnail fix.

## Work packets
### WP1 - Shared presentation
- Dependencies: none.
- Files: shared image helpers, Candidate Board, fullscreen shell and templates.
- Work: share labeled zoom controls matching review; explicitly decorate input
  actions with distinct supported icons in every context; refresh cache versions.
- Acceptance: fullscreen, standalone and review zoom have the same labels and
  behavior; Paste/Choose/Inventory never become Information after rescanning.
- Validation: JS syntax and disposable isolated Chromium checks, including zoom.
- Status: complete.

### WP2 - Reference acquisition adapters
- Dependencies: WP1.
- Files: `image_generation.js`, `minor_characters.js`, `narrative.js`, index template.
- Work: use the common toolbar for reconstruction; expose the shared Inventory
  picker for Minor Character sources and Narrative element references.
- Acceptance: active reference inputs expose three acquisition choices; Inventory
  ingestion exposes Paste/Choose only. Existing import/save boundaries hold.
- Validation: disposable Chromium checks and relevant existing workflow scenarios.
- Status: complete.

### WP3 - Validation and knowledge
- Dependencies: WP1 and WP2.
- Files: Docs/COMPONENTS/DASHBOARD_UI.md, Docs/UI_STYLE_GUIDE.md, Docs/CODE_MAP.md.
- Work: document shared owners and behavior, record observed checks and inspect diff.
- Acceptance: checks pass without normal-library or live AI writes.
- Validation: approved `npm.cmd run test:e2e`, `git diff --check`, disposable checks.
- Status: complete.

## Validation and risks
Approved scenarios do not directly assert glyph paths or every reference toolbar.
Use disposable checks for those gaps. Clipboard checks use prepared images, not
physical-device clipboard permission evidence. Do not auto-import Inventory
selections or change locked/generated records.

## Progress
- Confirmed missing action inference and explicit input-icon decoration.
- Used an `inventoryButton` adapter rather than replacing workflow pickers.
  Existing handlers, source semantics and import/save boundaries are retained.
- Shared zoom styling preserves the Candidate Board's labeled text controls;
  fullscreen and standalone controls use the same order and labels.
- Disposable Chromium checks passed all three groups (15.0s): distinct SVGs
  surviving rescans; real file-picker/clipboard/Inventory paths and reconstruction
  source saving; both wizard toolbars and Inventory ingestion exceptions;
  dashboard/standalone/Candidate Board zoom, narrow toolbar bounds; Minor
  Character and Narrative picker preservation. Initial disposable failures were
  test setup errors (collapsed disclosure and an incorrect picker selector),
  corrected without changing application behavior.
- Screenshot inspection found the global hover style washed out fullscreen
  Reset Zoom text. Added an explicit dark hover treatment and a disposable check.
- `npm.cmd run test:e2e` passed all 20 approved scenarios (2.3m).
- Final disposable rerun passed all three groups (15.1s), including fullscreen
  hover contrast after the CSS correction. Desktop reference/fullscreen captures
  were inspected, and 390px fullscreen toolbar bounds passed.
- All seven changed JavaScript files passed `node --check`; `git diff --check`
  and final diff review passed. No dependencies or permanent tests were added.
- Live site deployment is outside this local change.

## Final results
Shared image input assigns distinct Paste, Choose and Inventory SVGs. Active
reference workflows use the same toolbar while retaining their existing pickers;
Inventory ingestion and evidence keep their two actions. All full-size viewers
use labeled zoom controls matching Candidate Board review, with readable hover
styles. Affected component, style-guide and code-map documentation is current.
The earlier reference-thumbnail restoration is preserved. No live AI calls or
normal-library writes occurred; physical device clipboard/touch is unverified.
