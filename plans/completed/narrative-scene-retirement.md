# Retire Scene Builder and integrate Narrative Scenes
Status: complete
Related specification: Joe's approved implementation plan, 2026-10-12.

## Goal and boundaries
Make Narrative the dashboard story workflow. Migrate eight First Day and twenty
Phlan Adventures scenes from the current V5 Moonsea copies. Preserve final image
bytes as independent library assets; reconstruct editable backdrop/subscene/assembly
inputs from individual visual reviews. Preserve existing Narrative stories, original
libraries, other legacy stories, and saved 3D data. Archive the empty Collision draft.
No generated jobs, prompts, selections or invented assembly layers in migrated stubs.
No new tests, dependencies, live dispatch, or external publications.

## Current behavior and impact
Narrative has independent services, /api/narrative and NarrativeStories storage.
The dashboard and Candidates still use StoryService/Scene Builder. Shared render
registry imports geometry even for Narrative. Entity usage discovery only scans
*.scene.json, not Narrative scene.json. V5 contains 28 final PNGs not registered in
the entity catalog, plus a blank Collision draft. Exact front adventure costume
reference currently resolves to an archived asset. Three celestial scenes share a
candidate ID and must remain distinct.
Documentation owners: Architecture, Data Model, Invariants, Code Map, Narrative,
Library, Scene Builder, Testing, README/Tutorial where affected; ADR for retirement.

## Luna-sized work packets
Each packet is sequential, single-agent, and excludes unrelated cleanup.

| Packet | Files/interfaces and work | Dependencies | Acceptance / validation | Status |
|---|---|---|---|---|
| WP1 | Plan, migration inventory, archive manifest: sources/order/hashes/references/IDs | none | read-only 8+20 scenes / 28 finals | complete |
| WP2 | Narrative models/repository/scene service: provenance and logical bindings | WP1 | compatible records; S1/S3 | complete |
| WP3 | Entity usages / Narrative legacy-image endpoint / preservation | WP2 | checksum/idempotency/deletion checks in disposable storage | complete |
| WP4 | Migration service and CLI: prepare/dry-run/apply/resume/verify, stable IDs/journal | WP1-3 | no dry-run writes; recoverable reruns | complete |
| WP5 | First Day eight individually reviewed image briefs | WP1/4 format | required targets and image-reviewed staging | complete |
| WP6 | Phlan first ten image briefs in story order | WP5 | visual review and reference issues | complete |
| WP7 | Phlan remaining ten image briefs | WP6 | 28 complete briefs; celestial scenes distinct | complete |
| WP8 | Narrative Candidates service/router/config/index: parsing, import, review, passed state | WP2/4 | repeat import; multi-associations; safe source changes | complete |
| WP9 | Narrative JS/CSS/template: mount/unmount, legacy-image panel | WP2/3 | listener/polling lifecycle; S1/S3 | complete |
| WP10 | Dashboard shell/routes/task context/Candidates integration | WP8/9 | navigation/history/universe; S1/S3 | complete |
| WP11 | Adventure Log Project_Instructions.md: Narrative import guidance | WP8 | semantic Markdown remains compatible; no Drive writes | complete |
| WP12 | Zines/discovery/index/summaries: Narrative and read-only legacy references | WP3/8/10 | finals discoverable; stubs not completed | complete |
| WP13 | Render registry/app/harvester/recovery: detach geometry and fence old work | WP12 | no new old jobs; S2/S3 | complete |
| WP14 | Offline 3D archive, backend retirement and narrow compatibility readers | WP13 | no runtime archive imports; recovery manifest | complete |
| WP15 | Remove obsolete dashboard controls / Three.js dependency | WP10/14 | baseline E2E; diff check | complete |
| WP16 | Backups, migration apply/verify, docs/ADR, plan completion | all | two stories / 28 scenes / 28 immutable image bindings; rerun adds nothing | complete |

## Validation and rollback
Run existing npm.cmd run test:e2e only; repair navigation without expanding scenarios.
Use migration verifier and manual disposable checks for uncovered contracts. Do not
run the live scenario. Review git diff --check and final diff. Back up destination
catalog and affected stores with dashboard stopped before real apply. Keep source
files untouched; archive copies and migration journal identify added records/assets.
Only migration-owned output may be rolled back; preserve subsequent user edits.

## Progress and decisions
- Planning inspection completed; no earlier creative-data changes.
- Joe selected current V5 authored scenes, excluding the blank Collision draft.
- Stable logical costume bindings; direct assets for other imported references.
- Legacy images do not become selected Narrative candidates or completed assemblies.
- Missing references remain visible review issues, never obsolete-view substitutions.
- Changed candidate sources are explicitly reviewed, never silently applied.

## Final results
- Implemented the dashboard Narrative workflow, Candidates import/review, legacy image bindings, reference/usage protection, downstream consumers and retirement fences.
- Migrated First Day (8) and Phlan Adventures (20); all 28 legacy PNG checksums verified. Every migrated scene has backdrop/subscene/assembly targets and no generated jobs, prompts, candidate selections or layers.
- Actual resume left every Narrative JSON byte unchanged and created no additional legacy assets.
- Existing Narrative Phase 1 Test (3 scenes) and both original source story folders are byte-identical to their pre-migration backup. Both passed choices were retained.
- Backup: `C:\Users\Joe\Projects\Zet_Library_v5\Moonsea\backups\narrative-migration-20261012T134525Z`.
- `npm.cmd run test:e2e`: all 3 approved scenarios passed (23.9 s), using existing installed tools; no new maintained tests/scenarios and no live rendering.
- Active Python source parsed (184 files), JS syntax checks passed, affected-doc local links resolved, and `git diff --check` passed.
- Read-only dashboard acceptance: migrated legacy image loaded at original 1024x1536 dimensions under both scene buttons in the left column; Stories/Candidates/Zines navigation; 11 candidate briefs; three celestial associations; legacy URL mapping; no legacy panel on an ordinary existing scene; retired mutation returned HTTP 410; no browser page errors.
- Disposable checks verified interrupted candidate import resume, repeat-import idempotency, source-review preservation of authored inputs/target bytes, Narrative usage guard and scene deletion preserving legacy image.
- Remaining intentional stub issues: five managed-image PNGs unavailable despite recovering their historical records; the adult adventure-gear front reference points to an archived image. Per-scene visual/prose review notes remain visible.
- Documentation and ADR 0005 synchronized. Three.js runtime/build helper and dedicated legacy modules retained in the offline archive.
- Unrelated concurrent AGENTS dependency guidance, Kanban configuration, and `Scripts/ensure-e2e-tools.mjs` / pretest hook changes were preserved and are not part of this retirement implementation.
- Dashboard restarted on its original host/port (0.0.0.0:8081).

- WP1–15 implemented sequentially. Three approved E2E scenarios passed after repairing shared UI dependencies (23.7 s).
- Disposable migration applied and rerun: 2 stories / 28 scenes / 28 checksum-matching images, no duplicates.
- Five managed image records were recovered read-only from old-library Git, but their PNGs are absent from both working files and Git; review issues remain.
- Shared character wizard image picker remains active outside retired Scene Builder panels.
- WP16 completed after actual apply/resume, byte-preservation checks, dashboard inspection and documentation synchronization.
