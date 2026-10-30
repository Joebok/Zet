# Story Animation
Status: active
Related issue/specification: User-approved Story Animation plan (2026-10-30)

## Goal
Add a Narrative story Animation workspace with portable animation instructions, locked assembly snapshots, deterministic standalone HTML playback, and optional AI-assisted instruction proposals. Preserve source artwork and text layers independently.

## Current behavior
Narrative stories persist ordered scenes in `NarrativeStories/`. Candidate locks, selected assemblies, and confirmed lettering are managed by `NarrativeSceneService` and `NarrativeSceneTextService`; `finished_path` resolves the confirmed output. Fast scenarios S1/S3 cover Narrative authoring and scene lifecycle, not animation. AI interviews use `NarrativeGenerationService` and shared AI_Proxy dispatch and collection. See `Docs/COMPONENTS/NARRATIVE.md`, `Docs/DATA_MODEL.md`, `Docs/INVARIANTS.md`, `Docs/COMPONENTS/AI_JOBS.md`, and `Docs/Testing.md`.

## Desired behavior
Multiple named animations per story, each with a versioned output-neutral shot/camera/text/transition specification and private content-addressed source snapshots. Deterministically compile that data to an offline self-contained HTML player. A separate optional LLM interview proposes changes for review; it never edits current instructions automatically.

## Invariants and constraints
- Universe/story confinement, atomic persistence, stale revision rejection, locked-source integrity, and confirmation-bound text snapshots.
- Never call models/renderers directly; optional interviews use shared AI_Proxy services.
- No new dependencies, permanent test scenarios, or live model checks without explicit approval. Preserve existing uncommitted edits.
- Existing confirmed overlays may only be separated when their frozen snapshot and original artwork can reproduce the finished image. Flattened legacy lettering remains inseparable.

## Implementation steps
### WP1 — Specification, validation, resolution
- Dependencies: none.
- Files/interfaces: `zet/models/story_animation.py`; `zet/services/story_animation_service.py`.
- Work: define spec v1, validation, deterministic timeline resolution, keyframe evaluation, transitions and defaults.
- Acceptance: two-shot example resolves stable absolute intervals and interpolated states.
- Validation: disposable pure-function checks.
- Status: complete (specification and timeline resolver implemented; compiler uses the resolver).

### WP2 — Persistence and source snapshots
- Dependencies: WP1.
- Files/interfaces: `zet/repositories/story_animation_repository.py`; focused Narrative source/snapshot service.
- Work: atomically persist named animation documents; source locked assemblies, original bytes and independently rendered frozen text layers; deduplicate assets by hash; fence revisions.
- Acceptance: snapshots reload unchanged after source edits/unlocks/deletion; unsupported flattened text is disclosed.
- Validation: temporary-library checks for locks, hashes, text reconstruction, stale writes and path confinement.
- Status: in progress (named records, revision fences, locked source listing and byte snapshots implemented; refresh/history and complete source diagnostics remain).

### WP3 — HTML compiler/player
- Dependencies: WP1/WP2.
- Files/interfaces: `zet/services/story_animation_html_compiler.py`; embedded player runtime resource.
- Work: deterministic offline HTML, canvas layers, camera/text interpolation, overlap transitions and accessible playback controls.
- Acceptance: output opens offline through `file://`, seeks and renders the same state as sequential playback.
- Validation: disposable compiler and Chromium checks; no permanent test additions.
- Status: in progress (standalone HTML player/compiler implemented; browser validation and several playback edge cases remain).

### WP4 — App and API integration
- Dependencies: WP2/WP3.
- Files/interfaces: `zet/app.py`; focused `zet/web/story_animation_router.py`; router registration.
- Work: list/create/read/update, source listing/bind/refresh, preview and HTML export within story scope.
- Acceptance: API round trip and exports are universe/story confined; stale revisions return actionable conflicts.
- Validation: isolated disposable API checks.
- Status: in progress (story CRUD, bind/save, and download endpoints implemented; refresh and preview endpoints remain).

### WP5 — Story Animation workspace
- Dependencies: WP4.
- Files/interfaces: `zet/web/static/story_animation.js`, scoped stylesheet, Narrative mount/navigation templates.
- Work: named animation CRUD, ordered shots, durations/transitions, visual and numeric camera keyframes, subject marks, text opacity controls, preview, save/export.
- Acceptance: author, save, reload, scrub and export without AI; story scene order is unchanged.
- Validation: disposable isolated Chromium journey.
- Status: in progress (story workspace supports basic shot add/remove, duration, single-key framing, transitions, text fade-in, and preview/export; named animation selection, pan keyframes, subject marks, fade-out, reorder/duplicate and scrub remain).

### WP6 — Optional LLM interview
- Dependencies: WP4/WP5.
- Files/interfaces: focused animation interview service; `zet/services/llm_role_service.py`; shared continuation registration; workspace interview panel.
- Work: use shared AI_Proxy, propose schema-validated edits/questions, bind to source/revision snapshot, allow preview/apply/reject, reject stale answers.
- Acceptance: prepared interview proposes a marked-subject zoom; applying is explicit and stale results do not mutate the spec.
- Validation: disposable prepared-response and recovery checks.
- Status: pending (not implemented).

### WP7 — Documentation and integration verification
- Dependencies: WP1–WP6.
- Files/interfaces: Narrative, data model, invariants, architecture, code map, ADR, this plan.
- Work: document ownership, formats, source/text limitations, compiler contract, and evidence; run approved baseline and diff checks; archive only after completion.
- Acceptance: documentation matches implementation and reports validation accurately.
- Validation: `npm.cmd run test:e2e`; `git diff --check`; relevant disposable checks.
- Status: pending (documentation, live feature verification and acceptance are incomplete).

## Progress and decisions
- 2026-10-30: Confirmed story order, locked final assembly candidates, frozen text snapshots, and shared AI_Proxy integration in current source. User chose a timeline/interview workspace, manual subject marking, independent stationary text opacity, dissolves and crossfades, and core silent effects.
- Existing user changes in `zet/web/static/zet.css` and `zet/web/templates/index.html` predate this implementation and must be preserved.
- 2026-10-30: Implemented spec validation/resolution, file-backed animation records, locked candidate snapshots, HTML compilation, basic story page authoring and API routes. Pixel comparison is used to verify independently rendered lettering rather than comparing encoded PNG files.
- 2026-10-30: `npm.cmd run test:e2e` passed all four approved scenarios. Python syntax, JavaScript syntax, a dissolve timing/compiler determinism smoke check, and `git diff --check` passed. New animation UI/API has not received a dedicated browser journey. WP6 is partial; WP7 and documentation/ADR remain outstanding.

## Final results
Incomplete: foundational authoring, storage, resolution, compiler and API are present, but the approved optional LLM interview and full timeline editing requirements remain unimplemented. Keep this plan active.
