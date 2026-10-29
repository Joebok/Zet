# Scene text in Narrative final assemblies
Status: complete (2026-10-29)
Related specification: approved scene-text implementation plan in this chat.

## Goal and behavior
Add ordered editable scene-text entries to final assemblies, manually placed on raw composites and independently adjusted/confirmed on rendered candidates. Support restricted nested bold/italic markup, fixed-size wrapping with overflow errors, straight/no tails, draggable tip/attachment, box movement/resizing, keyboard nudges and full-viewport/fullscreen editing. Universe settings supply font/shape/background; stories have field overrides and reset, with no scene overrides. Confirmed PNGs are local post-render artifacts; original artwork never changes.

## Current ownership and interfaces
Narrative models/repository own backward-compatible defaults and target JSON. NarrativeSceneTextService owns draft revisions, candidate placements, preview and Confirm and select. SceneText style/render services own installed font validation, inheritance, restricted markup and Pillow overlays. Narrative router exposes target scene-text actions and finished-image retrieval; generation selection/locking checks confirmations. Assembly snapshots freeze raw seeds without including text in AI images. Finished sources and NARRATIVE references share finished_path for thumbnails/discovery/zines. See ADR 0037 and Docs/COMPONENTS/NARRATIVE.md.

## Constraints
One agent; no permanent tests, dependency additions, model calls, normal-library writes or deployment. Preserve old records and source/finished bytes. Server owns artifact paths. Workflow locks, revision/source tokens and atomic writes fence confirmation. New outputs precede pointer updates; a failed write leaves the preceding confirmed pointer usable. Old output revisions are retained until protected candidate deletion.

## Luna-sized packets
All implementation packets complete; validation limits are recorded below.

| Packet | Dependencies | Files/interfaces | Acceptance and validation |
| --- | --- | --- | --- |
| WP1 Style | none | scene_text_style_service, UniverseService, Narrative story | Validated universe/story settings and four-face installed fonts; style preview/save exercised in disposable Chromium. |
| WP2 Persistence | WP1 | narrative models/repository, narrative_scene_text_service | Stable entries, normalized geometry, revision fences and old-record defaults; disposable Python persistence/stale-save checks passed. |
| WP3 Rendering | WP1-2 | scene_text_render_service | Shared restricted-markup renderer, shapes/tails and fixed-size overflow; disposable Python checks and rendered-image inspection passed. |
| WP4 HTTP | WP2-3 | narrative_router, ZetApp | Draft/preview/confirmation/finished actions delegate to services; disposable actual API journey passed. |
| WP5 Style UI | WP1,4 | scene_text.js, zet.js, index.html | Universe/story dialogs, inheritance/reset, installed families and shared raster preview; universe save/preview exercised, story reset source-inspected. |
| WP6 Entries | WP4-5 | scene_text.js, narrative.js | Add/edit/delete/reorder, emphasis, tail choice, revision save and local errors; raw authoring and candidate checks passed. |
| WP7 Placement | WP3-4,6 | scene_text.js/css | Draw/move/resize, tail controls, image-bound coordinate mapping, keyboard and fullscreen; Chromium drag/keyboard/fullscreen/viewport checks passed. |
| WP8 Final outputs | WP4,7 | generation/assembly/author services, StoryReferenceService | Placement seeds, confirmation/locking and shared finished resolver, retained originals/revisions and protected cleanup; disposable confirmation/PNG/lock and original-byte checks passed. |
| WP9 Integration | WP1-8 | affected Docs and ADR 0037 | Existing baseline, disposable checks, syntax and diff review passed; no permanent test expansion. |

## Validation and observed results
- `npm.cmd run test:e2e`: final run passed all four scenarios, 42.2s. An earlier run failed S1/S3 due to an invalid await in a synchronous browser handler; corrected and both subsequent complete runs passed.
- `python3 -B test-results/scene-text/contracts.py` with repository PYTHONPATH: passed persistence/reload, stale save/confirmation, formatting/shapes/overflow, retained finished output and original-byte preservation.
- `npm.cmd exec -- playwright test --config test-results/scene-text/playwright.config.mjs`: final disposable journey passed, 7.8s including startup. Includes candidate dragging, save, keyboard resize, fullscreen exit, tablet/narrow image bounds, confirmation, finished PNG, lock and style preview/save. Fixed an initial disposable config working directory and an actual delayed-preview status race found during this check.
- Changed Python AST checks, JavaScript syntax checks, actual Chromium module loading and `git diff --check`: passed. Git emitted line-ending normalization warnings for appended documentation; no whitespace errors.
- Inspected formatted bubble and candidate-editor screenshots under ignored test-results/scene-text.

## Limits and final results
Implementation is local and complete. No physical touch/pen device, fullscreen-denial simulation, exhaustive write-failure/concurrency injection or live render was used. Story field reset and protected artifact cleanup were source-inspected rather than covered by a new maintained scenario. Existing S1/S3 provide baseline regressions; they do not prove every new contract. No production data changed. Documentation owners updated: Narrative, data model, invariants, architecture, code map, Testing and ADR index.
