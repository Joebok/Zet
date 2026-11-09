# Character Candidate Board integration
Status: complete
Related specification: [Candidate Board](../../Docs/COMPONENTS/CANDIDATE_BOARD.md) and [integration guide](../../Docs/COMPONENTS/CANDIDATE_BOARD_INTEGRATION.md)

## Goal
Adopt the shared Candidate Board for the five Character Asset Container pipelines. Preserve existing workflow actions, API boundaries, and approvals. Move compiled Prompt Preview beside Refresh.

## Current behavior
The five pipelines share [character_asset_container.js](../../zet/web/static/character_asset_container.js), which renders board cards and review into dedicated markup and uses legacy helpers from [candidate_board.js](../../zet/web/static/candidate_board.js). Shared mount/update/dispose and review are implemented in [candidate_board_component.js](../../zet/web/static/candidate_board_component.js). Character APIs remain in [character_asset_container_router.py](../../zet/web/character_asset_container_router.py) and service.

## Desired behavior
Shared component owns Render Controls, eight cards, comparison review, zoom, actions presentation, and candidate saved-input disclosures. Character adapter maps workflow records and actions and sends accepted detail/progress through update. Prompt Preview remains view-specific and appears alongside Refresh.

## Invariants
Preserve universe and container scope, expected revision and slot occupant guards, frozen retry, current-input regeneration, lock publication, protected-effect preview and approval, and active-only polling. Display saved source notices as FYI.

## Implementation steps
### WP1 — Shared comparison evidence
- Dependencies: none.
- Files/interfaces: candidate_board_component.js, candidate_board.js.
- Work: Render candidate and comparison prompt, negative prompt, ordered linked inputs, and provenance through common disclosures. Open links separately and preserve disclosure state.
- Acceptance: Comparison evidence is shown when present and omitted cleanly when unavailable.
- Validation: Disposable browser check.
- Status: complete.

### WP2 — Character adapter
- Dependencies: WP1.
- Files/interfaces: character_asset_container.js and component host markup.
- Work: Normalize records, actions, recipe fields, comparisons, prompt preview, and progress for all five pipelines. Retain existing service calls and bulk approval.
- Acceptance: Existing actions and settings remain reachable exactly once.
- Validation: Static inspection and disposable API/browser checks.
- Status: complete.

### WP3 — Replace duplicate board UI
- Dependencies: WP2.
- Files/interfaces: index.html, character_asset_container.js, narrative.css.
- Work: Mount shared board and dialog. Remove duplicate board/review renderers, listeners, and styles. Put Prompt Preview beside Refresh. Route detail, actions, and compact progress through update; dispose on exit.
- Acceptance: Board and open review update coherently, reject stale data, and preserve review state for unchanged images.
- Validation: Approved S2 and disposable browser checks.
- Status: complete.

### WP4 — Verify and update knowledge
- Dependencies: WP3.
- Files/interfaces: Candidate Board docs, Local Characters, CODE_MAP, Testing.
- Work: Run syntax checks, approved E2E, and diff check. Update docs and archive this plan after recording observed results.
- Acceptance: Existing approved workflow passes and final diff is scoped.
- Validation: `node --check`, `npm.cmd run test:e2e`, `git diff --check`.
- Status: complete.

## Progress and decisions
User clarified Prompt Preview belongs beside Refresh. Shared comparison disclosures include saved prompts and ordered input links. Character view recipes and Costume Dressing settings now render through shared Render Controls. S2 exercises the shared board through Assembly and Dressing.

## Final results
The shared board now owns Character Render Controls, cards, comparisons, review, and zoom. Character API calls, guarded bulk approvals, and polling remain in the existing controller. Prompt Preview appears beside Refresh. The legacy Character card grid and review dialog were removed.

Validation passed with `node --check` for the Character controller, shared component, and S2 scenario, `npm.cmd run test:e2e` (four approved scenarios, 40.9 seconds), and `git diff --check`. Disposable browser checks beyond S2 were not added or run. No live generation was performed.
