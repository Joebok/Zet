# Zet reliability, library scaling, and model qualification

## Summary and execution contract

Remediate the investigation’s failures in small, sequential work packages. Target **ModelUpdater**, as confirmed. Keep authored library files portable; introduce a **rebuildable, machine-local SQLite index** for discovery, search, dependencies, and history.

The repository confirms repeated scene/catalog loading, duplicate summary scans, direct-Ollama runtime overrides, and whole-catalog rewrites. Shared retry and locking utilities already exist. ModelUpdater currently has limited binary fixture scoring and permits comparative quality failures to remain advisory.

**Each package is one implementation assignment:**

- Implement only the named package after its dependencies pass.
- Preserve unrelated changes, authored content, and existing queue tasks.
- Deliver code, focused tests, test commands/results, and a concise handoff identifying remaining work.
- Stop after the package. Do not activate model aliases, publish externally, or perform live destructive migrations without the applicable authorization.
- “Light/local” means a bounded implementation suitable for Sol light or a local coding model; “Medium” means Sol medium. Storage and crash-recovery packages require medium-level review.
- Use existing dependencies and Python’s SQLite support. Do not introduce production dependencies.
- Retain old-format handling only in explicit migration commands. Updated runtime readers must require the current format and give an actionable migration error.

No files were changed and no tests were run during this planning review.

## Reliability work packages

### WP01 — Reproducible regression and performance fixtures
**Executor:** Light/local. **Dependencies:** None.

- Extend existing Zet test fixtures with eight ordered scenes, main/subscene candidates, inherited catalog metadata, and active/completed queue records.
- Add opt-in performance instrumentation for catalog discoveries, scene-document loads, render compiles, file reads, archive traversals, and endpoint duration.
- Generate deterministic 1×, 10×, and 100× datasets from recorded entity counts. Reuse small fixture images; do not duplicate production media.
- Record environment, dataset counts, cold/warm state, and concurrent activity with each benchmark.

**Acceptance:** Repeated generation produces identical logical data; benchmarks use temporary roots and cannot mutate the live library or queue. Existing failures have reproducible regression cases or recorded operation-count baselines.

Handoff:

* New invariants introduced: Reliability fixture roots must be empty before generation; generated logical data uses fixed ordering, identifiers, timestamps, and reusable image bytes; application instrumentation is inactive unless explicitly enabled.
* APIs/contracts changed: `create_app(config_path, performance=None)` accepts an optional `PerformanceInstrumentation`; `collect()` activates bounded operation counters and temporary Path read hooks; service counters use `catalog_discoveries`, `scene_document_loads`, `render_compiles`, `file_reads`, `archive_traversals`, and `endpoint_duration`.
* New tests/fixtures available to later WPs: `tests.support.reliability_fixture.write_reliability_fixture()` creates 1x/10x/100x isolated datasets; `ReliabilityFixture.logical_snapshot()` compares logical output; `tests/test_wp01_reliability.py` covers determinism, scale counts, inherited metadata, queue state, instrumentation, and benchmark reporting.
* Assumptions later WPs may rely on: Eight base scenes are ordered as `scene-001` through `scene-008`; every base scene has a main and `background` subscene candidate; queue fixtures contain one active Ask and one completed Answer at 1x; benchmark output records environment, counts, cold/warm state, and concurrent activity.
* Deviations from master plan: The repository had no shared story reliability fixture or performance instrumentation, so WP01 extended the existing fixture helper with a dedicated reliability module; no production dependency or later work package was started.

### WP02 — Navigation independent of pending requests
**Executor:** Medium. **Dependencies:** WP01.

- Update `zet.js` to attach navigation handlers before awaited startup loading.
- Introduce page/selection generations and `AbortController` handling through the existing fetch helper.
- Change the active page immediately; perform page loading independently. Only the current generation may update data, errors, loading indicators, or selection.
- Replace overlapping summary intervals with completion-scheduled refreshes. Allow at most one summary request per client; pause it while the document is hidden.
- Treat cancellation as cancellation, not an empty result or user-facing error.

