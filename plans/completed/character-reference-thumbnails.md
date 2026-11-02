# Character reference thumbnails
Status: active
Related issue/specification: User request for mode and image identity faithful previews.

## Goal
Make per-view source thumbnails match the images used for a new Draft or Final
render across the five active local character pipelines. Show mode and candidate
identity where available; retain candidate-specific historical references.

## Current behavior
Assembly and Dressing thumbnails use the run's saved source snapshot, while
mode-aware render preparation resolves current inputs. In the reported Assembly
batch, saved sources are Draft Body F-006 and Head F-007; Final render hashes
match the current locked Final Body F-012 and Head-Image-Edit F-048. Shared
presentation is in `local_asset_pipeline.js`; source resolution belongs to
`LocalImagePipelineWorkflowService` and its pipeline adapters.

## Implementation packets
### WP1 — Project current previews
- Dependencies: none.
- Files/interfaces: `local_image_workflow_service.py`,
  `local_character_asset_pipeline_service.py`,
  `local_character_asset_pipeline_router.py`.
- Work: expose view/mode source metadata through the existing mode resolver;
  extend the source image route with optional `render_mode`, preserving the
  saved-snapshot path when omitted. Report Final input errors without fallback.
- Acceptance: preview metadata and served bytes identify the same sources as
  `CharacterRenderSlots.prepare_input` for Assembly/Dressing.
- Validation: disposable isolated projection/route checks; no production data.
- Status: complete.

### WP2 — Render labels and audit all pipelines
- Dependencies: WP1.
- Files/interfaces: `local_asset_pipeline.js` and focused renderer adapters as
  needed for candidate identity metadata.
- Work: use mode-resolved previews for Assembly/Dressing. Show role separately
  from `Mode/ID`; preserve uploaded-source labeling and frozen candidate refs.
  Audit Body-Reference, Head-Image and Head-Image-Edit labels and byte sources.
- Acceptance: Final Assembly FRONT shows Head `Final/F-048`, Body `Final/F-012`;
  mode changes and source/lock changes refresh the displayed preview.
- Validation: disposable pipeline display checks.
- Status: complete.

### WP3 — Documentation and final verification
- Dependencies: WP1–WP2.
- Files: `Docs/COMPONENTS/LOCAL_CHARACTERS.md`; update `Docs/CODE_MAP.md` only
  if implementation ownership changes.
- Work: record behavior and observed validation; complete and archive this plan.
- Acceptance: documentation matches source behavior and validation results.
- Validation: `npm.cmd run test:e2e -- --grep "character-to-costume"`;
  `git diff --check`.
- Status: complete.

## Constraints
No serialized run migration, live AI generation, new dependencies, or permanent
test scenarios. Keep unrelated working tree changes untouched. S2 and diff checks
are authorized by the request.

## Progress and decisions
- Initial source audit confirmed Assembly's saved Draft thumbnails diverge from
  its frozen Final render references; current Final lock hashes match F-012/F-048.
- The external page was inaccessible to the web tool; local run and asset records
  provided the diagnosis.

## Final results
- Added mode keyed preview metadata for Assembly/Dressing, an optional mode-aware
  source-image route, and separate role plus `Mode/ID` labels in the shared UI.
- Updated Local Characters documentation. Ownership stayed in the existing
  shared workflow service, pipeline adapter and page controller, so the code map
  required no change.
- Python compilation and JavaScript syntax checks passed. The approved S2 command
  completed all four existing fast E2E scenarios (41.0 seconds); `git diff
  --check` passed with line-ending normalization warnings only.
- The E2E fixture does not exercise the production Tsaeytte library. No live
  generation or production-library writes were performed; route/UI byte agreement
  against changed or unavailable production locks remains unverified.
