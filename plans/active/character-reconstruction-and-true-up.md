# Shared reconstruction and true-up, developed through Freydis

Status: simplified local workflow verified; operator trial awaiting publication/deployment. Final Freydis reference set remains unfinished.
Date: 2026-10-15 (America/Los_Angeles).
Related work: [Style Unification phase 1](style-unification.md), [ADR 0012](../../Docs/DECISIONS/0012-universe-style-and-reconstruction.md).

## Goal

Develop one reusable reconstruction and true-up process through the Quick Character Wizard, prove it with Freydis, then expose the same behavior in Image Generation. The wizard is guided image generation: references establish appearance; Joe can deliberately change equipment, clothing, or other features; requested reference views must retain the resulting identity and design.

The product outcome is a generic operator-driven render/review/correction loop, including freeform custom tweaks and an operator decision that a result is close enough. Freydis provides evidence for that process; automated pixel-perfect repair is not an acceptance condition. Individual handwork may remain after guided iteration. Automated findings are advisory and cannot override artistic acceptance.

### Operator trial follow-up packets (2026-10-15)

- **WP12 — Simplify iteration.** Files: shared true-up/reconstruction services, wizard service/browser, Image Generation browser/template, affected prompt/decision documentation. Replace model-based correction compatibility approval with direct composition of selected suggestions and operator feedback; explicit feedback can override prior artistic direction. Keep optional analysis, prior attempts and detailed findings out of the primary view. Generating uses the current brief without an approval checkbox; allow choosing a rendered image or custom refinement when automatic review failed. Dependencies: existing shared reconstruction. Acceptance: image → custom feedback → render → use image, with no requirement to clear findings or obtain model approval. Validate with the existing disposable service/browser journeys and JS syntax; no new maintained tests.
- **WP13 — Operator access.** Inspect the current runtime/release path and prepare the reviewed local build for an actual operator trial. Dependencies: WP12 and relevant checks. Acceptance: explain exactly how Joe can reach this build; request any required production promotion/external-write authorization only after the local result is ready. Do not point Joe at the older running release as though it contains these changes.

Freydis acceptance: start from original asset `adc81790-036d-43e9-95f3-aa651df2ebcb`; produce a Moonsea-styled reference set with no axe, original-length asymmetric hair, and a better identity match than `16878a07-a727-401e-a0fd-418f2463e662`. Joe judges artistic/identity success from images. Software checks alone cannot establish it.

Joe subsequently requested implementation of this plan. Local implementation and its Freydis trial are authorized; Joe retains artistic approval of front/views and final library publication. No deployment or external publication is authorized. Use one agent; no new production dependencies or maintained tests.

## Current behavior and evidence

Authoritative code inspected:

- [ImageReconstructionService](../../zet/services/image_reconstruction_service.py): durable source/style analysis, optional notes, automatic txt2img dispatch; directly reserves Image Generation workspace slots. Original source pixels are analysis-only. No candidate comparison or correction loop exists.
- [UniverseStyleService helpers](../../zet/services/universe_style_service.py): read/fingerprint `canonical_art_style`, compose it with content once. Reuse this ownership.
- [QuickCharacterWizardService](../../zet/services/quick_character_wizard_service.py): one to three captioned references, primary identity, editable analysis/proposals/questions, front approval before other views, candidate review/refinement/history, revision fencing. Its analysis and rendering explicitly preserve source style and equipment. Review supplies prose/refinement strings, without an explicit intentional-change contract.
- [Wizard UI](../../zet/web/static/quick_character_wizard.js), [router](../../zet/web/quick_character_wizard_router.py), and [template](../../zet/web/templates/index.html): notes/captions can describe changes but no distinct preserve/change/style or true-up guidance is displayed. Users choose full body/portrait and left/right; output is FRONT, chosen-side FRONT_3_4, chosen-side PROFILE.
- [Quick publication](../../zet/services/quick_character_publication_service.py): transactional, repeatable library set publication with source plus three views and prompt identity. Does not create traditional character-pipeline prerequisites.
- [Ad hoc generation](../../zet/services/ad_hoc_image_generation_service.py), [workspace](../../zet/services/image_generation_workspace_service.py), [router](../../zet/web/ad_hoc_image_generation_router.py), [app](../../zet/app.py), [web construction](../../zet/web/app.py): shared durable render transport already reaches the wizard. Reconstruction currently accepts a library asset or uploaded image, not a server-resolved selected render result. Eight-slot selection/protection/reservation and provenance already exist.
- [Existing S1–S3](../../tests/e2e/fast.spec.mjs) and [fixture server](../../tests/e2e/server.py): inspect existing source/publication and isolated queue patterns; neither reconstruction nor the wizard has a maintained scenario.

Read-only inspection of Moonsea's authoritative `catalog.sqlite3`, both source PNGs, `universe.json`, and the existing wizard session found:

| Evidence | Finding / implication |
| --- | --- |
| Original Freydis | Approved, 941 × 1672; asymmetric pale hair with a swept side ending around the jaw and a closely cut opposite temple; recognizable angular facial structure, headband, fang necklace, leather/metal/fur outfit, burgundy cloak, and ornate axe. Hair length should use visible facial landmarks rather than the ambiguous word “long.” |
| Freydis From Prompt | Approved, 768 × 1024; the swept hair extends onto the upper chest. Its saved prompt says “down past her jaw,” which does not bound the length. It is useful as a comparison of drift, not as an identity or hairstyle authority. Other apparent face/costume changes should be reviewed against the original, not automatically accepted. |
| Moonsea style | The current canonical style is the accepted detailed naturalistic fantasy illustration with restrained painterly finish. Freeze the actual style text/hash for each new task; do not repeat or revise the phase-1 style calibration. |
| Existing wizard session `3f481d5ed1854c89829e059fce1bfef6` | “Freydis Quick Character validation,” DRAFT_READY, full body/left, no current selections. Notes explicitly preserve the ornate axe and source style; description calls the hair “long.” Several reviewed candidates exist, including angle/gaze concerns. Preserve this historical draft and start a new session. Do not silently reinterpret its brief. |