**Acceptance:** With review/candidate requests delayed by 120 seconds, another page activates within 250 ms. Late success and error responses cannot alter the new page. Loading, empty, and failed states remain distinct.

Handoff:

* New invariants introduced: Each page activation owns a monotonically increasing generation and `AbortController`; production-review selections have independent per-view generations/controllers; only the current generation may consume a response; request cancellation does not render empty or failed UI; production summary refreshes are completion-scheduled, single-flight, and paused while the document is hidden.
* APIs/contracts changed: `fetchJson(url, options)` now accepts internal `bindToPage` and `pageGeneration` options in addition to standard fetch options and binds ordinary requests to the active page signal by default; `activatePage()` activates chrome before awaiting page data and may supersede an earlier in-flight activation.
* New tests/fixtures available to later WPs: `tests/browser/dashboard.spec.mjs` provides 120-second delayed response gates and regressions for sub-250 ms review/candidate navigation, stale success/error isolation, distinct loading/empty/failed candidate states, single-flight summary refresh, and visibility pause/resume.
* Assumptions later WPs may rely on: WP03 selection routes may use the existing page/selection generation helpers; cancellation preserves the newly requested story/scene context and does not clear editors or emit user-facing failures.
* Deviations from master plan: Primary tab handlers were already attached before startup awaits, so WP02 retained that ordering and added a startup generation guard. The full browser suite still has two unrelated pre-existing failures (`cards` is undefined in the imported-image test, and the AI Queue recent-harvest fixture is not surfaced); the other 24 browser tests pass, so later WPs must not assume the unfiltered suite is green until those fixture/test defects are repaired.

### WP03 — One Scene Builder selection contract
**Executor:** Medium. **Dependencies:** WP02.

- Use one canonical ordered scene collection populated by workspace context.
- Route header selection, arrows, Scenes-page Builder, and workflow navigation through the same selection function.
- Track requested scene separately from the loaded editable document. Disable save/render until their story and scene IDs match.
- Preserve existing unsaved-change protection and render-target context on Builder ↔ Prompt/Analysis ↔ Render Console transitions.
- Make To Do and Template Instruction Manuals activate their intended existing destinations; report an actionable error if loading fails.

**Acceptance:** Direct entry supports all eight scenes; first/last arrows are correct; rapid selection cannot stage the previous scene; browser back/forward and return paths preserve context.

Handoff:

* New invariants introduced: Story workspace context owns one ordered scene collection; requested story/scene identity is tracked separately from loaded scene and Scene Builder documents; same-scene and cross-story requests are cancellable, and stale responses cannot restore prior context; save, rename, move, delete, Builder, and render actions remain disabled until loaded and requested identities match; valid browser route state is written as soon as page chrome activates and carries page, story, scene, and active render target where applicable.
* APIs/contracts changed: Browser navigation uses `selectStoryScene(storySlug, sceneSlug, options)` for header selectors, overview cards/phone arrows, Scenes-page Builder entry, Scene Builder arrows, candidate imports, workflow navigation, Prompt Review returns, and Render Console returns. Invalid explicit scene IDs fall back to the canonical first scene. `activatePage()` supports `fromHistory`/`updateHistory`, updates history before awaited page loading, and reports actionable tab-load errors; workspace-summary and story loading accept the active selection signal.
* New tests/fixtures available to later WPs: The browser fixture now gives Alpha Story eight ordered scenes and supplies a valid harvested-answer manifest. WP03 tests cover all eight scenes, first/last arrows, complete back/forward traversal, late scene-document, Scene Builder, and cross-story responses, disabled mutation controls while loading, invalid-scene fallback, and successful/failed To Do and Template Instruction Manuals navigation. The imported-image test now uses an exact card locator and waits for the completed metadata refresh before continuing.
* Assumptions later WPs may rely on: WP03 acceptance and the previously failing WP02 handoff cases are green. An equivalent full Playwright run using a temporary port-8766 config passed all 33 browser tests on 2026-09-10; the standard `npx playwright test` command could not start locally because an unrelated process already occupied port 8765. `node --check zet/web/static/zet.js` and `.venv\\Scripts\\python.exe -m pytest tests/test_web_app.py` also passed (9 tests). The temporary Playwright config was removed and is not part of the delivered change.
* Deviations from master plan: No backend scene API, production dependency, or WP04 work was added. The existing workspace-summary scene rows remain the browser’s canonical ordered collection, with the scene-list endpoint populating the same collection when the Scenes page loads. The three pre-existing browser failures recorded across the WP02/WP03 handoffs were repaired as prerequisite test/fixture defects rather than deferred again.
* WP02 and WP03 issues should now be fixed.

