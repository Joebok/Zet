# Unique accessible names for proposal controls
Status: complete

## Goal
Give every dynamic proposal checkbox, review button, and replacement action a unique accessible name so exact-name browser automation can address each item.

## Implementation steps
### WP1 — Template corrections
- Files: `character_asset_container.js`, `local_template_improvement.js`.
- Acceptance: each correction checkbox includes its full-list position and normalized replacement context.
- Validation: correction labels use the returned-list position and replacement text; the E2E baseline passed.

### WP2 — Image and post-render suggestions
- Files: `local_character_prompt_improvement.js`, `local_character_refinement.js`, `image_generation.js`.
- Acceptance: suggestion and nested scope checkboxes identify their parent correction and target.
- Validation: suggestion checkboxes include correction position and content; nested costume scope checkboxes include correction position.

### WP3 — Interview reviews and wizards
- Files: `narrative.js`, `minor_characters.js`, `character_wizard.js`, `zet.js`.
- Acceptance: row actions and replacement actions resolve to a single exact accessible name.
- Validation: Narrative action names include action, field, and row position; pending review names use interview history position. Minor Character and wizard actions include their field or section. Existing interview E2E passed.

### WP4 — Integration and docs
- Update cache versions and dashboard accessibility guidance.
- Updated static script query versions for changed renderers.
- Recorded the naming guidance in the dashboard UI component document.
- `node --check` passed for all nine changed JavaScript files. `npm.cmd run test:e2e` passed all four scenarios (46.5s). `git diff --check` passed.
- Disposable browser fixtures for every review surface were not run. The maintained E2E suite exercised Narrative interview application; other generated names were checked by code inspection.

## Progress
- Confirmed duplicate labels in template correction and interview review renderers.
- Implementation complete. No API payloads or saved review formats changed.