Image checksums recorded for reproducible pilot preflight:

- Original: `0d5b2c36008b550b609d618d7f5a5620c1e248421fdcf5a6cc6b3a7549af1407`.
- Comparison: `6091c4c5bdc29e0491237f8b99caf0df0f7c3dc1135b6a480e46bf8058b90975`.

## Desired user process

### Wizard first

1. **Choose references and outputs.** New Freydis session with the original as primary identity/design evidence; use current full-body FRONT, FRONT_LEFT_3_4 and LEFT_PROFILE defaults. Keep portrait/right-side options. Additional view families or arbitrary view lists are outside this first implementation. No second reference is necessary for Freydis.
2. **Say what stays and what changes.** Choose “Reconstruct in Moonsea style.” Preserve original identity and visible design except requested edits. Enter “Remove the axe; leave both hands naturally empty; retain the rest of her outfit.” Hair should match the original swept shape and jaw-level extent. Provide general free-text changes; equipment/costume examples are guidance, not a closed feature list.
3. **Review the character brief.** Show compact Preserve, Change, Style, and Uncertain/unseen sections, with a plain summary of the intended result. Distinguish observed facts from proposed completions. Existing question/proposal approval resolves material uncertainty; do not require Joe to author a long prompt or approve a technical prompt before each render. Removing the axe requires plausible hand/occluded-costume completion, not reintroducing the original grip.
4. **Reconstruct the front.** Analyze original pixels into content independently of source style; apply the deliberate edits; render in the frozen Moonsea style. Source pose/background are not identity and yield to reference-view instructions. Render one candidate per wizard action initially; retain candidate history.
5. **Compare and true up.** Show original and candidate side by side, with a face/hair inspection affordance and a concise report. Separate accidental drift, requested changes successfully applied, requested changes missed, style/view problems, and details that cannot be judged. Offer “Apply selected corrections” with editable instructions. For example, shorten the swept hair to the original jaw-level extent while retaining its asymmetry and the axe-free hands.
6. **Approve the front.** Joe can correct again, generate another alternative, or approve despite advisory findings. A failed/unavailable review offers retry; it must not masquerade as a clean comparison. Never automatically publish, silently approve, or run an unbounded correction loop.
7. **Generate the other views from the approved front.** The approved styled, axe-free front is the design anchor. Compare each view with the original identity evidence, approved front, requested view, and deliberate edits. Do not force hidden face/necklace details into view or rotate the face back toward the camera to satisfy comparison.
8. **Accept and save the reference set.** Require three current approved views as today. Save new assets and ordered set membership with complete lineage; keep the original separately identified as source evidence. A source member containing the axe must never be labeled or chosen as an approved axe-free output. Do not replace existing assets, locks or preferred bindings implicitly.

### Image Generation, after the wizard pilot

- **One-off reconstruction:** existing library/upload/paste entry uses the shared target brief, reconstruction and selected-candidate true-up. Initial analysis still automatically dispatches as in phase 1; optional brief editing is available without adding a mandatory prompt-review gate.
- **Finish a selected render:** “Reconstruct in universe style” operates on a completed selected `{request_id, image_index}` from either txt2img or img2img. Resolve bytes server-side and freeze the exact selected child; no library import is required. This is an explicit action after selection, not automatic processing of every generated image.
- Each corrected/reconstructed result is a new child task/result in available workspace capacity. Retain the selected input and its bindings. Show “clear space” when no slots are available; never unselect, clear, or replace it automatically. Joe explicitly chooses the final result before import.
- Reuse upstream reconstruction identity/design evidence and intentional edits when present. Otherwise the selected image becomes the baseline; unrelated references from its parent img2img job are not automatically elevated to identity authorities.

## Shared behavior and proposed interfaces

Extend the existing `ImageReconstructionService`; do not build a second wizard-specific reconstruction engine. Keep vision comparison in a focused supporting service and rendering in the existing ad hoc transport. Host services own wizard candidates/selection or Image Generation workspace reservations; the reconstruction core must work without a board or HTTP request.

Proposed internal operations (names are planned, not existing APIs):

- `prepare`: resolve/freeze validated source(s), ordered roles, target brief, model and style; return a reconstruction task/revision.
- `analyze` / `compose`: obtain source observations, apply approved changes and task framing, create the effective render specification.
- `compare`: receive a server-resolved candidate and frozen target revision; return a persisted structured report.
- `correct`: receive selected report item IDs and optional user refinement, validate against the same target revision, submit a new candidate attempt with frozen inputs.

Existing Image Generation `start/status/options` remain compatible wrappers around this behavior. Wizard routes call their service/facade; no business logic, discovery, prompt transitions or render orchestration moves into `zet/web`.

### Target brief and precedence

Store source observations separately from the intended result. A target revision contains:

- Source IDs or task-relative snapshots, hashes, ordered captions/roles, and a primary identity authority. The comparison image can be “comparison only,” never a render/reference authority by accident.
- Style mode (`preserve_source` for the existing wizard path, `universe` for reconstruction), frozen destination style text/hash, analysis model and instruction version.
- Preserve facts with source attribution and uncertainty; explicit change records with stable IDs, action (`add`, `remove`, `replace`, or general `modify`), subject and desired result; approved unseen-detail proposals.
- Task framing/view constraints separately from reusable appearance. Avoid baking source pose/gaze/background into identity.
- An effective target description that resolves changed features rather than concatenating contradictory source facts and instructions. Unresolved contradictions require a focused question; do not let the model silently choose.

For affected features: explicit current user changes override source observations and prior generated anchors. The accepted front supplies completed design for other views only within that brief. Destination style governs rendering treatment independently of identity. A later explicit edit creates a new revision and supersedes earlier instructions for that feature; all unaffected changes remain in effect. Style/view changes do not license altered identity or equipment.

Freydis example: “axe exists” remains a source observation; the effective target says empty hands and no axe. Every render and review sees that distinction. Hair remains a preserve fact bounded by visible jaw/neck landmarks. Never interpret “restore source fidelity” as permission to restore removed equipment.

### Comparison and correction contract

Each report binds task ID, target revision/hash, candidate ID/hash, original reference hashes, optional front anchor, model and instruction version. Report items contain stable item IDs, feature, evidence reference, expected versus observed appearance, category, visibility/uncertainty, severity, and a proposed correction. Categories distinguish `drift`, `requested_change_missing`, `intentional_change_satisfied`, `style_or_view_issue`, and `not_evaluable`.

Compare identity using visible facial structure/proportions, hair silhouette/length/side, headband, body build and stable costume details. Judge clothing and equipment against the edited target, not an unconditional pixel match. Do not penalize intended style changes, new neutral pose, empty hands, occlusion, or appropriate foreshortening. AI confidence is advisory; no fabricated numeric identity threshold.

Before dispatch, resolve selected correction IDs from the persisted report, not arbitrary client evidence or paths. Compose corrections with all active keep/change/style constraints; reject proposals that contradict them and request a fresh comparison when necessary. Do not rely on negative-prompt keywords alone to keep the axe absent. Prompt correctness and actual rendered compliance are separate checks.

Initial reconstruction retains ADR 0012's **original pixels used only for analysis**. True-up edits use the selected, already styled candidate as an img2img render input; the original remains a comparison/identity analysis input. Other views use approved styled output references. This prevents source style/equipment from being repeatedly fed back into rendering, but text can lose facial precision. The Freydis front pilot is the explicit quality gate: if this cannot beat the comparison image, stop and document the limitation before wider rollout. Consider a separately approved, narrowly scoped identity-reference mode only with rendered evidence and an ADR amendment; do not silently violate the source-reference contract.

### Persistence, compatibility and failure behavior

- Version new reconstruction records explicitly (planned v2); preserve reading/status/retry/import of v1 records without rerunning analysis or changing saved prompts. Version new wizard reconstruction sessions; absent style/target fields retain existing source-style behavior and old candidate history. Never infer that an old session wanted axe removal.
- Keep reconstruction tasks under universe `_state/ImageReconstruction/`; add immutable target revisions and report/attempt artifacts under the owning task. Wizard sessions retain task/revision/attempt links rather than copying a second mutable target. Use task-relative filenames; external references use existing portable library path helpers, never new machine-absolute persisted paths.
- Freeze candidate bytes/hash, parent generation request/index or wizard candidate, source snapshots, target/style, ordered render references, exact effective prompt, seed and model before submission. Keep parent versus corrected result provenance explicit through library import/publication.
- New attempts need unique IDs and persisted ownership before dispatch. Fence review/analysis/render application by owning universe, session/target revision, candidate hash, front anchor, and attempt ID. Repeated polling/retry/application must not submit duplicate work. Clear/abandon/replace makes late work inapplicable.
- Retrying a failed operation reuses its frozen inputs; editing the target or explicitly adopting current universe style creates a new revision. Candidate-only corrections do not change the target. A corrected front replaces the selected front only by Joe's approval, then invalidates downstream approvals tied to the previous anchor. Target edits invalidate incompatible approvals without deleting history.
- Interrupted analysis/review reports failure with retry guidance. On a crash around render handoff, reconcile the persisted request before offering resubmission. Review failure does not lose a valid rendered candidate. No automatic replacement/publication or lock changes.
- Publication keeps existing transactional/idempotent IDs and entity linkage; enrich provenance with target/style/change decisions, reports and correction ancestry. Do not use `source_asset_id` replacement bindings to express reconstruction provenance.

## Impact and documentation owners

| Area | Planned ownership / effect |
| --- | --- |
| Shared reconstruction | Existing `image_reconstruction_service.py`; proposed `image_reconstruction_contract.py` for validated records/precedence, and `image_true_up_service.py` for comparison. Reuse `structured_ai_service.py`, existing model discovery and `universe_style_service.py`; no new dependency. |
| Host integration | `quick_character_wizard_service.py`, `ad_hoc_image_generation_service.py`, `image_generation_workspace_service.py`, `zet/app.py`; minimal lifecycle injection in `zet/web/app.py`. |
| Presentation | Existing wizard and ad hoc routers; `quick_character_wizard.js`, `zet.js`, `index.html`, scoped `zet.css` if needed. Browser owns drafts/presentation only. |
| Library publication | `quick_character_publication_service.py`, existing ad hoc import and `ZetApp` provenance forwarding. No catalog schema change expected; verify existing provenance JSON capacity before implementation. |
| Knowledge | `Docs/COMPONENTS/PROMPTS.md` owns prompt/reference rules; `LOCAL_CHARACTERS.md` owns wizard journey; `DATA_MODEL.md` owns versions/lineage; `LIBRARY.md` owns output/source distinction; `CODE_MAP.md` owns entry points. `INVARIANTS.md` and an ADR should describe shared target/true-up fencing and original-versus-generated render inputs. `Testing.md` retains the same maintained baseline and names coverage gaps. |