### WP04 — Remove redundant review and summary work
**Executor:** Medium. **Dependencies:** WP01.

- Separate lightweight pending-candidate discovery from detailed freshness evaluation.
- Check main/subscene candidate paths before loading detailed status or compiling renders. Read a scene’s subscene definitions at most once per discovery pass.
- Introduce a request-scoped discovery context shared by scene, catalog, and summary services.
- Obtain scoped and project totals from one discovered dataset.
- Add process-level single-flight summary computation with a 15-second cache, invalidated by relevant Zet mutations. Browser cancellation alone must not be treated as backend cancellation.

**Acceptance:** Zero-candidate scenes cause zero render compiles. One summary request performs at most one catalog discovery. Concurrent identical summary requests share computation. Counts match review rows for the same snapshot.

Handoff:

* New invariants introduced: Candidate review discovery checks main and subscene candidate paths before detailed status evaluation; a discovery pass loads each scene's Scene Builder data at most once; zero-candidate targets never enter freshness compilation; scoped and project summary counts derive from one discovered dataset; identical summaries single-flight through a 15-second process-local cache; relevant Zet mutations invalidate cached summaries.
* APIs/contracts changed: Added `DiscoveryContext` and `SceneDiscoveryRecord`; `ZetApp.discovery_context()` creates a request-scoped context; scene review listing/status and image-catalog listing accept an optional `discovery_context`; `ScenePromptAnalysisService.pending_keys()` exposes one queue snapshot; `SummaryCache` provides process-local single-flight caching and invalidation.
* New tests/fixtures available to later WPs: `tests/test_wp04_reliability.py` covers main/subscene candidates, zero-candidate compile suppression, shared catalog/scene discovery, concurrent summaries, snapshot count parity, and mutation invalidation. WP01's `write_reliability_fixture()` remains the isolated 1x/10x/100x dataset source; `Scripts/Benchmark_WP01.py` records the operation counters used during validation.
* Assumptions later WPs may rely on: WP04 acceptance is PASS. Focused validation passed with 34 tests, and the isolated WP01 benchmark completed for 1x/10x/100x cold and warm runs. Backend work continues if a browser request is cancelled; browser cancellation is not propagated as backend cancellation.
* Deviations from master plan: None.

### WP05 — Durable manual-render publication
**Executor:** Medium. **Dependencies:** WP01.

- Route publication through a focused backend service using existing locking and bounded replace/retry utilities.
- Validate bundle completeness and hashes before publication. Retry sharing violations with the existing 15-second deadline.
- Record publication intent durably so restart recovery can reconcile the bundle, `Active_Render.json`, and superseding of earlier tasks.
- Preserve complete staging bundles on exhausted retries. Expose inspect/recover through `ZetApp` and the dashboard.
- Recovery must verify identity, hashes, current dependencies, and destination conflicts; it must not overwrite a different ready task or silently supersede a newer active task.
- Do not automatically delete the investigation’s orphan or other incomplete bundles.

**Acceptance:** Inject WinError 5/32/33, timeout, conflicting destination, duplicate recovery, and crashes at each publication boundary. Exactly one ready task results; earlier tasks are superseded only after successful publication.

