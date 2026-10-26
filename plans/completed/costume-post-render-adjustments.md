# Costume-Dressing modes and post-render adjustments
Status: complete
Specification: Joe's approved implementation plan in this chat (2026-10-26).

## Goal and decisions
Independent Costume-Dressing views after governing-prompt acceptance; per-view Doll-dressing (w/ Ref), Doll-dressing (no Ref), or Rotate. FRONT retains its existing Assembly-based dressing only. Reference choices are explicit same-batch selections. Four private target-view test renders per adjustment round reuse session seeds. Acceptance criteria persist per costume/view across batches and modes. Costume adjustments edit only the costume Markdown. Other character pipelines retain Character.md adjustments. Retire executable Prompt Generator Pilot while preserving historical records and adopted-image provenance.

## Contracts
One mode preparation/eligibility policy serves slots, previews, staging, runners and publication. Frozen retries do not follow changed settings. Scoped line edits compose existing view tags with optional inline ZET:RENDER_MODES annotations, preserving unchecked contexts. Suggestions favor the target and unselected symmetric mirror; other selected views default unchecked. The operator approves a cumulative diff before tests and explicitly saves the reviewed costume source afterward. Criteria save independently; only unfinished criteria feed analysis. Source/revision conflicts and cancelled/obsolete continuations cannot publish results.

## Impact and constraints
Owners: CostumeRenderModeService, costume compiler and view conditioning, CharacterRenderSlots, local progression/runner/overview/automation, staging, LocalImagePipelineWorkflowService/router, batch controls, CostumeAdjustmentCriteriaService, LocalCostumePostRenderService and post-render workspace, LLM roles/AIWorkflowService, Pilot services/pages/adapters and compatibility provenance readers. Knowledge owners: Local Characters, Prompts, Data Model, Invariants, AI Jobs/LLM Roles, Dashboard UI, Code Map; add an ADR. No new dependencies, permanent tests, live inference or normal-library writes during validation. Preserve universe/queue/attempt fences, ordered image bindings and locked-image integrity.

## Luna-sized packets
Each packet owns its named subsystem, is implemented by the single agent, and remains bounded by the approved specification.

| Packet | Dependencies | Files/interfaces and work | Acceptance / validation | Status |
| --- | --- | --- | --- | --- |
| WP1 | none | CostumeRenderModeService; workflow/router render-settings operations | Persisted modes, legacy defaults, FRONT restriction, input-specific reasons; disposable service checks | complete |
| WP2 | WP1 | Costume compiler, rotation/no-reference services, slots/staging/preview preparation | Identical ordered inputs across entry points; correct rotation instructions; disposable compile parity | complete |
| WP3 | WP1-2 | LocalCharacterAssetPipelineService, progression, overview, Run All Remaining, publication | Independent ready views, frozen retries and actual lineage; disposable run/resume/lock checks | complete |
| WP4 | WP1-3 | local_asset_pipeline.js and dashboard styling | Saved mode/reference controls; three-item staging menu; disposable browser checks | complete |
| WP5 | none | CostumeAdjustmentCriteriaService, workflow/router and costume lifecycle | Cross-batch/mode persistence, statuses, revision fencing, rename/archive; disposable checks | complete |
| WP6 | WP2 | View conditioning/compiler, scoped costume line-edit composer | Preserve unchecked view/mode cells; reject malformed/overlapping edits; disposable compile matrix | complete |
| WP7 | WP5-6 | LocalCostumePostRenderService, LLM roles, post-render dispatch | Frozen evidence, unfinished criteria, scoped suggestions, cumulative diff; prepared responses | complete |
| WP8 | WP3,7 | Costume trials/promotion; AI continuations and image services | Four fixed seeds, selective retries, assessments, explicit recoverable master save; prepared lifecycle checks | complete |
| WP9 | WP4-8 | Existing post-render page/controller/styles | Checklist, scope checkboxes, diff, four trials, refinement/save/reload; isolated browser review | complete |
| WP10 | WP9 | Pilot services/models/pages/routes/adapters/continuations; documentation | Retired jobs terminalize; provenance survives; approved E2E, syntax, diff review | complete |

## Validation
Use verified Python 3, node --check for changed JS, disposable prepared-response service/browser checks, npm.cmd run test:e2e (four approved scenarios), git diff --check and final diff inspection. No new maintained scenarios or live rendering. Record observed outcomes here, then move to plans/completed only after all packets are complete.

## Progress and deviations
- Initial approved E2E baseline after mode integration: four passed in 38.6s. Disposable all-view compilation, scope preservation across 24 view/mode cells, shared criteria, and costume-only four-render/promotion lifecycle passed. No live inference.
- Initial working tree clean. Authoritative code confirms current staging compilers, Character.md-only post-render flow, predecessor gates, and Pilot provenance compatibility dependencies.

## Final results
All ten packets implemented. New services own per-view modes, persistent costume criteria, scoped line edits and costume-only private trials. Shared lifecycle hooks preserve Character.md adjustments for other pipelines. Pilot execution/UI/adapters are removed; raw history and adopted-image provenance compatibility remain.

Observed validation:
- Approved `npm.cmd run test:e2e`: 4 passed after integration (37.8s; 39.6s).
- Final focused approved S2: `node node_modules/@playwright/test/cli.js test --config=playwright.config.mjs --grep character-to-costume`: 1 passed, 13.0s.
- Disposable `checks.py`: all-view mode compiles, 24-cell scope preservation, shared criteria/revisions, two rounds/four fixed seeds, failed render and assessment/selective retries, exact diff gates, earlier image history, costume-only save/replay, unchanged gallery count passed.
- Disposable `compile_checks.py`: production mode-tag compiler matrix/source maps, staging alternatives/failure preservation, existing Character.md review, and costume rename/checklist persistence passed.
- Disposable `edge_checks.py`: circular publication rejection, explicit-source blocking, frozen slot/runner retry after mode input changes, retired continuation fencing and cancelled-session reopening passed.
- Disposable Chromium `browser.mjs`: real mode save/reload, three-item staging menu, scoped review choices, checklist save/reload, four image review, desktop/narrow containment and no page errors passed. Screenshots inspected. Helpers were stopped.
- Python AST checks: 25 changed/new Python files; three changed JS `node --check` invocations; `git diff --check` passed. Existing Git LF/CRLF notices are informational.

No permanent tests, dependencies, live inference, production deployment, or normal-library writes. Live artistic quality and physical-device acceptance remain unverified. All disposable scripts/data/screenshots are ignored under `test-results/costume-adjustments/`.

Integration discoveries resolved: temporary staging outputs cannot receive PipelineCandidates-owned source-cache records; frozen retries must bypass later mode eligibility; same-batch cross-view lineage must reject cycles; shared Character.md analysis needed its role resolver imported after extraction. Independent partial batches rerun only their requested views. Mode filtering runs before costume normalization so excluded instructions cannot affect derived equipment/visibility facts. Existing candidate re-evaluation remains independent of current mode readiness. Documentation owners and ADR 0033 updated.
