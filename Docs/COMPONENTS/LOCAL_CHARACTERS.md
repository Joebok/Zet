# Local character assets

## Independent Head-Image Edit (2026-10-22)

**Head-Image Edit** (`head-image-edit`, page `local-head-image-edit`) runs beside
Head-Image. [LocalHeadImageEditService](../../zet/services/local_head_image_edit_service.py)
reuses bounded identity/compiler hooks in the existing head lifecycle, with
independent `Head-Image-Edit` runs, queue ownership, selections and publication
keys. No batches or ad hoc trial results are migrated. Overview's automatic
Body/Head/Assembly/Dressing chain continues to use legacy Head-Image; the new
pipeline has its own page, batch status, Run All Remaining and recovery support.

Accept prompts, run/select FRONT, then open the remaining requested views. Each
independently edits same-batch selected FRONT, including BACK. Partial requests add
only FRONT. Other pipelines retain their predecessor chains. Source changes retain
existing selections/images and locks, with advisory stale-source flags. New
publication/adoption validates captured source/guide identity and bytes.

For a new Head-Image Edit batch, Apply Phase Change can use an uploaded/pasted
FRONT or the same character's available locked Head-Image Edit FRONT from a
different phase. The dashboard previews the chosen lock and directs the user to
lock FRONT in that phase if missing; preview and creation both enforce the gate.
Creation snapshots the resolved image and records its source phase and lock key.
Only the target FRONT uses that source; later views use the selected FRONT from
the new batch. Replacing an existing batch's FRONT source with an upload clears
the locked-phase provenance. Legacy batches need no migration.

On a selected rear-quarter image's **Refine** page, choose **Rear-quarter hair
finishing from BACK** after selecting BACK. The image model receives the quarter
canvas first and BACK second, for lower-hair volume/length only. Scoped correction
supports custom feedback and an optional selected-view render guide with an
explicit transfer scope. Analysis comparison checkboxes do not attach render
guides. Each render creates a separate attempt; **Use this image** explicitly
adopts it into the original slot while retaining history and published bytes.
Later text-only edits retain the established result without citing absent guides.

Assembly's **Head pipeline** setting chooses either head family for each new
batch, using that family's selected source batch or locked images. Saved
`head_pipeline` governs refresh; missing values default to legacy and unavailable
sources never fall back across families. Assembly retains the `head_image`
compiler role and promotes actual source keys, including BACK finishing lineage.