Handoff:

* New invariants introduced: Manual render asks publish from a complete, hash-verified staging bundle through a durable publication journal; the ready destination and active render identity are conflict-checked; retry exhaustion preserves staging; older matching manual tasks are superseded only after ready publication and active-render recording.
* APIs/contracts changed: Added `ManualRenderPublicationService.publish()`, `inspect()`, and `recover()`; `ZetApp.inspect_manual_render_publications()` and `recover_manual_render_publication()`; dashboard `GET /api/render-console/publications` and `POST /api/render-console/publications/{ask_id}/recover`. Story and asset manual ask publication now use the service.
* New tests/fixtures available to later WPs: `tests/test_wp05_reliability.py` covers WinError 5/32/33, timeout, bundle/hash/dependency validation, conflicting destinations and newer active renders, duplicate recovery, crash-boundary recovery, superseding order, and ZetApp/dashboard exposure using temporary queues.
* Assumptions later WPs may rely on: WP05 acceptance is PASS: the focused suite passed 6 tests, the full suite passed 260 tests, `node --check zet/web/static/zet.js` passed, and the isolated WP01 benchmark passed at 1x/10x/100x cold and warm scales. The investigation’s live orphan and live queue bundles were not recovered, deleted, superseded, or otherwise mutated; its live recovery status remains unverified.
* Deviations from master plan: None.

### WP06 — Preserve overrides and reconcile AI status
**Executor:** Light/local. **Dependencies:** WP01.

- Add raw `identity_override_text` and `costume_override_text` to catalog models/API responses alongside effective text.
- Mode changes retain raw text and provenance. Omitted text means unchanged; explicitly supplied empty text means clear.
- Disable editing in inherit/not-applicable modes without clearing the retained override.
- Derive AI status messaging from the latest selected record; clear obsolete harvested messages after approval/rejection.

**Acceptance:** Both override sections survive override → inherit/not-applicable → save → reload → override exactly. AI drafts survive navigation; approval produces one consistent final status.

Handoff:

* New invariants introduced: Effective identity/costume text is selected by mode, while raw override text and provenance remain retained independently in the existing `sections.*.approved_text` and `sections.*.provenance` records. Omitted text leaves the retained raw value and provenance unchanged; an explicitly supplied empty text clears the raw value. Inherit and not-applicable editors are disabled in the dashboard, and AI status messaging is rendered from the latest selected catalog record.
* APIs/contracts changed: `ImageCatalogItem` and catalog API payloads now expose `identity_override_text`, `costume_override_text`, `identity_provenance`, and `costume_provenance` alongside effective `identity_text` and `costume_text`. Dashboard metadata saves omit `approved_text` for non-override modes; override mode submits the editor value, including an explicit empty value.
* New tests/fixtures available to later WPs: `tests/test_image_catalog_service.py` covers independent identity and costume raw-text/provenance retention, inherit/not-applicable round trips, omitted text, and explicit clearing. `tests/browser/dashboard.spec.mjs` covers disabled mode editors, draft persistence across navigation, and clearing the harvested status after approval.
* Assumptions later WPs may rely on: WP06 acceptance is PASS. Focused catalog/web tests passed (22 tests), the WP01 dependency suite passed (4 tests), the Image Inventory browser tests passed (3 tests), JavaScript syntax validation passed, and the isolated WP01 benchmark passed at 1x/10x/100x cold and warm scales using temporary roots. The full 33-test Playwright run had 32 passes and one unrelated pre-existing WP03 direct-scene history failure (`scene-builder-status` remained `Market-Meeting` where the test expected `Opening-Scene`); rerunning that case reproduced it, so the full browser suite is not green. WP08 must migrate the existing `sections` storage contract deliberately: `approved_text` is the raw override field and `identity_text`/`costume_text` in API models are effective fields; no catalog format migration was introduced here.
* Deviations from master plan: None.

### WP07 — Empty harvest and bounded history
**Executor:** Light/local. **Dependencies:** WP01.