Consulted [Architecture](../../Docs/ARCHITECTURE.md), [Data model](../../Docs/DATA_MODEL.md), [Invariants](../../Docs/INVARIANTS.md), [Code map](../../Docs/CODE_MAP.md), [Prompts](../../Docs/COMPONENTS/PROMPTS.md), [Local characters](../../Docs/COMPONENTS/LOCAL_CHARACTERS.md), [Library](../../Docs/COMPONENTS/LIBRARY.md), [Testing](../../Docs/Testing.md) and plan/ADR conventions. No Narrative or retiring Scene Builder workflow changes are required.

## Implementation packets

Packets are tracked in Progress and decisions below. These are bounded Luna-sized units, not delegation authorization. Packet validation commands describe intended checks; observed results are recorded separately. Disposable checks live under ignored `test-results/`; no permanent scenario is added. Use the verified Python 3 interpreter from the implementation environment.

### WP1 — Define the target brief and record compatibility

- Dependencies: none.
- Files/interfaces: proposed `zet/services/image_reconstruction_contract.py`; reconstruction/wizard record readers only.
- Work: define v2 target/source/change/report contracts, revision hashing and precedence; normalize missing legacy fields on read without rewriting history. Keep unknown/occluded facts explicit.
- Acceptance: Freydis target retains original hair and appearance while intentionally removing the axe; arbitrary add/replace/modify instructions fit the same model. Legacy wizard and v1 reconstruction records remain readable with old semantics.
- Validation: disposable prepared-record check `python3 -B test-results/reconstruction-contract-check.py`; inspect before/after legacy bytes; `git diff --check`.

### WP2 — Extract shared analysis from workspace allocation

- Dependencies: WP1.
- Files/interfaces: `image_reconstruction_service.py`, `ad_hoc_image_generation_service.py`, `image_generation_workspace_service.py`, minimal `zet/app.py` construction.
- Work: implement prepare/analyze/compose with durable immutable inputs independent of workspace slots; retain current start/status/options wrappers and automatic Image Generation handoff. Expose shared operations to the wizard service. Generalize image/upload/library source validation through existing tools, without arbitrary path APIs.
- Acceptance: the same target analysis works with a wizard host and no board reservation; existing one-off reconstruction still reserves before dispatch, emits txt2img without original references, and does not duplicate handoff on polling/restart.
- Validation: `python3 -B test-results/reconstruction-analysis-check.py` with prepared model/queue answers; check source bytes/hashes and old-route compatibility; `git diff --check`.

### WP3 — Produce structured, intent-aware comparison reports

- Dependencies: WP1–WP2.
- Files/interfaces: proposed `image_true_up_service.py`, reconstruction facade; reuse existing Codex/Ollama structured execution.
- Work: compare candidate, original evidence, optional front anchor and edited target; persist report categories/evidence/corrections; validate model replies and visibility handling.
- Acceptance: a prepared long-hair/axe-free candidate gets a hair correction and successful axe-removal finding, never “restore axe”; unavailable/hidden features are not mismatches; stale candidate/revision reports cannot be applied.
- Validation: `python3 -B test-results/reconstruction-comparison-check.py` with prepared replies including contradictory/invalid suggestions and review failure; source inspection of image order and role labels; `git diff --check`.

### WP4 — Apply corrections as durable candidate attempts

- Dependencies: WP2–WP3.
- Files/interfaces: `image_reconstruction_service.py`, `ad_hoc_image_generation_service.py`; contract helpers as needed.
- Work: select persisted report item IDs, compose constrained corrections, snapshot the candidate as img2img input, retain lineage and frozen prompts/seeds; provide retry/recovery and attempt fencing. Keep target edits separate from candidate correction.
- Acceptance: hair correction retains every active intentional edit and style; original source is absent from render inputs. A retry cannot duplicate an existing submitted render; an obsolete report cannot correct a replacement candidate. A contradictory suggestion is rejected, not appended to the prompt.
- Validation: `python3 -B test-results/reconstruction-correction-check.py` against a disposable private queue; inspect rendered payload, attempts, hashes and restart reconciliation; `git diff --check`.

### WP5 — Connect the wizard front workflow

- Dependencies: WP2–WP4.
- Files/interfaces: `quick_character_wizard_service.py`, `quick_character_wizard_router.py`, minimal `zet/app.py`/`zet/web/app.py` injection.
- Work: opt-in universe reconstruction mode, shared target links, front candidate generation/comparison/correction actions, revision/selection guards. Route all new shared behavior through focused services. Keep the existing source-style workflow functional.
- Acceptance: create/resume a new Freydis session; reconstruct and true up a front without occupying Image Generation board slots; existing drafts/history and reference captions remain intact. Corrected candidates require explicit front approval.
- Validation: `python3 -B test-results/wizard-reconstruction-check.py` using disposable sessions/prepared replies; inspect universe/service binding and busy/abandon/stale handling; `git diff --check`.

### WP6 — Guide the wizard user through the front decision