Adult Tsaeytte's separate HEAD_EDIT block follows [the trial evidence](../../Docs-Joe/Qwen-Head-Image-Prompts.md)
without changing earlier sections. FRONT alone anchors front quarters/profiles;
`elf-ears-back` guides rear-right/BACK. Rear-left correction and BACK-guided quarter
finishing remain separate operations. The generalized compiler's live image
quality is unverified. See [Prompts](PROMPTS.md#independent-head-image-edit-authoring-2026-10-22)
and [ADR 0028](../DECISIONS/0028-independent-head-image-edit.md).

## Per-view override images (2026-10-20)

Body, Head, Assembly and Dressing batch views offer Choose image, Paste image and
a keyboard paste target. PNG, JPEG and WebP images up to 32 MB are previewed before
**Use as selected** imports them. No render or advisory model is requested.
The override area starts collapsed. Expanded, its compact paste target sits beside
the image/action buttons, wrapping when the available width requires it.
[LocalCharacterOverrideService](../../zet/services/local_character_override_service.py)
validates the bytes and current selection under the batch state lock. Imports
replace the selected working slot, otherwise use an empty slot or an unprotected
slot without an image. A full board of available images requires selecting a
candidate to replace or explicitly clearing a slot. Active batch/slot work blocks
import. Original candidates/artifacts remain in history; downstream choices and
published locks remain intact.

Use the existing **Lock** action in Selected views to publish the override. When
another image is already locked, **Unlock published image** exposes the explicit
transition before Lock becomes available. Ordinary dependency/publication rules
still apply. Browse/paste drafts survive gallery polling; stale selection uploads
are rejected. Clipboard access uses the shared image-input helper and browser
permissions; choosing a file remains available.

Lock publication carries the source batch label when available and otherwise uses
character, phase, pipeline, and view context. Chain promotions preserve that label
through the catalog transaction; Costume-Dressing still owns its costume
classification and logical reference key.

Validation: approved S2 passed; disposable API checks covered all 32 pipeline/view
imports, replacement, image delivery, stale/invalid refusal and lock preservation.
Disposable Chromium checks covered all four pages, browse, clipboard events,
explicit apply, polling, 390px bounds, and Dressing unlock/lock/reload. Service
checks covered full reserved boards, active/slot fences, concurrent selection,
portable storage and invalid/oversized input. Native device clipboard permissions
and live inference were not exercised. No maintained scenario was added.

## Pipeline view order and continuation controls (2026-10-20)

All four character pipeline pages display view sections and selected-view cards in
render stage order: FRONT, front three-quarters, profiles, rear three-quarters,
then BACK. The review panel's previous/next view controls use this same order,
skipping views without review candidates. This is presentation order; saved view
lists and render scheduling are unchanged. Each view has a Continue control below
its observations and Luna ranking status. It appears when the top Continue control
is available and enabled, shares its label and action, and updates during polling
without replacing unsaved observations.

Validation: the approved character-to-costume E2E scenario passed (1 test, 16.6s).
Disposable Chromium checks covered all four pipelines' view order, control placement,
readiness/polling/busy states, and preservation of unsaved observations. No maintained
tests were added; live inference was not exercised.

## Head rear-view quality pilot (2026-10-19)

[Investigate_Head_Views.py](../../Scripts/Investigate_Head_Views.py) prepares a private
Tsaeytte Adult snapshot and eight BACK prompt/reference recipes, submits an explicitly
authorized 16-image screening through the existing AI_Proxy service, collects results
with reserved request identities, and produces a labeled comparison sheet. Its
`prepare`, `hair-trials`, `confirmation`, `submit`, `collect`, and `sheet` commands require an explicit `--output`;
`prepare` also requires `--batch`. Preparation is offline; submission performs real
inference and must be explicitly authorized. Results live outside the source batch.
The current investigation does not change production prompts, recipes or selections.
After partial human acceptance of ears/neck, `hair-trials` prepares four matched-seed
lower-bob diagnostics instead of the original ear/neck ablations; the 32-render
ceiling is unchanged. The B-004 lower hair is a visual target, not a new render input.
Those four diagnostics did not restore the preferred lower contour. Joe approved
continuing the original silhouette recipe with hair deferred. `confirmation`
freezes twelve matched-seed current/silhouette comparisons across BACK and both
rear quarters, reaching the 32-render cap; `sheet --phase confirmation` produces
the dedicated comparison. No production improvement is claimed before reviewing
these results and the final human checkpoint.
After Joe repaired the AI_Proxy-managed ComfyUI startup failure, all 32 logical
image slots were collected from the existing requests. Some images improve neck
width and rear orientation, but Joe rejected both selected rear-quarter ears as
camera-facing. The agent's earlier quarter passes are withdrawn. The full recipe
is not validated, the pilot budget is exhausted, and no production integration
proceeded. Ear orientation and the deferred lower-bob mismatch remain open.
See the [active pilot plan](../../plans/active/head-reference-quality.md) for its
32-render ceiling, yes/no acceptance gates and conditional integration boundary.

The active character workflow produces and reviews **batches of candidates** for Body-Reference, Head-Image, Character-Assembly, and Costume-Dressing. It reuses prompt compilers while keeping its own run/selection state. Traditional stage-driven generation is retired via [pipeline_retirement.py](../../zet/services/pipeline_retirement.py); retained traditional assets are not local batch IDs.

## Interfaces and workflow

Image review and touch input follow [Dashboard UI](DASHBOARD_UI.md). Review stays
in the viewport when opened from a scrolled gallery, with decisions/selection
outside scrolling details. Compact screens collapse existing batches' new-batch
settings. Selection and lock contracts remain unchanged. Available Luna advice is
expanded above Human decision; Prompt and source is collapsed below the actions.
Pending/failed candidates support details inspection without image-dependent
decisions. Same-candidate polling preserves drafts, disclosure state and focus.

| Responsibility | Implementation / consumer |
| --- | --- |
| Body generation/review | [LocalBodyReferenceService](../../zet/services/local_body_reference_service.py), [Run_Body_Reference_Jobs.py](../../Scripts/Run_Body_Reference_Jobs.py) |
| Head generation/review | [LocalHeadImageService](../../zet/services/local_head_image_service.py), [Run_Head_Image_Jobs.py](../../Scripts/Run_Head_Image_Jobs.py) |
| Assembly and costume-qualified dressing | [LocalCharacterAssetPipelineService](../../zet/services/local_character_asset_pipeline_service.py): `preview`, `create_run`, `execute_run`, `select_view`, `lock_preview`, `lock_selected_view`, rerun/resume/stop methods |
| Shared review/run semantics | [local_image_pipeline_policy.py](../../zet/services/local_image_pipeline_policy.py), [candidate_review_contract.py](../../zet/services/candidate_review_contract.py), [local_candidate_review_contract.py](../../zet/services/local_candidate_review_contract.py), [local_image_ranking_service.py](../../zet/services/local_image_ranking_service.py) |
| Candidate image delivery | [local_candidate_image_service.py](../../zet/services/local_candidate_image_service.py) resolves current candidate membership and contained image paths from the owning run's spec/state without building full run detail |
| Selection, lock and publication | [LocalAssetStoreService](../../zet/services/local_asset_store_service.py), file-available [LocalAssetSourceService](../../zet/services/local_asset_source_service.py), entity image library |
| Overview and sequenced automation/recovery | [LocalCharacterOverviewService](../../zet/services/local_character_overview_service.py), [LocalRunAllRemainingService](../../zet/services/local_run_all_remaining_service.py), [local router](../../zet/web/local_character_asset_pipeline_router.py), app startup recovery |

Inputs include character/phase, normalized requested views, costume qualifier when applicable, source batch/candidate selections, source templates, profile and seed controls. Runs retain specs, snapshots, candidate state, ranking jobs, human decisions, and selections. Outputs include candidate image artifacts and, after locking, approved library image/reference bindings.

1. Preview validates inputs and dependencies. Assembly uses body/head references; dressing uses an assembled character and costume source. Read the service's source resolution before assuming every input must already be locked: selected-batch workflows also exist.
2. Creation snapshots source material and records the run. Rendering queues work through the shared File Proxy; answer harvesting and view-specific evaluation progress persisted state.
3. Rendered candidates are available for Luna ranking and human review immediately. Front-anchor/order requirements differ by pipeline; use the owning service rather than a universal view loop.
4. Current ranking, human decisions, image validity, and selection determine eligibility. Selection and locking are separate operations; promotion may collect a source chain.
5. Lock publication preserves approved image bytes/checksum and a stable logical reference. Available published locks feed identity keys, turnarounds, costumes, phase comparison and scene references.

The shared review page skips unchanged human decisions. Review, selection, and rank
responses carry the same presented run fields as detail, allowing the page to merge
them directly without another detail request. Candidate images use the focused
resolver above; reference previews keep URLs stable for their saved content identity.

Detail presentation uses the loaded run's progression and reference recipes;
slot prerequisites are computed once per view per response. Compiler reference
resolution still reads persisted recipes. Path conversion reuses identical values
within each document walk (see [data model](../DATA_MODEL.md)). A read-only profile
of the reported 64-candidate Assembly batch improved from 2.668s to 0.928s with an
identical presented response; this measures service work, not browser click latency.
The dashboard's startup asset filter preference also tolerates denied browser
storage and keeps the current tab usable. The reported context-storage console
error was not reproduced in a fresh in-app browser, so its exact origin is unverified.

All four pipelines' detail and batch summaries recognize completed publication when
every requested view's current selection matches a published lock from that batch,
including the selected image checksum and any required FRONT anchor. Assembly has
no render-anchor requirement; Dressing retains its optional-anchor setting and matches the costume qualifier.
[LocalAssetStoreService.all_selected_views_locked](../../zet/services/local_asset_store_service.py)
owns this shared check. Stale advisory rankings do not leave these fully locked
batches awaiting selection. This projection does not rewrite saved rankings,
selections, locks, or batch state, and does not override active or stopped work.

## Contracts, failures, and extension

Candidate, source-snapshot, and local asset-lock records persist library-owned paths relative to the bound universe using format version 1. Storage helpers resolve paths before file access, so service and HTTP consumers continue to receive usable filesystem paths while newly written JSON remains portable. Image bytes, checksums, selections, and lock state remain governed by their existing workflow contracts. See [portable library references](../DECISIONS/0011-portable-library-references.md).

The supported production renderer is ComfyUI with registered Qwen Image 2.1 profiles in [Local_Render_Presets.json](../../Config/Local_Render_Presets.json), enforced by [local_render_policy.py](../../zet/services/local_render_policy.py). Historical Stable Matrix/other profiles are not allowed production choices. Use AI Proxy; follow AGENTS before direct ComfyUI operation.

Active edit profiles use the shared Qwen reference sizing policy described in
[PROMPTS](PROMPTS.md). Prepared snapshots preserve source order and are retained
with pending workflow artifacts so retries keep the original edit inputs.

Template-authored image references supplement those pipeline sources. Body and
Head share a Qwen graph builder that now binds all ordered references rather than
assuming one anchor. Body initial candidates and fresh/cached render slots freeze
the compiler's complete resource list. Required sources, view selection and
same-batch ownership still belong to their existing pipeline services. See
[supplemental template images](PROMPTS.md#supplemental-template-images-2026-10-19).
Disposable offline checks covered the four character compilers, Body slot/initial
packaging and all eight Tsaeytte Head views; they establish prompt/binding behavior,
not live image quality. The approved four fast E2E scenarios passed (42.9s).

Preserve the review semantics, live-batch/checksum lock requirements, universe ownership, and immutable dependent locks in [INVARIANTS](../INVARIANTS.md). Failure modes include unavailable external rendering/ranking models, stale rankings, changed/missing source snapshots, invalid batch IDs, missing `spec.json`, missing locked bytes, and interrupted runners. Stop/resume/rerun and recovery must respect superseded work; do not reset persisted state blindly.

Deleting a Body-Reference batch is blocked while its runner still owns the durable runner lock. A persisted active status with no live runner is interrupted work and can be deleted without first changing it to cancelled/stopped; queued asks are withdrawn during deletion.

For a new local asset operation use the local store/services and downstream source provider, not `Assets.json` stage mutation. Data formats belong to [DATA_MODEL](../DATA_MODEL.md); prompt mechanics belong to [PROMPTS](PROMPTS.md).

## Verification and decisions

[S2 in fast.spec.mjs](../../tests/e2e/fast.spec.mjs) previews, creates and starts a front-only Character-Assembly run, applies a prepared image response, waits for ranking, selects/locks it, and repeats for Costume-Dressing. Body/Head prerequisites are seeded with valid batch specs/locks. This does not verify Body/Head generation, other views, multi-candidate rankings, cancellation or recovery. The former Python cutover failures are historical, not outstanding baseline failures. See [Testing](../Testing.md) for the approved baseline and coverage policy.

[ADR 0003](../DECISIONS/0003-local-character-production-boundary.md) records the retirement/renderer boundary. [V5 Realignment](../../Docs-Joe/Zet%20V5%20Realignment.md) describes intent and open questions; it does not authorize a new implementation phase.

## Fixed render slots (2026-10-12)

Each Body, Head, Assembly and Dressing view offers **Stage in Image Generator**.
[ImageGeneratorStagingService](../../zet/services/image_generator_staging_service.py)
uses `CharacterRenderSlots.prepare_input` with the current view recipe and Recompile
choice, validating prerequisites and captured image bytes before clearing the
generator board. This stages the next Generate inputs, rather than replaying a
candidate. It preserves prompt text, render profile/checkpoint, effective dimensions,
prompt-global behavior and ordered references. It neither allocates pipeline
candidates nor changes selections/locks or submits inference. The independent
generator results are not automatically adopted. Minor Characters and refinement
windows are outside this handoff. Missing inputs and unsupported reference limits
leave the existing generator board intact.

Costume Dressing also offers **Stage Rotation**. It uses the view's explicit
selected-view reference recipe, or the closest available different selected view
when the recipe is default. A `none` recipe requires choosing a source first.
The button tooltip names the source; unavailable/rejected/outside-batch sources
are refused. [CostumeRotationService](../../zet/services/costume_rotation_service.py)
compiles a fresh rotation alternative with the accepted batch template overlay
(current templates otherwise), independently of the Recompile checkbox and saved
dressing prompt. Image 1 is the selected dressed edit base; Image 2 is the
original matching Assembly snapshot used only for orientation, stance and framing.
View-filtered costume resources follow in citation order. The garment instructions
preserve openings, continuous rear construction and authored hem landmarks while
allowing template requirements to correct source-image errors. This handoff uses
the same generator replacement/settings/reload behavior above and never adopts
results or submits inference. Rendered fidelity remains an operator assessment.

All four local character pages display eight stable slots per view. Initial FRONT/other-view counts are integers 1–8 (defaults 8/4); planned candidates awaiting an anchor are reserved, not empty. Add renders fills empty positions only. Generate/Regen use the current view prompt with fresh seeds; the view’s Recompile checkbox also applies to these actions and compiles current templates first. Already submitted asks retain their frozen inputs. Regen replaces an unselected candidate with a new identity; render Retry retains the failed render inputs/seed. Failed advisory review keeps its separate retry behavior.

[CharacterRenderSlots](../../zet/services/render_slot_service.py) owns atomic allocation and protection behind [LocalImagePipelineWorkflowService](../../zet/services/local_image_workflow_service.py). Detail includes `slots_by_view`, `slot_controls`, candidate slot numbers and action reasons. Render actions persist `slot_render_ids` before scheduling; an independent per-run collector submits/reconciles them without taking the batch runner lock. Other slots remain usable while renders run. Clear detaches running candidates so late answers cannot fill replacement slots. Startup recovery reattaches this collector. Candidate definitions added after creation live separately from mutable review state so rerun resets retain them. Clear detaches active membership and retains provenance/artifacts. Legacy galleries over eight remain visible; clear surplus unprotected candidates to reach capacity.

The browser polls at two-second intervals while active, including in review. Updates patch slot/status sections and preserve unsaved observations, human decisions, focus and current candidate. Once a view has a complete ranking, candidate cards and previous/next review navigation follow Luna order, with unranked occupied candidates after ranked candidates in physical slot order; empty slots remain after candidates. This is presentation only: each card retains its physical slot label and its actions remain bound to that slot. Incomplete, stale or failed rankings leave cards and review navigation in physical slot order. Selected/locked outputs require explicit protection transitions; adding alternatives does not modify immutable library locks. Body ranking compares the valid, non-rejected candidate set. See [ADR 0007](../DECISIONS/0007-stable-render-slots.md) for the original slot design; the review contract is now ranking-only.

Re-running a whole view in Body-Reference, Head-Image, Assembly, or Dressing targets every candidate in that view, including candidates created through supplemental slots. The batch runner may skip slot-managed candidates during ordinary recovery because the slot collector owns those asks; the explicit view target lets the rerun render and rank the full replacement set.

Head-Image **Re-run failed** persists the requested view and exactly the failed or
human-rejected candidate IDs before dispatch. These explicit targets include
supplemental slots without resetting kept candidates. Disposable checks exercise
the actual reset/runner methods for both front-quarter views with prepared renders;
S2 remains Assembly/Dressing regression coverage and does not prove live Head dispatch.

Body-Reference batch/view **Recompile** refreshes the affected candidates' effective
prompts, including mutable overrides and supplemental slot definitions, from the
current templates and active batch revision. Protection checks precede compilation.
Batch, view, failed-candidate and legacy downstream resets clear frozen render
inputs, reference previews and reference hashes so pending candidates do not show
references from discarded renders. Without Recompile, resetting leaves saved prompt text unchanged;
render Retry continues to replay its frozen inputs and seed.

Re-evaluate is the single dashboard evaluation action for all four pipelines. [LocalImagePipelineWorkflowService.reevaluate](../../zet/services/local_image_workflow_service.py) refreshes Luna ranking and AI prompt-improvement observations for existing harvested images, for one view or every rendered view in the batch. Unrendered views are skipped. It preserves human decisions, notes and selections and does not invoke the render runner or retired defect gates. Existing active ranking/observation work is reused; completed evaluation records receive a new identity and late updates remain fenced. The separate Rank images/Re-rank and Re-analyze buttons are removed; ranking and observations remain visible.

Explicit Re-evaluate refreshes candidate file bookkeeping through
[reconcile_candidate_harvest](../../zet/services/image_harvest_service.py). Under
the run lock it checks every target file before refreshing missing or outdated
hashes. A current candidate's existing file is sufficient for local review; saved
hashes, receipts and historical requests do not gate availability. Recovered render
state enters human review without changing decisions, observations, selections or
image bytes. Cancellation, candidate/attempt replacement and evaluation ownership
still fence publication. Hashes continue to identify stale rankings and changed
inputs. This does not change immutable published-lock or transport validation.
See [ADR 0021](../DECISIONS/0021-file-based-local-image-availability.md).

Reference previews above candidate cards deduplicate repeated per-candidate snapshots by image checksum, preserving the prompt role and image label in the caption. Older snapshots without checksums fall back to their role and prompt label.

Comparative Luna ranking in all four pipelines uses each candidate's supplied
reference snapshots, rather than substituting FRONT for every non-front view.
[supplied_ranking_references](../../zet/services/local_image_ranking_service.py)
maps frozen render inputs (or adopted refinement ancestry) to labeled image
attachments, retaining source roles, source views and matching prerequisite inputs.
The prompt asks for visible identity/design consistency across views while still
requiring the target orientation. Identical recorded checksums share an attachment;
each candidate retains its own reference mapping. Explicitly empty inputs stay
empty. Historical candidates use saved reference-image metadata where available,
otherwise the configured view recipe and existing pipeline inputs. Missing recorded
images fail ranking instead of silently using FRONT. Existing rankings are unchanged
until **Re-evaluate**; single-candidate views still receive deterministic rank #1.
Head-Image ranking additionally compares visible distinctive anatomy (shape,
head-relative proportions, attachment, taper and perspective) with each candidate's
mapped references. It prioritizes clear identity/anatomy failures over cosmetic
polish and explicitly penalizes shortened or human-shaped ears when the supplied
design establishes elongated pointed ears. Natural hair/skull occlusion remains
valid; exposing hidden features or changing the target angle earns no reward.
Reasons must describe the visible anatomy accurately. This is advisory model
guidance, not a deterministic anatomy gate or evidence of live ranking accuracy.
Disposable prepared-response checks verified the Head ranking request, attachment
mapping and result handling; approved S2 passed. Tsaeytte Adult's front-quarter
ear wording was also added to its master and accepted batch revision for
`20261019_170553_311743`; eight text previews passed without inference. See the
[completed plan](../../plans/completed/tsaeytte-quarter-ear-ranking.md) for limits
and unchanged-image/ranking checks.
Disposable prepared-payload checks cover this mapping; S2 covers one-candidate
Assembly/Dressing publication and does not establish comparative model quality.

Existing S2 verifies Assembly/Dressing publication. Joe separately approved disposable checks for costume deep-link loading, card containment, current prompt/Recompile behavior and overlapping slot actions. Those checks use prepared renders/rankings; no new maintained tests or live services were added. Full Body/Head generation and general restart recovery remain outside maintained coverage.

## Prompt review, staged generation and image refinement (2026-10-18)

New Body, Head and Dressing batches start with text-only governing-template review. Assembly bypasses this review, as described below. [LocalPromptPreviewService](../../zet/services/local_prompt_preview_service.py) compiles all eight view prompts through the existing compilers with declared future reference roles. Preview artifacts are explicitly non-renderable; production compilation still validates actual image files. The analysis receives complete sources, compiled prompts and compact source maps, without images or image-review observations.

[LocalTemplateRevisionService](../../zet/services/local_template_revision_service.py) saves version-2 reviews with individual source corrections, affected views and rationale. Suggestions start unchecked. Checkbox decisions persist; acceptance applies only selected, nonoverlapping exact source edits after checking master baselines and recompiles a READY child version. No-change acceptance is valid. Operator feedback and manual child edits support iteration. Accepted sources are batch-local overlays; master promotion retains its separate confirmation, baseline checks and partial-write journal. Legacy version-1 records and pending continuations remain readable.

The governing-template UI offers **Skip improvement — use current masters** to
freeze, compile and accept current sources without AI analysis. **Restart from
current masters** recompiles and starts a fresh analysis without inheriting the
active batch overlay; earlier versions and existing images remain available.
**Reload saved results** (formerly Refresh revisions) only reloads saved records
and analysis status. Ordinary Analyze prompts can continue from a saved READY
version. Restarting analysis before FRONT requires acceptance or skip again.

Correction checkboxes sit beside their text, with acceptance actions below the
findings. Master/proposed diffs precede batch-use and master-update actions; the
parent-version diff is omitted. **Edit master template**, below each source diff,
opens a separate proposal editor. **Save proposed** compiles a READY child without
an AI job, changing masters or selecting that child for new renders. **Use for new
renders** explicitly accepts/selects it for the batch; **Update master templates**
retains the separate confirmed promotion. Project-template edits can subsequently
be published through Restart's **Create template PR** recovery action; promotion
itself does not publish anything. See
[update recovery](../GitHub_Task_Workflow.md#accepted-template-edits-and-update-recovery).
The status block before compiled prompts
reports pending corrections, unsaved editor text, selected batch sources, master
updates and drift from the captured baseline. **Start Front Renders** at the end
uses the same FRONT continuation and readiness checks as the top Continue control;
after FRONT opens, further generation uses the existing view controls.

[LocalCharacterProgressionService](../../zet/services/local_character_progression_service.py) owns explicit Continue boundaries: FRONT, both front quarters, both profiles, both rear quarters, then BACK. Body, Head and Dressing pairs use the selected same-side predecessor. Body-Reference BACK uses selected FRONT; Head/Dressing BACK default to the selected rear-left quarter and may use rear-right. Assembly runs its requested views without stage waits, using only matching body/head inputs. The Body rule also applies to future Generate/Regenerate actions in existing staged batches; saved renders and Retry retain their frozen inputs. Existing matching Body/Head/Assembly/costume inputs retain their roles and order. Preview includes required ancestors for requested partial batches; front-only batches remain front-only. New generation, supplemental slots, runner resume and automation respect the opened stages. Overview automation and Run All Remaining pause for human prompt/selection/Continue actions. Existing batches retain legacy sequencing until explicitly entering prompt improvement.

Prompt previews declare those future predecessor inputs through the same compiler contracts used for actual renders, even before any batch images exist. Shared reference descriptions keep preview and render prose identical for equivalent bindings; actual generation substitutes selected image paths and candidate provenance. Body task/image-input text is conditioned before its Qwen wrapper is added, and Head, Assembly and Dressing preserve their own ordered prerequisite roles. See [prompt preview compilation](PROMPTS.md#character-prompt-review-previews-2026-10-18) for the validation boundary and historical-review limitation.

Selected-image cards link to `/local-character-refinement`, a dedicated resumable page. [LocalCharacterRefinementService](../../zet/services/local_character_refinement_service.py) freezes its original image and chosen selected-view comparisons. All other available selected views are initially offered; the operator can include any subset or none. Shared true-up analysis distinguishes visible defects and continuity from occlusion and intentional asymmetry. Findings remain unchecked suggestions; custom-only edits need no successful report. Correction renders use exactly one edit-base image, selected findings and feedback; comparison images are analysis-only. Earlier accepted edits remain unless explicitly overridden. All work uses registered AI_Proxy continuations and existing Qwen image services.

**Use this image** explicitly places a new candidate identity in the original selection's occupied slot and selects it. Original/refinement images remain in session history; the adopted candidate has a separate gallery copy. Adoption checks the current selected identity and never changes published image bytes. Future stages use adopted selections. Changed predecessors produce advisory reference warnings without clearing selections or requiring re-review, regeneration, acknowledgment or new rankings. Missing images and invalid ownership remain errors. Generated images stay subject to the existing separate explicit publication action.

Routes extend `template-revisions` with decisions/acceptance, retain `activate`/`promote`, and add view `refinement` plus batch `refinements/{session_id}` detail, analysis, edit, retry, adoption and images. Business logic stays in services behind the shared workflow boundary. See [ADR 0025](../DECISIONS/0025-character-review-stages-and-refinement.md), [data ownership](../DATA_MODEL.md#character-template-revisions), and [Testing](../Testing.md). Prepared checks establish workflow behavior, not live visual quality.

## Style-unification batch review (2026-10-14)

Body and Head bootstrap from text; other views may use newly generated local front anchors. Dressing uses that local chain, with costume-only references remaining narrowly bound. Assembly uses matching body/head sources without a view anchor. Shared character instructions use the existing fine-grained head/body visibility tags to separate visible identity facts from rendering treatment. Prompt wording seeks dimensional anatomy and differentiated materials; it does not establish observed image quality.

Joe approved initial Tsaeytte batch review for FRONT (8), FRONT_LEFT_3_4 (4), and BACK_RIGHT_3_4 (4), through Canonical Adventure Gear, in existing galleries. Provisional selected-batch sources can advance this chain without replacing published locks. New images require explicit source-layer refresh before appearing in an already frozen Narrative assembly. Local implementation checks passed; live batch review remains pending rollout of the new prompt templates.

Local Head, Assembly and Dressing candidates track the staged ask�s `target_output_file`, matching the background harvester�s destination. A runner must not wait on a separate candidate filename after the generic harvester has consumed the answer. The live style-unification trial exposed this handoff race; existing successful outputs were recovered by matching ask receipts and seeds without rerendering.

Costume-Dressing batch lookup compares normalized workspace qualifiers, so a costume display name and its underscore slug resolve the same batch. Costume links also accept either identifier when selecting the existing gallery control. Other costume qualifiers remain isolated.


## Quick Character reconstruction and true-up (2026-10-15)

`QuickCharacterWizardService` offers source-style preservation or opt-in universe-style reconstruction. New sessions default to universe reconstruction in the UI, with preserve/change inputs, model choice, frozen style, editable brief and unseen-detail proposals/questions. Legacy sessions retain source-style semantics. The wizard remains independent of Body/Head/Assembly/Dressing prerequisites.

Shared reconstruction creates the edited target; front generation uses text only. Review shows original/candidate images and selectable corrections. True-up uses the styled candidate and retains intentional edits. Joe approves the front before three-quarter/profile generation from that anchor. Requested angle/visibility applies to head and torso together; hidden details are not automatically defects. Full body/portrait and left/right retain their existing output choices.

Intent/description changes invalidate approvals; a new front invalidates views using the prior anchor. Failed review retries separately; failed renders with saved inputs retry the submitted prompt/references/seed. Background submission is fenced against abandonment/revision/front changes. Transactional publication records target/style, actual correction lineage, comparison and seed, with source evidence distinct from approved outputs. Freydis's artistic acceptance is pending; disposable checks do not establish identity improvement. See [ADR 0013](../DECISIONS/0013-shared-reconstruction-target-and-true-up.md).

Operator trial update (2026-10-15): Joe accepted the Freydis improvement as sufficient to proceed. The wizard now emphasizes Generate, custom feedback, Try these changes and Use this image. Analysis, suggestions and earlier attempts are optional details; generating uses the current description without a separate approval checkbox. Failed automated review does not block choosing or refining a rendered image. Custom feedback composes directly without model compatibility approval; see PROMPTS.md and ADR 0013.


## Minor Characters: alignment and true-ups (2026-10-15)

`MinorCharacterService` handles named universe-local workspaces, input analysis and publication. `MinorCharacterWorkflow` in `minor_character_workflow_service.py` owns current boards, stage prompts, rendering and review. New workspaces use the current workflow only; retired records are excluded without migration or file deletion. The Quick Character notes above describe preceding view/history rules, superseded by [ADR 0015](../DECISIONS/0015-minor-character-alignment.md).

Style alignment reconstructs identity, costume and details in universe style without enforcing an official view. Suggested changes/custom feedback refine it. Select a style image before generating any view. Every view independently uses this selected image with a short direction-only prompt, without the full character brief. Select an aligned view and Continue to true-ups before refining it. Only generated view true-up candidates can lock into Inventory; style candidates and carried alignment images never lock. Pending/failed review does not block selection or custom refinement.

New Qwen Image 2.1 style prompts request one neutral character reference with explicit full-body or portrait framing. Direct style references keep their existing order and identify the first image as primary identity; multiple images use `<imageN>` roles. Reconstruction-based style generation still uses original pixels for analysis only. View prompts name the visible anatomical side instead of a screen-side facing direction, align head/torso/hips, and preserve identity and costume. True-ups edit the selected candidate as a canvas and preserve unaffected composition and design. Generic reference labels are not appended to Minor Character render prompts; each candidate retains the actual instruction for replay.

Each stage has one four-slot board. Refinement edits the previewed candidate and carries the selected image, if any, in its same slot as Prior selection; other slots clear. Repeated carry is allowed. Clear/Regen removes that slot's working selection. Additional renders replay the frozen recipe with fresh seeds. Current images retain their own prompt/kind. Revisions reject stale mutations and late results cannot restore discarded slots.
Restarting a view clears that view's working round and selection, returns it to alignment, and starts a fresh render from the selected style image. Restarting Style clears required changes, additional direction and analysis results, resets every stage's working board, and re-analyzes the retained original references. If any view work exists, Style restart requires confirmation that view images and revisions will be discarded. Immutable Inventory locks remain. The current board template candidate's final prompt is shown below custom feedback; it represents the latest round even when an older image is advanced.

Undo true-up restores one prior prompt/supporting state, including frozen findings, checked suggestions and feedback, with every slot and working selection cleared. There is no redo or image history. Regenerate from that recipe or choose different corrections using its private source binding. Private immutable inputs can remain for reproducibility, without discarded-image access. Inventory locks survive clear, refinement, undo and workspace deletion.

Paired review has independent navigation. Right arrows/keyboard keys move among rendered current slots. Small left arrows loop through original and occupied style slots during style work; during view work they loop through original, selected style and selected other views. Images deduplicate by checksum and unavailable entries are skipped. Comparison choice affects display only, independently of primary identity and reference order.

Main Minor Characters navigation saves edits and opens the complete list, including from an editor. Direct character links/history and Inventory handoffs remain. The All Minor Characters button and iteration history are removed. Board actions use `/api/minor-characters/{sid}/boards/{view}/{action}` and `/boards/{view}/slots/action`; mutations carry expected board revisions and services enforce eligibility. See [data model](../DATA_MODEL.md) and [prompts](PROMPTS.md). Disposable checks cover this workflow; S1-S3 are regression coverage, not artistic acceptance.

## Unified AI jobs (2026-10-16)
Ranking, prompt observations and Minor Character analysis/review/render requests
use the common AI job boundary. Generic execution moved to AI_Proxy;
Minor Character continuations persist and resume without session-page reads.
Domain eligibility, immutable publication, revisions and image binding rules stay
here. [Shared AI jobs](AI_JOBS.md) owns collection/receipts, queue activity and the
capability-aware model popup.

Ranking requires the current render's successful harvest receipt, validated bytes
and committed image hash. Ranking staging uses the run's state lock and a durable
publication reservation. Minor review uses a deterministic workflow
identity and process-shared session locks; its candidate image is committed before
review starts. Admission rechecks current membership, cancellation, hashes and
evaluation immediately around publication. Queued render work does not fail
solely because a subscriber's 30-minute wait elapsed.

Reconstruction preparation verifies its frozen input fingerprint and reuses its
saved record after suspension. Draft-application and analysis-to-candidate
checkpoints prevent replay from creating another reconstruction or candidate.
See [AI jobs](AI_JOBS.md) for common lifecycle/receipt ownership.

## Recurring runner recovery (2026-10-17)
The backend storage recovery host discovers orphaned Body, Head, Assembly and Dressing work after reconnect and during ordinary polling. It preserves saved target views/candidates and render-only/review intent, rechecks local OS runner ownership at execution, and excludes stops, cancellations, completed locks and human/prerequisite waits. Campaign recovery also respects cancelled batches. See [storage recovery](STORAGE_RECOVERY.md).

## Image availability policy (2026-10-17)

Locks need their recorded permanent file, not retained candidate/batch history or
matching historical bytes. Detail/overview/ranking-observation reads compare saved
Zet versions and current memberships instead of rehashing images. Explicit
Re-evaluate may refresh bookkeeping; fresh render/analysis handoffs still freeze
ordered actual input bytes. Upstream drift is advisory for published locks.
See [ADR 0023](../DECISIONS/0023-streamlined-image-integrity.md).

## Simplified Character Assembly (2026-10-20)

Local Assembly renders use exactly the matching Body-Reference and Head-Image, in that order. The prompt asks for a natural head/neck join while preserving both sources, their orientation and rendering style. FRONT/predecessor references and supplemental image tags do not supply render inputs. Assembly ignores legacy anchor flags and recipes for fresh generation and publication; Body, Head and Dressing retain their existing rules.

Assembly uses **Run front**, then requires an available, non-rejected same-batch FRONT selection before **Run remaining** queues the other requested views together. This selection supplies ranking evidence only; matching body/head render inputs stay unchanged. There is no pre-render governing-template acceptance or predecessor recipe gate. Older partial batches and interrupted work respect the FRONT selection requirement; explicit per-view requests stay bounded, and whole-batch rerun starts again at FRONT. Rendering completion still leaves human selection and publication to the operator. Its pre-render template improvement panel and render-reference controls are unavailable; post-render Character.md improvement is described below. Existing batch revision history remains readable; fresh compilation uses current masters unless a post-render batch version is accepted. `CharacterRenderSlots.prepare_input` upgrades old prompt/manifests with the versioned two-image preparation contract, shared by Image Generator staging. Submitted requests and Retry retain their frozen inputs.

For multi-candidate non-front ranking, Luna receives the required selected FRONT as a separately labeled comparison. Ranking guidance prioritizes matching head-to-body proportions and identity, including relative head size, shoulder/neck scale, torso/limbs and silhouette, while accounting for perspective and visibility. Matching body/head inputs remain candidate-specific evidence. FRONT is never a render input or publication dependency and does not control target camera angle or hidden features. Rankings retain comparison provenance. Changing, clearing or rejecting FRONT makes existing non-front advice stale and supersedes pending evaluations without clearing downstream images or selections; late results cannot commit against a different FRONT. Legacy multi-candidate rankings lacking the current comparison project as stale until Re-evaluate. The single-candidate shortcut remains deterministic. See [Testing](../Testing.md#assembly-front-ranking-validation-2026-10-20) for observed validation and artistic limits.

## LLM purpose separation (2026-10-22)

Character descriptions and costume template wording use Qwen fragment guidance; prompt review and existing correction suggestions use review guidance. Source observations, evidence validation, candidate ranking and Body compliance remain separate skill-free roles. Shared reconstruction retains character-description/review role ownership. No LLM pass is added to deterministic compilation, alignment or correction composition. See [LLM roles](LLM_ROLES.md) for defaults, overrides and frozen guidance.

## Post-render Character.md improvement (2026-10-23)

AI Observations no longer start after ranking or Re-evaluate. Each view's Observations section offers an explicit run action; human notes are saved separately. Each rendered view in the five local character pipelines has a **Post Render Adjustments** button opening `/local-character-prompt-improvement`. A view-scoped private session freezes one review image and its submitted prompt plus the batch source text; it snapshots that view's observations for each proposal. The operator can switch the representative within the view before analysis. Review suggestions are individually selectable and confined to `Character.md` but may change any valid location in that file; other active batch source overlays remain in place. The page uses the same side-by-side master/proposed source diff as prompt improvement.

The selected edits compile all eight text previews and two private renders of the chosen view with current ordered inputs, even if a suggestion cites another affected view. Trial images do not enter slots, selections, rankings, or Inventory. Another observation round can build on the trial. Cancel discards the private trial and leaves only explicitly saved observations. Keep requires completed trials and unchanged source/batch baselines, then writes `Character.md`, activates a batch version, and recompiles available renderable prompts. Unopened views compile from that version when generated. Assembly gains this post-render version path without changing its initial Run front gate. Frozen asks, Retry and locks remain unchanged.

The persistent review and promotion boundary is recorded in [ADR 0030](../DECISIONS/0030-private-post-render-character-prompt-trials.md).