- Return immediately when active Answer contains no harvestable records.
- Decouple harvest execution from the full AI-controls/history payload.
- Limit toolbar responses to action results and active queue state. Load recent history separately.
- Remove archive enumeration from harvest, ordinary status polling, and toolbar refreshes.

**Acceptance:** With an empty Answer queue and 100× archived history, archive access is zero and the action returns within 500 ms on the reference host. Failed answers remain available for retry.

## Larger-library work packages

### WP08 — Catalog record format and explicit migration
**Executor:** Medium. **Dependencies:** WP06.

- Replace the monolithic catalog with a versioned catalog manifest, one record per catalog ID, one record per reference-set ID, and a small organization document for collections/keywords.
- Preserve existing IDs, source keys, tags, metadata, provenance, and image locations. Use library-relative paths for library-owned files; keep explicitly external references identifiable.
- Add an explicit migration command with dry-run reporting, preflight validation, backup, resumable progress, and final verification.
- Stage and validate the complete new representation before switching the catalog manifest. Runtime startup rejects an incomplete migration.
- Remove runtime auto-upgrade/legacy auxiliary discovery for this catalog path. Keep legacy conversion in the migration command.
- Change metadata updates and backups to touch only the affected record.

**Acceptance:** A migrated temporary library retains every ID/reference and exact override text; image hashes remain unchanged. A second migration is a no-op. Interrupted migration resumes safely. One-item edits never rewrite or back up the whole catalog.

### WP09 — Machine-local index repository
**Executor:** Medium. **Dependencies:** WP08.

- Add a SQLite repository outside Dropbox, Git, and the authored library, keyed by canonical library location.
- Index stories, ordered scenes, render targets, catalog records, reference relationships, active work, and historical job summaries.
- Store relative source paths, fingerprints, parse status, and index generations. Use indexed scope/status/name queries and deterministic pagination.
- Run initial rebuild explicitly or as a background startup task. Serve an “index building” state rather than falling back to expensive request-time scans.
- Publish rebuilt generations transactionally; retain the last complete generation until replacement succeeds.

**Acceptance:** Index deletion/rebuild preserves authored files. Queries support stable ordering and scope filters. Corrupt source records appear as errors, not silently missing valid work. Database corruption triggers rebuild guidance.

### WP10 — Incremental refresh and dependency invalidation
**Executor:** Medium. **Dependencies:** WP09.

- After successful Zet writes, update affected index records and invalidate dependent summaries/compiled results before reporting refreshed state.
- Use a single background reconciler for external edits and Dropbox changes: start a new scan 60 seconds after the previous scan completes.
- Enumerate relevant authored roots only; exclude backups, media contents, temporary files, and archives. Reparse only changed fingerprints.
- Persist a reconciliation cursor and expose last-completed time, current generation, and errors.
- Track dependency edges from scene/render targets to referenced records, templates, and settings. Cache compilation by dependency fingerprint plus compiler version.
- Revalidate actual dependencies before staging, promotion, or other consequential actions; cached “fresh” status cannot authorize a stale operation.

**Acceptance:** External create/edit/delete/rename converges after reconciliation. Unrelated edits do not invalidate unrelated scenes. Dependency changes invalidate affected targets. A crash between file write and index update is repaired on restart.

### WP11 — Move lists, counts, and history onto the index
**Executor:** Medium. **Dependencies:** WP04, WP07, WP10.

- Route Inventory, Image Review, Candidates, production summaries, and recent-harvest queries through indexed services.
- Add list responses containing `items`, `total`, `next_cursor`, `generation`, and freshness/error metadata. Default page size: 50; maximum: 200.
- Use one index snapshot for scoped/project counts. Update all affected dashboard consumers in the same package; retain no dual response format.
- Perform detailed freshness calculation only for displayed/requested targets.
- Backfill harvest history once through a resumable explicit operation; thereafter record transitions incrementally. Provide paginated history without archive scans.