- Dependencies: WP5.
- Files/interfaces: `quick_character_wizard.js`, wizard markup in `index.html`, scoped `zet.css` if needed.
- Work: visible style choice; Preserve/Change brief and free-text edits; uncertainty/proposal guidance; original/candidate comparison with useful face/hair inspection; selectable corrections, editable refinement, next-action messages and candidate history. Preserve dirty fields during polling and universe switches.
- Acceptance: Joe can express axe removal and hair fidelity without writing a technical prompt; UI explains the next step through front approval; review failure/uncertainty is visible; no mandatory technical-prompt gate.
- Validation: `node --check zet/web/static/quick_character_wizard.js`; disposable browser check `node test-results/wizard-reconstruction-browser.mjs` against an isolated server, including desktop/narrow layout and reload; visually inspect screenshots; `git diff --check`.

### WP7 — Carry the approved design through views and publication

- Dependencies: WP5–WP6.
- Files/interfaces: `quick_character_wizard_service.py`, `quick_character_publication_service.py`; existing wizard view presentation.
- Work: use the approved styled front for three-quarter/profile rendering; apply the same intent-aware review/correction; preserve angle/visibility rules. Carry task/revision/style/report/attempt provenance into the ordered library set; identify source evidence distinctly.
- Acceptance: all three current views retain axe removal, hair silhouette, outfit and identity; changed front invalidates dependent approvals. Transactional repeat acceptance creates one set, and the axe-bearing original is source evidence only. No pipeline locks or historical draft are changed.
- Validation: extend the disposable `wizard-reconstruction-check.py` through three-view approval, front replacement, repeat save and provenance; browser inspection of view review; run `npm.cmd run test:e2e` once after integration, then `git diff --check`.

### WP8 — Run the Freydis artistic acceptance pilot

- Dependencies: WP7; explicit authorization for implementation/live trial and library writes where applicable.
- Files/interfaces: new Moonsea wizard session and its normal service/queue artifacts; this plan's recorded pilot evidence. No source-image/prompt/style edits outside that session.
- Work: preflight catalog IDs/hashes and available existing models/AI Proxy; new brief using original identity, no axe, jaw-bounded hair and current Moonsea style. Review front against original and comparison before generating other views. Apply selected true-up corrections, then complete three views only after front acceptance. Save through the normal wizard after Joe approves outputs.
- Acceptance: Joe judges the front a better identity match than the supplied comparison, accepts hair/axe/style, and accepts the coherent three-view set. Record actual IDs, prompts, reports and rejected attempts. Unsatisfactory art leaves this packet incomplete even if every software check passes.
- Validation: visual comparison at full-body and face/hair scale; read back saved provenance/set order and verify image hashes. Use AI Proxy; if direct ComfyUI is needed, follow the existing request-to-start-Desktop rule. Do not run the unrelated live Narrative test.

### WP9 — Adapt Image Generation backend sources and ownership

- Dependencies: accepted WP8 pilot; WP2–WP4.
- Files/interfaces: `ad_hoc_image_generation_service.py`, `image_generation_workspace_service.py`, `ad_hoc_image_generation_router.py`, `image_reconstruction_service.py`, existing `ZetApp` import/provenance forwarding.
- Work: reuse shared target/compare/correct from existing one-off entry; add server-resolved completed selected-result input and ancestry inheritance. Validate universe, request/index/hash and expected board assignment; reserve new capacity without altering selected inputs. Preserve import provenance and v1 route/replay behavior.
- Acceptance: selected txt2img and img2img outputs can start reconstruction without library import; legacy source bindings are not inherited as replacement authority; cleared/replaced selections and late attempts cannot dispatch/apply to the wrong slot. Full board gives an actionable capacity conflict.
- Validation: `python3 -B test-results/image-generation-reconstruction-check.py` with disposable jobs/board/private queue, both parent modes, ancestry and stale/full-board cases; `git diff --check`.

### WP10 — Expose one-off and selected-result actions

- Dependencies: WP9.
- Files/interfaces: Image Generation controls in `zet.js`, `index.html`, scoped `zet.css` if needed; reuse wizard presentation patterns where coherent without unrelated UI refactoring.
- Work: selected-image reconstruction action, shared keep/change brief and comparison/correction controls, original/current/result display, explicit new-result selection and import.
- Acceptance: both entry paths use the same target semantics as the wizard; no silent auto-finish, input clearing, history replacement, duplicate requests, or dirty-field loss; selected-result input is clearly identified.
- Validation: `node --check zet/web/static/zet.js`; `node test-results/image-generation-reconstruction-browser.mjs` on an isolated fixture, plus screenshot inspection and `git diff --check`.

### WP11 — Consolidate validation and affected knowledge

- Dependencies: WP1–WP10 complete.
- Files/interfaces: this plan and documentation owners listed above; add a short ADR for shared target/review ownership and generated-candidate correction inputs, linking ADR 0012 without rewriting its history.
- Work: document actual versions/entry points and reference policy, summarize artistic evidence and unresolved limits, run final baseline if code changed since WP7, review final diff, and complete/archive this plan only after all intended workflows are verified.
- Acceptance: wizard and both Image Generation entry paths are delivered; evidence distinguishes software checks from Joe's artistic acceptance; no new maintained scenario/dependency or unrelated changes. Any failed/unverified portion remains explicit.
- Validation: `npm.cmd run test:e2e` after final code integration; relevant disposable checks only when changes justify rerun; `git diff --check`; inspect final diff and documentation links.

## Validation scope and observed planning results

Existing S1 protects library/source and Narrative authoring; S2 protects the separate Assembly/Dressing path and publication; S3 protects Narrative lifecycle/assembly. None proves new wizard/reconstruction behavior, identity quality, original-versus-candidate attachment policy, or stale true-up fencing. Use the targeted disposable checks above; adding a permanent scenario requires Joe's explicit approval naming the task and gap. Never reuse the normal library/queue/index for fast prepared-response checks.

