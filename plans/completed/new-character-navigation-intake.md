# New Character navigation and intake
Status: complete
Related issue/specification: user request

## Goal
Make New > Character open the intake on Character Overview and place Species and Gender Presentation in the normal intake form flow.

## Current behavior
The header action opens the modal directly. When another page is active, the modal belongs to hidden Character Overview and blocks the dashboard. Species and gender are grouped inside a fieldset.

## Desired behavior
Navigate to Character Overview before opening the create wizard. Keep the guarded transition, close the wizard before leaving Overview, and present create metadata as required form rows.

## Impact analysis
Browser behavior is owned by `zet.js`, `character_wizard.js`, and `index.html`. Operator guidance lives in `Docs/CHARACTER_WIZARD_GUIDE.md`. API/storage contracts do not change.

## Invariants and constraints
Preserve editor guard behavior, edit-mode omission of create-only metadata, and current species/gender field names and options. Use the isolated fast E2E fixture.

## Implementation steps
### WP1 — Navigate before opening the create wizard
- Dependencies: none.
- Files/interfaces: `zet/web/static/zet.js`, `Docs/CHARACTER_WIZARD_GUIDE.md`.
- Work: navigate to onboarding after guarded transition; open only on successful active-page navigation; surface failures; close the wizard before a successful transition away from onboarding; correct the operator guide.
- Acceptance: New > Character from another dashboard page opens visibly on Character Overview; editor cancellation and browser Back do not leave an invisible modal blocking input.
- Validation: disposable Chromium fixture checks and approved `npm.cmd run test:e2e`.
- Status: complete.

### WP2 — Integrate metadata fields into the intake
- Dependencies: none.
- Files/interfaces: `zet/web/templates/index.html`, `zet/web/static/character_wizard.js`.
- Work: render species and presentation as regular form rows after phase; show/enable them in create mode and hide/disable them in edit mode; bump changed script cache versions.
- Acceptance: create choices remain required and edit submission omits these inputs.
- Validation: disposable Chromium form checks and `node --check` for changed scripts.
- Status: complete.

## Validation
Run the requested browser checks against the isolated fast fixture, the approved E2E baseline, JavaScript syntax checks, and `git diff --check`.

## Progress and decisions
The issue reproduced on Costumes in Chromium. The modal was open but invisible because its parent page was hidden.

## Final results
New Character now navigates to Character Overview before opening the wizard. The modal closes before navigation away. Species and Gender Presentation render as regular create-mode rows and remain excluded from edit submissions. Updated the operator guide and JavaScript cache versions.

Validation passed: disposable Chromium checks confirmed navigation from Costumes, visible intake, aligned fields, required create choices, edit-mode omission, and dialog closure on browser Back. `node --check` passed for both changed JavaScript files. `npm.cmd run test:e2e` passed all four approved scenarios. `git diff --check` passed. Dirty-editor cancellation and direct New-button launch while already on Overview were not separately exercised in the disposable browser check. The existing guarded transition remains in the New-button path.
