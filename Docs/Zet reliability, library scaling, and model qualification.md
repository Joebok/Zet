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

### WP02 — Navigation independent of pending requests
**Executor:** Medium. **Dependencies:** WP01.

- Update `zet.js` to attach navigation handlers before awaited startup loading.
- Introduce page/selection generations and `AbortController` handling through the existing fetch helper.
- Change the active page immediately; perform page loading independently. Only the current generation may update data, errors, loading indicators, or selection.
- Replace overlapping summary intervals with completion-scheduled refreshes. Allow at most one summary request per client; pause it while the document is hidden.
- Treat cancellation as cancellation, not an empty result or user-facing error.

**Acceptance:** With review/candidate requests delayed by 120 seconds, another page activates within 250 ms. Late success and error responses cannot alter the new page. Loading, empty, and failed states remain distinct.

### WP03 — One Scene Builder selection contract
**Executor:** Medium. **Dependencies:** WP02.

- Use one canonical ordered scene collection populated by workspace context.
- Route header selection, arrows, Scenes-page Builder, and workflow navigation through the same selection function.
- Track requested scene separately from the loaded editable document. Disable save/render until their story and scene IDs match.
- Preserve existing unsaved-change protection and render-target context on Builder ↔ Prompt/Analysis ↔ Render Console transitions.
- Make To Do and Template Instruction Manuals activate their intended existing destinations; report an actionable error if loading fails.

**Acceptance:** Direct entry supports all eight scenes; first/last arrows are correct; rapid selection cannot stage the previous scene; browser back/forward and return paths preserve context.

### WP04 — Remove redundant review and summary work
**Executor:** Medium. **Dependencies:** WP01.

- Separate lightweight pending-candidate discovery from detailed freshness evaluation.
- Check main/subscene candidate paths before loading detailed status or compiling renders. Read a scene’s subscene definitions at most once per discovery pass.
- Introduce a request-scoped discovery context shared by scene, catalog, and summary services.
- Obtain scoped and project totals from one discovered dataset.
- Add process-level single-flight summary computation with a 15-second cache, invalidated by relevant Zet mutations. Browser cancellation alone must not be treated as backend cancellation.

**Acceptance:** Zero-candidate scenes cause zero render compiles. One summary request performs at most one catalog discovery. Concurrent identical summary requests share computation. Counts match review rows for the same snapshot.

### WP05 — Durable manual-render publication
**Executor:** Medium. **Dependencies:** WP01.

- Route publication through a focused backend service using existing locking and bounded replace/retry utilities.
- Validate bundle completeness and hashes before publication. Retry sharing violations with the existing 15-second deadline.
- Record publication intent durably so restart recovery can reconcile the bundle, `Active_Render.json`, and superseding of earlier tasks.
- Preserve complete staging bundles on exhausted retries. Expose inspect/recover through `ZetApp` and the dashboard.
- Recovery must verify identity, hashes, current dependencies, and destination conflicts; it must not overwrite a different ready task or silently supersede a newer active task.
- Do not automatically delete the investigation’s orphan or other incomplete bundles.

**Acceptance:** Inject WinError 5/32/33, timeout, conflicting destination, duplicate recovery, and crashes at each publication boundary. Exactly one ready task results; earlier tasks are superseded only after successful publication.

### WP06 — Preserve overrides and reconcile AI status
**Executor:** Light/local. **Dependencies:** WP01.

- Add raw `identity_override_text` and `costume_override_text` to catalog models/API responses alongside effective text.
- Mode changes retain raw text and provenance. Omitted text means unchanged; explicitly supplied empty text means clear.
- Disable editing in inherit/not-applicable modes without clearing the retained override.
- Derive AI status messaging from the latest selected record; clear obsolete harvested messages after approval/rejection.

**Acceptance:** Both override sections survive override → inherit/not-applicable → save → reload → override exactly. AI drafts survive navigation; approval produces one consistent final status.

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