Observed during planning:

- Repository was clean at investigation start.
- Verified `python3` is Python 3 (`C:/Users/Joe/AppData/Local/Python/pythoncore-3.14-64/python.exe`).
- Read catalog through SQLite `mode=ro`; inspected both original images and the existing session without invoking app startup, generation, review, publication or model calls.
- No application files, library records, queue items, historical plans, or tests changed. Only this new plan is added.
- Application tests were not run for this planning-only change. `git diff --check` passed. The untracked-file `git diff --no-index --check` comparison emitted no whitespace diagnostics (exit 1 for the new-file comparison, plus the normal LF-to-CRLF warning). A disposable Python check passed for every local Markdown link, all 11 work-packet headings, and whitespace.

## Risks, defaults and deferred decisions

- **Identity bottleneck:** text-only reconstruction can lose face geometry. Do not declare success from a detailed description or a “no mismatches” model answer. The front pilot must establish improvement before multi-view expansion and Image Generation rollout. If it fails, record why and propose the smallest evidence-backed reference-policy change for review.
- **Regressions during correction:** fixing hair can alter face, hands or clothing; compare every new result against the whole target and allow keeping the previous candidate. Repeated corrections do not prove convergence; Joe controls iterations.
- **Wrong authority:** the comparison image is a drift example, not the source of truth; the old wizard explicitly preserves the axe. Neither should seed the new effective brief accidentally.
- **Unseen views:** the original does not establish all profile/back details. Retain explicit minimal proposals and visibility-aware review; no claim of factual recovery of hidden anatomy/outfit construction.
- **Orientation:** previous draft reviews report near-frontal three-quarter/head-turn problems. Verify the existing requested camera/anatomical-side contract with the pilot; do not redesign view geometry or restore retired pipelines.
- **Defaults:** full-body front/left-three-quarter/left-profile follows the existing wizard and unfinished session. Broader angle lists, portraits as a second set, outfit variants, per-region editing/masks, automatic correction loops and original-pixel identity-reference rendering are deferred, not hidden prerequisites.
- **Approval boundary:** implementation is now authorized. Artistic acceptance of the front and each output remains Joe's decision; no production deployment or implicit catalog publication.

## Progress and decisions

- 2026-10-15: investigated code, phase-1 contracts, approved tests, live read-only catalog/images and unfinished wizard draft; completed this plan. All implementation packets remain pending.
- Shared target intent must survive every comparison/correction; removed equipment is not an identity error. Develop and judge the workflow in the wizard before Image Generation rollout.
- Keep phase-1 original-source analysis-only rendering policy initially; add generated-candidate img2img true-up and approved-front view references under a documented distinct contract.

## Final results

Local implementation is complete for the shared services, wizard, Image Generation and documentation. The live artistic checkpoint and final Freydis reference set remain incomplete; this plan stays active. No production deployment or normal-library publication was performed.

## Implementation progress (2026-10-15)

- WP1–WP7: implemented locally; shared v2 targets, intent-aware reports/correction prompts, wizard reconstruction/front/other-view integration, retry, UI guidance and transactional publication provenance. Source-style legacy sessions retain their semantics.
- WP9–WP10: local backend/UI wiring implemented for prepared-response verification; this does not constitute rollout or artistic acceptance. Ordering adjustment: validate both hosts against the same frozen target now, while retaining WP8 as the gate for claiming quality or deploying. No production rollout was performed.
- First disposable `python3 -B test-results/reconstruction-check.py` passed shared constraints, original-pixel exclusion, conflicting correction rejection, three-view publication/repeat save, front-anchor invalidation, selected-result ancestry/idempotency and stale selection. Subsequent retry/browser hardening is being validated.
- Approved `npm.cmd run test:e2e`: all 3 existing scenarios passed (26.3s). No permanent tests added.
- WP8 remains pending artistic acceptance; WP11 documentation and final checks are in progress.

### Final implementation evidence and remaining work

- WP1-WP7 and WP9-WP10: complete locally, including frozen target precedence, structured reports, correction compatibility, original-reference exclusion, exact selection/source fencing, asynchronous wizard dispatch, separate review/render retry with saved seed, side views, idempotent publication provenance and both UI entry paths. Image Generation integration was developed/checked locally before artistic acceptance; no production rollout is implied by this sequencing adjustment.
- WP11: affected code map, data/invariants, prompts, local characters, library and testing documentation synchronized; [ADR 0013](../../Docs/DECISIONS/0013-shared-reconstruction-target-and-true-up.md) records the durable policy. Existing non-UTF8 bytes in LOCAL_CHARACTERS.md were preserved while adding an ASCII-only section. Final diff reviewed.
- `python3 -B test-results/reconstruction-check.py`: passed after final backend changes. It combines the planned packet helpers into one ignored disposable integration check, including correction conflicts, hashes, three-view publication/repeated save, front invalidation, selected-result ancestry/idempotency/staleness, legacy reads, interrupted analysis, and failed-render retry preserving payload/seed. No maintained tests or dependencies were added.
- `node test-results/reconstruction-browser.mjs`: passed against an isolated fixture on port 8767; actual browser journey covered wizard intake/brief/render/comparison/correction/front approval/resume, Image Generation selected-source/compare/correction, dirty refinement preservation, and desktop/850px layout. Screenshots visually inspected; checkbox/textarea layout adjusted. No browser errors. Temporary servers stopped after verification.
- `node --check zet/web/static/quick_character_wizard.js`, `node --check zet/web/static/zet.js`, Python AST/import checks and `git diff --check`: passed.
- Approved `npm.cmd run test:e2e`: first full run passed 3/3 (26.3s). A repeat run had a transient ASGI error during S2 (S1/S3 passed); retained failure artifacts were inspected. S2 alone passed (8.9s), and the final full run passed 3/3 (28.1s). No unrelated Assembly code or test was changed to hide that failure. Final run log: ignored `test-results/reconstruction-e2e-final.log`.
- WP8: real `codex:gpt-6-luna` analysis of the original Freydis pixels succeeded in an isolated pilot (`test-results/freydis-pilot`, session `ba7d4a0a95a3459ca280f72c43c00ca5`). The first real draft exposed view-list/discarded-equipment detail leaking into reusable appearance; instructions were narrowed, then real reanalysis produced a stable appearance-only brief with jaw-bounded hair, no axe, empty hands and zero questions/proposals. No candidate/front selection or publication was performed. Readable output: ignored `test-results/freydis-pilot-brief.md`.
- The attempted live front preflight did not reach dispatch: ConfigService rejects normal-library/shared-queue configs under `ZET_WORKER_MODE=1`; a private fixture render path also needs an available render service, and `127.0.0.1:8188/system_stats` was unavailable. No worker guard was disabled and no ComfyUI Desktop was launched. The normal Moonsea library and queue were not written by this trial.
- Required next checkpoint: run the new build through its authorized runtime/AI Proxy (or provide a configured isolated render service), generate the Freydis front, let Joe judge identity/hair/axe/style against the original and comparison, then correct/approve the front and remaining views before library publication. Original-pixel identity-reference rendering remains deferred if text reconstruction cannot meet that quality bar. Keep this plan active until that artistic result is accepted.