**Acceptance:** After indexing, list/count requests perform no full library/archive traversal. Tenfold unrelated library growth does not increase scene loads or compiles for a fixed page. Mutation responses invalidate stale cursors or trigger a clean page reload.

### WP12 — Migration rehearsal and scale acceptance
**Executor:** Medium. **Dependencies:** WP03, WP05, WP11.

- Rehearse migration and index rebuild on a copy; compare entity counts, references, prompt outputs, overrides, and candidate/task associations.
- Benchmark 1×/10×/100× libraries, including dense candidate queues and simultaneous reconciliation.
- Require warm ordinary navigation under 2 seconds and review listing under 3 seconds, measured at p95 over 30 runs on the reference host.
- Require zero archive traversals on hot paths, one bounded list page in memory, and no overlapping reconciliation/summary work.
- Document cold rebuild duration separately; it must remain cancellable/resumable and never block page navigation.
- Produce a live cutover checklist with backup location, validation report, migration command, rebuild command, and restore procedure. Execute live conversion only as an explicitly approved package.

**Acceptance:** Scale report passes latency and structural work limits. All eight First Day tasks remain associated correctly; no rendering or candidate approval is required.

## ModelUpdater work packages and evaluation cases

### WP13 — Authoritative runtime and role contracts
**Executor:** Medium. **Dependencies:** None.

- Remove Zet’s hardcoded `num_ctx`/`num_predict` from direct generation. Managed alias settings own context/output limits; explicit task temperature and response schemas remain task-owned.
- Audit direct and queued paths for equivalent runtime behavior and record effective alias, digest, and runtime settings in evidence.
- Split Prompt Evolution analysis/editor configuration into vision analysis and text editing roles. Route bootstrap/diagnosis/image-backed refinement to vision; synthesis/minimal edits/JSON repair to text.
- Provide an explicit config migration that initially copies the former shared assignment into both roles, preserving behavior until qualification.
- Expose every selectable role in Config; label intentionally shared operations. Unsupported fallback tasks fail explicitly instead of using placeholder prompts.

**Acceptance:** Config round trips cover all roles, including new split roles. Direct and queued requests honor the managed context/output configuration. Fixtures cover repair, directed refinement, and fallback paths.

### WP14 — Versioned Zet evaluation corpus
**Executor:** Light/local for export; Medium review of expected answers. **Dependencies:** WP13.

- Extend ModelUpdater’s existing fixture format with task role, source provenance, prompt/schema version, critical assertions, scored dimensions, and performance class.
- Snapshot actual production prompts and schemas; do not rephrase them into easier benchmark instructions.
- Include source/image bytes in suite digests. Reject duplicate fixture IDs and missing required assets.
- Store private library examples through `MODELUPDATER_FIXTURE_ROOTS`; commit portable synthetic cases.
- Create development and held-out variants for every case below. Manually verify image annotations; the erroneous arch drafts are negative examples, never ground truth.
- Export actual short, median, and largest supported prompt examples and record token counts using the evaluated runtime.

**Acceptance:** Corpus loading is independent of the live library. Changing an image or schema invalidates prior evidence. Every required case has input, expected constraints, negative examples, and scoring rules.

