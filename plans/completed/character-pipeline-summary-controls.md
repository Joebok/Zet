# Character pipeline summary controls and review
Status: complete
Related issue/specification: User request in Codex conversation

## Goal
Improve Batch actions access, view ordering, summary image review, lock labels, and lock icon colors across all five character pipeline pages. No API, storage, or render scheduling changes.

## Current behavior
The shared dashboard markup has a clipped `<details>` Batch actions menu. `local_asset_pipeline.js` orders view cards, but view navigation uses the raw list. Summary image review reads nonexistent `review_cards` although the projection returns `selected_cards`. Summary and selected-view cards use redundant selected/locked labels. See `Docs/CODE_MAP.md` and `Docs/COMPONENTS/LOCAL_CHARACTERS.md`.

## Implementation steps
### WP1 — Batch actions dialog
- Dependencies: none.
- Files/interfaces: `zet/web/templates/index.html`, `zet/web/static/local_asset_pipeline.js`, `zet/web/static/zet.css`.
- Work: Replace dropdown with dialog; dismiss on action selection; keep rename until Save or Cancel; show comparison/master reports outside dialog.
- Acceptance: Dialog is keyboard dismissible, returns focus, fits narrow screens, closes before action confirmation, and failures/cancellations remain visible.
- Validation: disposable browser check; `node --check zet/web/static/local_asset_pipeline.js`.
- Status: complete.

### WP2 — Ordered summary review and labels
- Dependencies: WP1.
- Files/interfaces: `zet/web/static/local_asset_pipeline.js`, `zet/web/static/zet.css`.
- Work: Apply FRONT, FRONT_LEFT_3_4, FRONT_RIGHT_3_4, LEFT_PROFILE, RIGHT_PROFILE, BACK_LEFT_3_4, BACK_RIGHT_3_4, BACK order to summaries and previous/next navigation; review available summary selected/locked images from `selected_cards`; simplify lock labels and color lock/unlock icons.
- Acceptance: Order is shared across summary cards, view navigation and review navigation; clicked image opens first; only available selected/locked images are cycled; locked status is green; Lock icon green and Unlock icon red.
- Validation: disposable isolated browser checks across five pipeline summaries; S2 E2E; JS syntax check.
- Status: complete.

### WP3 — Knowledge and closeout
- Dependencies: WP1, WP2.
- Files/interfaces: `Docs/COMPONENTS/LOCAL_CHARACTERS.md`, `Docs/CODE_MAP.md`, this plan.
- Work: Document observed behavior and checks; record outcomes and archive the plan.
- Acceptance: Docs match implementation and validation; final diff has no unrelated changes.
- Validation: `git diff --check` and final diff review.
- Status: complete.

## Validation
- `node --check zet/web/static/local_asset_pipeline.js`: passed.
- `npm.cmd run test:e2e -- --grep "character-to-costume"`: all four approved scenarios passed (43.2 seconds); the runner executed the full baseline despite the grep argument.
- `git diff --check`: passed.
- A separate disposable browser check focused on the new dialog and summary interactions was not run. No permanent tests or live inference were added.

## Progress and decisions
- Reports remain on the summary page after dialog dismissal. Rename stays open through Save or Cancel. Unlocked selected cards have no redundant status label.
- Final review found only the requested UI/controller and documentation changes; pre-existing `AGENTS.md` edits were preserved.