### Live front trial continuation

Joe clarified that the analyzed brief is acceptable to proceed, but artistic acceptance requires an image. The earlier direct-port preflight was incomplete: the existing AI Proxy is healthy and deliberately stops managed ComfyUI while idle. Its `/_proxy/status` confirmed managed ownership with no blocker. The isolated new wizard now submits its frozen front render through the existing Zet Image Generation HTTP API; the normal runtime owns AI Proxy dispatch, preserving the worker's fixture-only configuration guard. No production deployment or new renderer process/controller is introduced.

Ignored helper `test-results/freydis-pilot-http-render.py` bridges only the pilot's submit/status/result calls to that transport, persists expected-to-actual request IDs, and reads this specific job's persisted seed for provenance. Front request: `7fa15db5893f4b5b974c6c5f86eb8401`. Wizard state/target and comparison remain in the isolated pilot. This creates a real Image Generation job in normal runtime history; it does not change the reference catalog, preferred references, pipeline locks, or workspace selections. Front approval and publication remain Joe's decisions.

- The first live front completed through the existing runtime: pilot candidate `92d3e458ed5f4de0bab373c9d90c1152`, seed `7467324578260900900`, local review copy `test-results/freydis-pilot-front.png`. The axe was removed, but visual inspection found a covered abdomen, added trousers, missing knee guards and an invented blue clasp. The initial broad automated comparison missed this drift.
- Narrow prompt correction in `ImageTrueUpService.compare` explicitly asks for actual garment coverage, knee/boot armor and clasp/material comparisons rather than broad outfit resemblance. Real re-evaluation reported exposed-midriff, thigh-coverage and knee-guard drift while correctly marking axe removal as intentional. Report `b46ddccf02784e739ca4d2819d0e8b45` is retained with the isolated task. No permanent tests added.
- One scoped true-up is being run through the shared correction service and normal transport API, using only the styled candidate as its render reference. The selected three report corrections plus explicit original-clasp/hair instructions retain empty hands and prohibit restoring the axe. Front remains unselected; no other views or reference publication have been performed.

- The first live true-up completed: Image Generation request `e5d1d0777bab4bae8d07685b019bbcbc`, seed `2203257702795665192`, pilot candidate `51368d8e9a7b4792b0bd776658fd7bdd`. Review image: ignored `test-results/freydis-pilot-front-true-up.png`. The actual frozen render payload was checked: img2img with exactly one reference, whose SHA-256 matches the first styled candidate; original source pixels were absent.
- Visual inspection confirms trousers were removed, knee guards were added and the blue clasp was replaced by a metal ring. Hair length and exposed-midriff corrections did not take; the updated comparison reported both, plus a potentially overly photographic finish. No front selection, side-view generation or reference-set publication was performed. Present both original and current front to Joe for concrete feedback; these are working drafts, not accepted artistic results.
- Broad-comparison failure and landmark-check improvement are recorded in PROMPTS.md; subsequent comparisons use instruction version 3. The disposable backend integration check and `git diff --check` passed after the prompt refinement; final checks repeated after recording the version boundary.

### Joe's front feedback and focused correction (2026-10-15)

