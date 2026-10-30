# Story scene ordering and final-assembly previews
Status: complete
Related issue/specification: none

## Goal
Add persistent scene-card ordering and selected final-assembly previews to the Narrative story page.

## Current behavior
Story order is `NarrativeStory.scene_ids`. The story detail GET returns scene records in that order, while the Stories overview separately resolves each scene's selected final assembly. The story page currently renders scene title and intent only.

## Desired behavior
Scene cards show selected final-assembly previews when available and can move earlier/later with immediate persistent ordering. Reordering validates that submitted IDs exactly match the current story membership.

## Impact analysis
NarrativeSceneService owns story mutation and story summaries; the existing story PATCH route and `narrative.js`/`narrative.css` own the API/UI. Update Narrative component documentation. No storage migration, dependency, permanent test or live AI call.

## Invariants and constraints
Keep scene IDs stable; persist only an exact permutation under the repository lock. Use the same selected-assembly and finished-image resolution as the Stories overview. Preserve the existing user edits in Narrative docs and prompt service.

## Implementation steps
### WP1 — Persist scene order
- Dependencies: none.
- Files/interfaces: `zet/services/narrative_scene_service.py`, existing `PATCH /api/narrative/stories/{story}`.
- Work: Validate submitted `scene_ids` as an exact permutation and persist atomically under the repository lock.
- Acceptance: Valid reorder reloads in its new order; malformed/mismatched membership is rejected without a write.
- Validation: Disposable checks using isolated temporary Narrative storage.
- Status: complete.

### WP2 — Add final-assembly preview data
- Dependencies: none.
- Files/interfaces: `zet/services/narrative_scene_service.py`, story GET response.
- Work: Share selected final-assembly resolution between story detail and Stories overview.
- Acceptance: Scene detail summary has a nullable preview descriptor consistent with the overview.
- Validation: Disposable checks for selected and absent assemblies.
- Status: complete.

### WP3 — Update cards and verify
- Dependencies: WP1 and WP2.
- Files/interfaces: `zet/web/static/narrative.js`, `zet/web/static/narrative.css`, Narrative component documentation.
- Work: Render linked, lazy-loaded finished-image previews; add accessible adjacent move buttons, boundary states, save-before-reorder, local failure feedback and focus preservation.
- Acceptance: Repeated moves persist; boundary controls and previews remain correct; failed save retains card order and keyboard focus.
- Validation: Approved E2E baseline, JS syntax and `git diff --check`; disposable browser checks if feasible without adding permanent tests.
- Status: complete.

## Validation
Observed: `npm.cmd run test:e2e` passed all four approved scenarios (40.6s).
`node --check zet/web/static/narrative.js`, `python3 -m py_compile
zet/services/narrative_scene_service.py zet/web/narrative_router.py`, and
`git diff --check` passed. No permanent tests or dependencies were added.

## Progress and decisions
The Stories overview's selected final assembly is the preview source of truth.

## Final results
Story order now validates exact scene membership under the repository lock. Story
detail responses and the Stories overview share final-assembly resolution. The story
page renders selected final assemblies and accessible move controls with immediate
persistence, boundary handling, save-before-move and focus retention. The temporary
`ZZZ` marker in the user-edited JavaScript separator was restored to a middle dot.