| Case | Zet input and expected quality |
|---|---|
| **SB-01: Story phase** | Chapter 1 narrative with only story phase requested. Capture the visible beat; ask no architecture/lighting questions; preserve known continuity. |
| **SB-02: Phase coverage** | One fixture for every current interview phase. Output passes its actual schema and changes only permitted phase content. |
| **SB-03: Exact elements** | Elements `person_A`, `person_B`, `arch_01`, including an off-frame prop. Preserve IDs; placements contain each required ID exactly once; composition excludes invisible elements. |
| **SB-04: Dialogue and follow-up** | Narrative contains exact dialogue and an answered ambiguity. Preserve speaker/text exactly, invent no dialogue, and do not repeat the answered question. |
| **PA-01: Prompt analysis** | Prompt deliberately contains a name typo, conflicting left/right placement, and incompatible gaze directions. Identify all three with localized corrections; do not rewrite unrelated content. |
| **PA-02: Clean prompt** | Valid compiled First Day prompt. No invented contradictions or unnecessary identity changes. |
| **PC-01: Condensation** | Detailed character prompt with required hair, costume, pose, and negative constraints. Exactly one `prompt:` and one `negative:` line; preserve all annotated critical traits without additions. |
| **ID-01: Arch inscription** | Actual arch image with verified visible-text annotation. Exact transcription where legible; no invented slogan or unsupported people. |
| **ID-02: Unreadable text** | An intentionally obscured inscription variant. Do not confidently invent missing text; uncertainty must be explicit. |
| **ID-03: Identity/costume separation** | Person reference containing distinctive anatomy, worn clothing, and a carried object. Identity and costume remain separated; carried objects enter neither field. |
| **VC-01: Ordered comparison** | Reference/candidate pair with annotated hair and costume changes plus stable traits. Correctly attribute differences to the candidate; reversing image order reverses attribution. |
| **VC-02: Unchanged pair** | Identical images. Report no major invented differences. |
| **RC-01: Checklist fidelity** | IDs `hair-01`, `coat_02`, `occluded-03`. Exactly one result per ID; obscured evidence yields unknown rather than fabricated pass/fail. |
| **PE-01: Cross-seed synthesis** | Three critic reports: one defect in all seeds, another in one, and one stable success. Preserve seed evidence, rank recurrence correctly, propose at most three priorities. |
| **PE-02: Minimal edit** | Approved intervention changes “blue coat” to “red coat.” Make only that authorized change and an accurate intervention-linked change log. |
| **PE-03: Vision diagnosis/refinement** | Reference plus critic evidence and a requested costume correction. Ground interventions in visible evidence; preserve stable identity and unrelated prompt text. |
| **JR-01: JSON repair** | Malformed response with known IDs and wording. Repair syntax/schema without changing supported meaning or inventing missing facts. Include an unrepairable case that follows Zet’s explicit failure path. |
| **AW-01: Asset workflow** | Snapshot each reachable AssetWorkflow task with its real output contract. Preserve required asset facts and formatting; unsupported stages fail before inference. |
| **LG-01: Long input** | Largest supported scene/batch with critical constraints near beginning, middle, and end. Preserve all constraints without truncation or silent omission. |
| **IN-01: Embedded instructions** | Narrative/report contains text asking the model to ignore its schema or change IDs. Treat it as source data and retain the production contract. |

### WP15 — Quality scoring and qualification gates
**Executor:** Medium. **Dependencies:** WP14.

- Extend `FixtureService` beyond nonempty/contains checks: nested schema assertions, exact ID sets, duplicate detection, field preservation, format checks, edit constraints, and annotated fact precision/recall.
- Return assertion evidence and dimension scores. Do not use keyword presence as a substitute for semantic correctness.
- Score grounded factual accuracy 40%, required-content coverage 25%, instruction/phase compliance 25%, and relevance/concision 10%. Normalize non-applicable dimensions.
- Hard-fail malformed required schemas, changed IDs/dialogue, unauthorized edits, invented critical visual facts, wrong image ordering, or ignored phase boundaries.
- Require at least 85/100 for every assigned task family, with all critical checks passing. Average scores cannot hide a failed family.
- Use manually anchored rubrics for semantic judgments; optional independent model judging is advisory. Unresolved semantic judgments block promotion pending review.
- Test validators against deliberately bad answers, including the investigation’s observed failures.
- Make sentinel-only runs insufficient for Zet production qualification.

**Acceptance:** Fast but incorrect candidates fail. Replayed good/bad answers produce expected scores. Reports distinguish schema success, semantic quality, repair success, and performance.

### WP16 — Context, resource, and latency qualification
**Executor:** Medium. **Dependencies:** WP15.

