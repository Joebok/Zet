# Reject empty Template Improvement saves
Status: complete
Related issue/specification: User request from 2026-11-14

## Goal
Prevent a template review from being reported as saved when it promotes no governing source. Require a changed selection and fresh preview in the dashboard.

## Current behavior
`CharacterContainerTemplateService.accept_review` allowed empty selected IDs, wrote an accepted record with an empty promotion, and the dashboard always reported success. Findings begin unselected in `character_asset_container.js`.

## Desired behavior
Reject empty/no-op promotions with HTTP 409 and no proposal/master mutation. Keep valid repeat acceptance and partial-save recovery. Require checked findings and a fresh changed preview before save. Identify historical accepted empty reviews accurately.

## Implementation steps
### WP1 — Service guard
- Dependencies: none.
- Files/interfaces: `zet/services/character_container_template_service.py`.
- Work: Reject no-op selection under proposal lock and reject repeat acceptance of historical no-op records.
- Acceptance: No-op acceptance leaves the proposal and masters untouched. Valid promotions retain existing conflict and recovery behavior.
- Validation: Disposable checks using isolated test library; existing fast E2E suite.
- Status: complete.

### WP2 — Dashboard and docs
- Dependencies: WP1.
- Files/interfaces: `zet/web/static/character_asset_container.js`, `zet/web/templates/index.html`, `Docs/COMPONENTS/LOCAL_CHARACTERS.md`.
- Work: Gate preview/save buttons on selection and preview state, show historical no-op outcome, update asset version and document behavior.
- Acceptance: Empty selection cannot be previewed or saved; changed selection requires fresh preview; dismissed confirmation does not report success.
- Validation: Disposable browser/API checks, JavaScript syntax check, fast E2E suite.
- Status: complete.

## Final results
The service rejects empty selections and selections whose compiled replacements do not change a source while holding the proposal lock. Repeated acceptance rejects historical accepted records with no promoted source IDs. The dashboard gates preview/save, requires a fresh preview after changing selection, and labels historical no-op acceptance. Updated the controller asset version and Local Characters guide.

Disposable service checks covered both an empty selection and a saved empty preview. Both returned the expected service error without changing proposal bytes or master text. `npm.cmd run test:e2e` passed all four scenarios (46.9 seconds), `node --check zet/web/static/character_asset_container.js` passed, and `git diff --check` passed. Browser-level template review, dismissed-confirmation, prompt preview, and retained-candidate checks were not run because the maintained fast scenarios do not prepare a template-improvement review. No live render was used.
