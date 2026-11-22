# Character overview improvements

## Goal
Implement separate image/workspace actions, Base Images template editing, and character plus phase management from the overview. Remove Delete Phase from the shared header.

## Current behavior
The overview renderer is in `zet/web/static/character_hub.js`; overview metadata and thumbnails are owned by `LocalCharacterOverviewService`. Phase archive deletion exists in `LibraryDeletionService` with image confirmation. No whole-character rename or archive operation exists.

## Implementation steps
### WP1 - Overview presentation
- Dependencies: none.
- Files/interfaces: `character_hub.js`, `index.html`, `zet.css`, overview service/router, shared `zet.js` viewer.
- Work: title-only workspace links, image fullscreen action; Base Images summary template edit; overview management controls; remove header Delete Phase.
- Acceptance: independent link/viewer actions and controls remain accessible when collapsed.
- Validation: syntax checks and isolated browser checks.
- Status: partially implemented. Title/image actions, fullscreen route, template edit placement, and phase-delete placement are present.

### WP2 - Character and phase management
- Dependencies: WP1.
- Files/interfaces: focused management service, `ZetApp`, FastAPI routes, library deletion and catalog services.
- Work: scoped rename/archive operations; protect selected/locked images with explicit preview and recheck; preserve related state and update references.
- Acceptance: both scopes rename/archive coherently; stale/busy/unsafe operations leave data untouched.
- Validation: disposable isolated fixture checks for rename, archive, protected images, stale approval, and recovery.
- Status: partially implemented. Rename now checks container activity/publication journals, rewrites structured path references and canonical name/phase labels, preserves catalog aliases, and updates catalog lock paths. Whole-character archive reviews catalog images and refuses active container work. A durable operation journal and stale-preview fencing remain.

### WP3 - Knowledge and final verification
- Dependencies: WP1-WP2.
- Work: update component/data/invariant/code-map documents and add ADR for durable rename behavior; run syntax checks, approved E2E suite and diff review.
- Acceptance: documentation reflects implementation and exact validation results.
- Status: pending.

## Constraints
Do not add permanent tests or dependencies. Keep mutations isolated. Preserve unrelated existing work. Delete archives data.

## Progress and validation
- Added title/image separation, locked-original endpoint, Base Images editor action, and overview management controls; removed the header Delete Phase action.
- Added character/phase rename with a recovery journal, active-container guards, structured path updates and catalog aliases/lock-path updates.
- Added whole-character archive with image confirmation, active-container guard and phase-list recheck; existing phase archive is available from the overview.
- `node --check` passed for `character_hub.js` and `zet.js`; Python AST parsing passed for changed Python modules; `git diff --check` passed.
- First `npm.cmd run test:e2e` run timed out all four scenarios in `beforeEach`. Inspection found `syncResponsiveChrome` still referenced the removed header button, causing a JavaScript runtime exception. After removing it, the approved suite passed 4/4 (42.0s).
- JavaScript syntax checks, Python AST parsing, and `git diff --check` passed. The maintained suite does not directly cover overview rename/archive/fullscreen interactions.
- Disposable checks passed for phase rename, Markdown and structured identity updates, interrupted rename recovery, active-render rejection, whole-character archive, and moved archive folders. These checks used temporary folders/catalogs and no user library data.
- A disposable browser check passed for overview management visibility, template edit visibility while Base Images is collapsed, and title navigation to the matching Asset Container. A second mocked-image browser check passed for opening the shared fullscreen viewer. Temporary test/config files were removed.

## Final results
- The approved E2E baseline passed all four scenarios (42.0s).
- Disposable service/browser checks passed for rename, recovery, active-work rejection, archive behavior, collapsed-state controls, workspace navigation, and fullscreen viewing.
- JavaScript syntax, Python AST parsing and `git diff --check` passed. No permanent scenarios, dependencies, live AI calls or live renders were added.
- Status: complete.