- Joe approved the facial identity and overall style of candidate `51368d8e9a7b4792b0bd776658fd7bdd`. Full-front acceptance remains pending: restore exposed midriff, shorten the long swept hair, show short white locks rather than a shaved opposite side, and restore the cloak over both shoulders. Preserve axe removal. These clarify original fidelity and do not authorize redesigning the face or style.
- A live compatibility check falsely rejected source-midriff restoration as changing an unaffected costume feature. True-up instruction version 4 distinguishes expected source detail from observed candidate drift, including when the analysis omitted that detail; partial feature approval does not approve every candidate feature.
- Midriff pass completed as candidate `f454085ce0c1486ab11d827b5112d452`, runtime job `50186c86e0884213830de4f02366dfa6`, seed `6665543090003538529`. Visual inspection confirms exposed abdomen/navel, with hair and single-shoulder cloak still unresolved. Ignored review image: `test-results/freydis-pilot-front-feedback.png`.
- Pilot interruption note: a concurrent PowerShell session-file read blocked atomic replacement; restarting the helper initially hit its incomplete status stub and marked the interrupted candidate failed. An additional runtime job `e7baae8d8446419e8fb0ee7c96867067` exists from that interrupted attempt. This is pilot scaffolding, not evidence of a production render failure. Avoid concurrent file readers during pilot updates; no library asset was published or selected.
- Correction composition now uses the validated self-contained edit, frozen style, required changes and view context without repeating the initial full appearance description. This removes competing generic costume wording from scoped edits while retaining target validation and provenance. A focused hair/cloak pass is in progress from the midriff candidate, retaining the accepted face/style and exposed abdomen.
- `python3 -B test-results/reconstruction-check.py` and `git diff --check` passed after both compatibility and correction-composition changes. No permanent tests or dependencies added.
- Focused hair/cloak candidate `403131caf44c4709a6878c4330e00467` (job `ee82c4ae1bf443efa541dbfe6a0e8bf5`, seed `6849804044447532622`) shortened the swept hair but retained the shaved-looking short side and one-shoulder cloak. A single cloak edit then produced `87cde16dc6ad4c3dbd2c5324301944c4` (job `bf669b7a3f9044259768be3ea5e29f90`), adding burgundy fabric over the second side, still narrower than the original's broad drape. Ignored review copies retain each pass. Face/style and midriff remain visually stable; all fronts remain unselected.
- A short-side-only prompt asking for ear-length hair was rejected as conflicting with the closely cut target; that wording was too broad. The next request retains closely cut, approximately one-centimeter white locks and exposed ear, specifically replacing gray shaved-looking scalp. No target revisions or original-image render bindings were introduced.
- Joe reiterated that the goal is generic prompting/rendering/review with operator-led custom iterations and eventual individual handwork, not automatic perfection of this example. Both interfaces now explain suggestions/custom feedback, repeated review and acceptance when close enough; the wizard retains earlier attempts. These are guidance changes over existing controls, not new acceptance gates or automatic correction loops.
- The in-flight short-side pass finished as candidate `f38954d37d6e4b3b83a897c7bdcd306a`, job `370701aa8c90472983bbea04abbafb42`, seed `1430958008504265770`; review image `test-results/freydis-pilot-front-short-hair.png`. Midriff and shortened swept hair remain; the short side still looks too shaved and the second cloak shoulder remains narrow. Stop further agent-driven cosmetic trials here for operator review. This is a draft, not full-front artistic acceptance. No selection, other views, publication or deployment occurred.
- Actual saved payload verification: exactly one render reference, SHA-256 `ad83482780ad3275a7cee6afdb69dda2762790162b007ee435a445e0555a8d31`, matching the prior styled cloak candidate. Original source pixels remain absent. Final UI JavaScript syntax and `git diff --check` passed; the disposable shared-service integration check passed after backend changes. No new permanent tests were added.

### Operator-first workflow ready locally

- Joe authorized commit, push and deployment after verifying original/candidate side-by-side review. The existing universe reconstruction review already pairs the original with the selected candidate. Extended that pairing to source-style wizard sessions too and retained two columns on narrow screens; the original stays beside whichever attempt is being reviewed. Deployment authorization includes the publication/merge step proposed in the preceding response. No new artistic or approval gate is added.
- Side-by-side browser recheck passed with actual bounding-box assertions at desktop and 850px widths, plus the existing wizard/Image Generation iteration journey. A first fixture startup encountered a transient Windows atomic-file read denial; a fresh startup and complete browser run passed. No live generation or library publication was needed for this check. Production promotion is authorized and in progress.

- Joe accepted the improvement as sufficient to proceed and wants to experience the generic process. WP12 is complete: direct suggestion/custom edit composition removes the model compatibility gate and its extra model call; explicit latest feedback can change earlier artistic direction. Image Generation carries feedback into the next target and submitted metadata. Wizard comparison receives refinement context.
- The primary wizard view now presents generation, a custom-change field, Try these changes and Use this front/view. Analysis/description editing, prior attempts and suggested changes are collapsed. Generating uses the current description without a separate checkbox approval. A review failure does not block choosing/refining a rendered candidate or saving an operator-selected set. Image Generation permits custom-only edits while its comparison is pending or failed. Technical source/selection integrity remains internal; no new gate or history requirement was added.
- Disposable integration/browser checks passed, including first wizard render without the checkbox, correction/selection/resume and Image Generation custom feedback. Integration also verified choosing/publishing a review-failed candidate and custom feedback surviving Image Generation reconstruction ancestry with matching submitted target metadata. Browser screenshots inspected. All three approved fast scenarios passed (26.8s). JS/Python syntax and `git diff --check` passed; no permanent tests/dependencies added.
- Temporary browser fixture stopped after verification. A subsequent fixture check initially encountered its still-running child process; the exact owned fixture PID was identified/stopped, then the final integration check passed. Production was not stopped.
- WP13: normal runtime `/api/deployment` reports production revision `e23377f3f4b9d065b411e91ba4843869c9fd443a`; available merged main is `64f5e78827364d6abf16973c4e12d12a1ef3cbf6`. This uncommitted local implementation is absent from both, so an ordinary restart/update cannot expose it. Runtime contract is unchanged with no manual migration required. Local result is ready for review; publishing/merging this work and promoting the runtime require Joe's approval under AGENTS.md external-write/deployment boundaries. No commit, push, merge or deployment performed in this follow-up.