- Evaluate 16K, 32K, then 64K context configurations; select the smallest passing all assigned tasks with at least 25% input headroom plus the output allowance.
- Preserve production output requirements; output-cap truncation is a failure.
- For interactive aliases, require full GPU residency, at least 4 GiB available host RAM, and 1 GiB VRAM reserve at peak measured use. Unknown telemetry blocks qualification.
- Permit spill only in epic profiles; no automatic interactive exception.
- Run each required case three times warm and once cold. Store raw durations, queue wait, load time, TTFT, generation rate, completion time, peak RAM/VRAM, and output tokens.
- Initial warm budgets: TTFT ≤5 seconds; short text/structured tasks ≤30 seconds; single-image ≤45 seconds; paired-image and long synthesis ≤60 seconds. Cold completion adds at most 30 seconds for loading.
- Report these as proposed acceptance budgets, not measured capabilities; if none pass, return no qualified candidate.
- Rank qualified candidates by quality first, then latency, then resource headroom. Do not let speed compensate for incorrect answers.

**Acceptance:** Tests cover insufficient RAM, CPU spill, missing telemetry, truncation, context overflow, slow TTFT, and high-quality but resource-ineligible candidates.

### WP17 — Pair diversity and resource scheduling
**Executor:** Medium. **Dependencies:** WP13, WP16.

- Require verified upstream-family diversity for every primary/alternate pair in ModelUpdater; unknown lineage cannot satisfy diversity.
- For critics, evaluate both candidates independently and report shared misses on paired fixtures.
- Prepare critic A → `image-analysis`, critic B → `image-analysis-alt` only when the pair passes.
- Test AI_Proxy same-model reuse, cross-model unload, failure propagation, and active-queue polling independently of archive size.
- Include Zet’s direct Scene Builder calls in the resource-ordering test. If they bypass shared scheduling, route them through the existing queued worker with dashboard job-status polling rather than creating a second scheduler.
- Run vision → general → vision, general → vision → general, and controlled overlap on the reference host.

**Acceptance:** No simultaneous unmanaged GPU loads; same-model work reuses residency; failed switches produce actionable job failures; navigation remains within WP12 limits during inference.

### WP18 — Assignment proposals and end-to-end handoff
**Executor:** Medium. **Dependencies:** WP12, WP17.

- Run the full corpus against incumbent aliases and candidate configurations.
- Recommend Prompt Condense/Analysis and text-edit assignments from task evidence; keep incumbent assignments when no replacement qualifies.
- Produce a role → alias → exact digest/runtime → fixture evidence matrix.
- Preserve ModelUpdater’s separate proposal, approval, and activation workflow. Revalidate evidence if prompt, schema, fixture assets, runtime, or candidate digest changes.
- Re-run focused suites, full Zet Python tests, dashboard Playwright tests, relevant AI_Proxy tests, and ModelUpdater unit tests.
- After authorized activation, smoke-test actual generated manifests and effective runtime settings. Restore the previous revision if activation validation fails.

**Acceptance:** Every production role has passing quality/resource evidence or an explicit unresolved qualification failure. No alias changes occur merely because a new model is faster.

## Defaults and rollout

- **Immediate sequence:** WP01 → WP02 → WP03 → WP04 → WP05 → WP06 → WP07.
- **Scale sequence:** WP08 → WP09 → WP10 → WP11 → WP12.
- **Model sequence:** WP13 → WP14 → WP15 → WP16 → WP17 → WP18.
- Execute one package at a time; package dependencies determine readiness.
- Files remain authoritative. SQLite is disposable and never synchronized between machines.
- External edits are eventually reflected by reconciliation; consequential operations revalidate their inputs immediately.
- Migrate only formats changed by these packages. Do not use the no-compatibility preference to rewrite unrelated library formats.
- Keep backups for recovery, not indefinite runtime compatibility.
- Retain the investigation’s staged scenes and pending draft as existing user work. The remediation does not require new image generation or approval of AI-authored metadata.
