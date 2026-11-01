# Pipeline reference thumbnails
Status: complete
Related issue/specification: reported Tsaeytte Adult Head-Image Edit batch `20261022_130159_301043`.

## Goal and current behavior
Fix reference thumbnails across Body Reference, Head Image, Head Image Edit,
Character Assembly and Costume Dressing. The shared browser deduplicates references
within the displayed render mode, but the HTTP resolver deduplicates all modes.
Its positional index can therefore serve different bytes from the displayed caption
and hash. Saved render inputs in the reported regenerated front quarters were
verified to contain the selected Final FRONT; rendering itself is outside this fix.

## Desired behavior and impact
Reference URLs identify the owning candidate, its ordered reference index and render
mode. Current-slot references supply view thumbnails; regenerated/reordered slots
and supplemental images retain their actual image numbering. Legacy positional
requests remain scoped to the requested mode (Draft by default).

Affected interfaces: shared local router, workflow service and pipeline controller.
Documentation owners: Local Characters and CODE_MAP. No storage/schema, rendering,
selection, lock or queue changes; preserve existing dashboard edits. References
remain request-universe bound and ordered as saved. No dependencies, permanent
tests, live AI calls or deployment are authorized by this plan.

## Implementation steps
### WP1 — Resolve an identified candidate reference
- Dependencies: none.
- Files: `zet/services/local_image_workflow_service.py`, `zet/web/local_character_asset_pipeline_router.py`.
- Work: move reference resolution behind the workflow service; accept candidate
  identity and mode; validate view/mode/index and unavailable paths. Keep the
  legacy deduplicated lookup for callers without candidate identity.
- Acceptance: all five routes deliver the requested candidate's exact saved input;
  mismatched candidate/view/mode and invalid indexes fail instead of substituting.
- Validation: disposable isolated FastAPI requests with distinct image bytes.
- Status: complete.

### WP2 — Bind shared thumbnails to current candidate inputs
- Dependencies: WP1.
- File: `zet/web/static/local_asset_pipeline.js`.
- Work: retain candidate identity and original reference index through deduplication;
  include identity/mode in thumbnail URLs and limit references to displayed slots.
- Acceptance: mode switches, replacement slots, differing candidate inputs and
  supplemental references show the bytes named by their caption/cache identity.
- Validation: disposable prepared Chromium checks across all five pipeline pages.
- Status: complete.

### WP3 — Validate and document
- Dependencies: WP1/WP2.
- Files: `Docs/COMPONENTS/LOCAL_CHARACTERS.md`, `Docs/CODE_MAP.md`, this plan.
- Work: document reference URL ownership, record checks and archive the plan.
- Acceptance: focused checks and approved fast baseline pass; final diff preserves
  pre-existing UI/CSS changes and contains no library or queue writes.
- Validation: `npm.cmd run test:e2e`, JavaScript/Python syntax, `git diff --check`.
- Status: complete.

## Validation and remaining limits
S2 covers existing Assembly/Dressing generation/publication; thumbnail identity
across modes is a gap covered by disposable checks only. Hosted deployment and
physical-device/browser cache behavior remain unverified until separately exercised.

## Progress and decisions
- Initial diagnosis verified live thumbnail responses return Draft FRONT bytes
  while regenerated Final requests freeze the correct Final FRONT bytes.
- No durable architecture decision or schema change requires an ADR.
- The shared workflow service now owns reference path resolution. Candidate-bound
  requests preserve duplicate/ordered input indexes; mode/view mismatches and
  missing or out-of-library files fail without substituting a different image.
- Polling's reference signature includes mode-specific slot and candidate ownership.
  Existing unrelated controller/CSS/documentation changes were preserved.

## Final results
- `npm.cmd run test:e2e`: four approved scenarios passed (48.4 seconds).
- `python3 -B test-results/thumbnail-check.py` (with repository PYTHONPATH):
  disposable FastAPI checks passed for all five pipelines: exact reference bytes,
  candidate/view/mode/index isolation, duplicate and supplemental input indexes,
  costume forwarding, legacy Draft/Final slot lookup, missing and confined paths.
- `node test-results/thumbnail-browser-check.cjs`: prepared Chromium checks passed
  for all five controllers: decoded images, URL candidate/mode/universe/costume
  identity, original captions, deduplication, mode switches, slot replacement and
  legacy boards. No page errors. Initial harness runs needed an image-input helper
  stub correction; application code did not change in response.
- Python AST and JavaScript syntax checks and `git diff --check` passed.
- Local Characters and CODE_MAP were updated. No maintained tests, dependencies,
  production library/queue writes, live inference or hosted deployment were added.
  Browser checks use prepared responses and do not establish hosted behavior.
