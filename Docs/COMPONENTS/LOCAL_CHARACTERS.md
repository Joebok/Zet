# Local character assets

## Character Asset Container current outputs (2026-11-06)

`CharacterAssetContainerService` owns the current per-view board lock. A locked
candidate is published to Inventory at either quality. `LocalAssetSourceService`
projects only current container locks to Phase Comparison, Turnarounds, Identity
Keys, Costume counts and new story references. Its source key is
`inventory:<asset_id>`, so a saved story reference can still resolve the immutable
Inventory image after board unlock or candidate clearing. `include_all=True` is a
compatibility reader for legacy keys; it does not participate in new source
choices. Legacy batch routes are no longer mounted, legacy batches are not resumed
at startup, and late legacy writes are excluded from current-output listings.
Disposable checks cover source precedence and saved Inventory resolution after
unlock. The accepted boundary is recorded in [ADR 0048](../DECISIONS/0048-character-asset-container-workflow.md).

## Character Overview Hub

`LocalCharacterOverviewService` returns the selected phase's current published
Body, Head Edit, Head Construct, Assembly and Costume Dressing locks in display
order: front, front left/right 3/4, left/right profile, back left/right 3/4, back.
The Character Asset Container view selector uses the same display order; prompt
conditioning retains its separate orientation order.
Persisted container identity compares view membership independently of order, so
existing containers remain readable when display ordering changes. Reads return
the current display order, and the next write stores it.
New Costume Dressing view settings default to Doll-dressing (w/ Ref) and use
FRONT as the reference view; the selector follows the same display order.
The dashboard links each view card to its owning Asset Container and uses bounded
cached previews. Setup creation/upload controls are visible until Character.md is
valid. The page refreshes on entry/context change and has no active polling.

## Character Asset Container workflow (2026-11-06)

Each mixed-quality view board offers an on-demand **Luna Review**. It compares
all completed Draft and Final images together. The request numbers finished
outputs first in slot order, then maps each candidate's frozen prompt and
ordered inputs to deduplicated evidence. For Costume Dressing, the captured
roles distinguish the Assembly base or layout guide from a dressed design or
rotation source. Unavailable evidence is identified without dropping the
candidate. The board stores rank and full assessment text without changing slot
order and shows the submitted prompt under Review criteria. A successful new
image makes that saved review obsolete. Selection and prompt edits do not.
The action is exposed by the
container view API and its status is included in compact view progress.

The replacement workflow is manual: Assets opens one container for Body Reference,
Head Image Construct, Head Image Edit, Assembly, or a selected Dressing costume.
Its overview shows the current selected or locked image for each view and holds
container-wide authoring and source settings. Open a view card to reach its
mixed-quality eight-slot Candidate Board. The operator prepares, generates,
reviews, selects and locks on that board. Character Overview is the selected-phase
hub for Setup, published base images and costume locks. Its bounded lazy thumbnails
link to their owning container view; the hub does not poll. The active implementation and
cutover status are recorded in the [completed migration plan](../../plans/completed/character-image-production-workflow.md).
Legacy batch contracts documented below are retained only as migration history and
are not part of the container path.

Render actions are explicit: Draft 1, Draft 4, Final 1, or Final 4. The pipeline
prepares the prompt and ordered references; the common image-production path queues
on demand and returns harvested results to the owning slots. Candidate review uses
the shared board actions for selection, locking, retry, regeneration, and clearing.
All five boards use the shared action row: blue Draft 1/4, green Final 1/4, outlined
Delete Drafts, and solid-red Delete Non-Selected. Bulk actions preview affected
slots and candidate images, and fence commit to the current container revision. Delete Non-Selected keeps
selected and locked candidates; both actions wait for affected renders to settle.
The up arrow on a completed, unlocked Draft queues a Qwen upscale. The Draft
stays visible until the validated Final replaces it in the same slot, with the
original generation prompt and captured inputs.
Its Character comparison area lets the operator choose multiple selected-view
images, typically FRONT or the selected opposite-side view. Selected or locked Draft images are not offered as comparisons.

`ImageProductionService` is the shared AI_Proxy image boundary. It validates the
frozen request and owner, publishes the render ask, recovers matching Character
attempts, and validates/collects completed images. Character container storage
still persists candidate status and places the collected image in its board slot.

Head containers use one phase-change source setting for Draft and Final requests.
Choose another phase and either Head Image pipeline; each new FRONT request uses
the current locked, published FRONT there, independent of its quality. A managed
upload is also supported. Existing prepared candidates retain their frozen
inputs. Migration retains old per-quality choices as provenance and prefers the
saved Final choice, falling back to Draft only when Final was not saved.
The container also opens the governing `Character.md` in the shared source editor;
new prompt compilation always uses the current master.

Template improvement is an optional, explicit container action. In candidate
mode, `CharacterContainerTemplateService` captures the candidate image,
submitted prompt, and frozen ordered inputs, proposes and validates a complete
master edit, then compiles a preview for the same view using those captured
inputs. The operator reviews the diff and prompt before accepting through
`SourceEditorService`; a master revision check prevents overwriting intervening
edits. Acceptance changes future compilation only. The latest proposal restores
when its container opens. This path has no run ownership or trial render.

The container overview now has a separate, collapsible Template Improvement
panel. It can analyze current governing sources and eight non-renderable text
prompts without an image or direction, or analyze a finished candidate's frozen
image, submitted prompt and ordered inputs. Reviews persist under the container;
individual exact-text findings start unselected. The operator previews selected
edits and explicitly accepts them with current-master revision checks. Dressing
can propose edits to Character.md and its selected Costume template; both also
open directly in the shared source editor. Assembly supports optional text
review. Current board work never waits for review, and existing asks remain
frozen. The earlier whole-file candidate proposal format remains readable.
Review responses name affected views with canonical eight-view names; recognized
view tags are normalized for compatibility. Each finding is checked separately
for exact source text and pipeline-owned edits. The panel reports rejected
findings with their source, reported views and reason, while valid findings stay
available for selection. A nonempty response with no valid findings fails with
those diagnostics; an empty response is a valid no-change review. Head Image Edit
review instructions and validation confine edits to `HEAD_EDIT_*` sections.

Costume rename retains the same Dressing container ID and candidate board under
the new canonical slug, updating saved paths inside its records. It refuses
active renders or pending publication journals. Costume deletion includes
retained board Inventory IDs in the confirmation preview and archives the
container and its candidate evidence with the costume.

## Render preparation contexts (2026-11-03)

Render actions compare a target-slot context at admission and reservation. New
renders resolve current masters and eligible same-mode references once, compile,
and capture the prompt and ordered reference files. Subsequent changes to original
sources do not gate commit or queueing. Commit checks captured files, target
ownership, slot membership and selection/lock protection. Render Retry retains its
frozen inputs. Source provenance uses library-aware decoding; historical hashes
are advisory. Compact and full views use the same active revision identity.

## Costume Wizard test renders and batch creation (2026-11-03)

`CostumeWizardService._render_job` stages a single FRONT Dressing candidate in a
private per-session library beneath `PipelineCandidates/Character-Pipeline`. It
copies the draft character and costume templates there, while reading the
selected universe's locked Assembly source through the real asset store. The
private candidate is not a normal Dressing batch. The Create New Batch dialog
enables Create only after its current requirements preview is ready; submission
still runs the server's authoritative check. The approved S2 scenario covers
normal Dressing batch creation, while an isolated prepared check staged a wizard
test render without calling live AI services.

## Batch and view reads (2026-11-02)

The shared dashboard loads a compact batch summary or one Draft/Final view from
`LocalPipelineProjectionService`; the former full detail route remains available
to existing callers. Candidate, selected-card, reference and source thumbnails
come from verified source bytes through a machine-local derived cache; review
opens the original. `LocalPipelineComparisonService` provides explicit Draft,
master and frozen-reference reports without changing ranking or selection.
`LocalCurrentMastersService` previews current masters and resolved inputs without
changing a batch revision. New render preparation compiles current governing
masters and eligible same-mode references, then freezes the exact prompt and
ordered bytes. Retry keeps its original frozen inputs. A missing required current
source blocks that new ask with a view-specific reason. Finished images can be
selected and locked from their available current bytes without revalidating old
references or master text. New locks preserve the candidate prompt independently.
Opened views persist a subtle `source_change_fyi` when captured template hashes or
reference identities differ from saved current sources; the marker is permanent
and advisory. Library-relative template source paths resolve from the owning
universe before comparison. A locked view checks only its locked candidate.
Restart and Draft cleanup require a state-bound preview and explicit approval for every affected
selection or lock. [ADR 0045](../DECISIONS/0045-finished-image-source-policy.md)
supersedes the older batch-overlay and lineage rules described in historical
sections below.

Batch summaries also carry compact selected/locked image identities for cards
and review comparisons. Unselected/unlocked view cards include the saved-path
image count within their mode's slots and a queued/running cue derived from
candidate status and pending render IDs. These are metadata-only attention
indicators: they add no queue or image-file reads and use the existing summary
refresh while work is active. The view and action paths retain authoritative
availability checks. Cards open the shared original-image review pane and
arrow through available selected/locked views. A view review can compare with
selected FRONT, its selected opposite side, and the matching locked Draft when
those images are available; view projections still contain only that view's
candidate records.
The policy is recorded in [ADR 0044](../DECISIONS/0044-character-batch-review-freshness.md).

Run front/available, slot generate/regenerate/retry, and view regenerate/re-run failed
now submit durable local preparation operations. Their batch
reservation freezes candidate IDs and seeds, commits targets individually, and
hands them to the existing slot collector. Batch and view Re-evaluate also use
durable operation admission, as do batch Start, Resume and candidate-review retry.
Re-run failed includes renderer failures and human-rejected completed images in
the selected view and mode. Renderer failures reuse frozen inputs; rejected images
receive new seeds and current governing inputs. Preparation rechecks eligibility
and selection/lock protection before replacing each slot.
Retry checkpoints generated-artifact detachment and the candidate state reset,
then reattaches the existing runner. See the [completed plan](../../plans/completed/character-pipeline-operations.md)
for recovery and validation limits.

Character pipeline **Re-start batch** clears candidates, selections and locks in
the displayed Draft or Final mode after a fenced confirmation. It preserves the
other mode and published Inventory copies. Recompile selects current masters by
skipping improvement; Assembly compiles directly. Locked phase-change sources are
refreshed for the selected mode, and Assembly/Dressing resolve current upstream
references when preparing renders. Restart does not dispatch rendering. The
[completed plan](../../plans/completed/character-pipeline-ui.md) records validation.
The durable behavior is recorded in [ADR 0042](../DECISIONS/0042-character-mode-restart.md).

Head Image and Head Image Edit use one FRONT reference source across Draft and Final. A phase/pipeline choice follows the current locked FRONT, without pinning a candidate or matching its quality; a managed upload is an alternative. Legacy mode-specific records prefer Final when present. See the [active phase-source plan](../../plans/active/phase-change-mode-sources.md) for source storage and migration status.

In Container settings, FRONT can render in three modes: no reference, reference without Phase Change, or reference with Phase Change. The shared Phase Change checkbox controls prompt intent; source phase/pipeline selectors are enabled while selected. Upload accepts file selection or clipboard paste. Phase Change without an available reference is rejected during prompt compilation and render preparation. The FRONT mode caption appears above render actions. Non-FRONT Head Image Construct and Head Image Edit default to the selected FRONT candidate as their reference; each view can save another selected view as its guide. A missing selected reference blocks prompt compilation and rendering. These settings affect new requests; prepared requests retain frozen inputs.

Shared slot recovery reattaches current candidates affected by the historical render-wait timeout to their original queued requests, or restores successful harvested images to review eligibility. It checks slot membership, request identity and receipts before changing state.

## Mode-aware batch rendering (2026-10-31)

The five local character pipelines expose Run front and Run available for the
selected Draft or Final mode. Bulk requests fill the saved Front/Other candidate
counts for currently eligible views; submitted and existing slots are preserved.
The slot collector owns background submission and recovery. Eligibility follows
the selected predecessor or configured Dressing inputs, independently of the
legacy Draft stage. Final renders require Final selections and upstream locks;
Draft rendering retains the existing reference preference and fallback. Existing
frozen requests and retries retain their saved inputs. Batch details and the
Batches page present mode-specific progress. Pause stops slot collection without
withdrawing submitted proxy requests; those requests can finish and their results
are collected after Resume. Restart recovery honors a paused collector and
resumes unpaused slot work even when the shared Draft batch status is Complete.
The collector releases the run-state lock between candidates and rechecks pause
and current pending membership before each transaction. Head-Image, Head-Image Edit,
Assembly and Dressing serialize a runner’s initial state transition with Stop.
Body-Reference also checks Stop before and after preflight; a queued Body batch can
be stopped before its runner begins. Runner entry and recovery also honor the
batch pause flag, so a delayed runner does not start after Stop. A lock timeout returns
HTTP 409 with retry guidance rather than a misleading missing-batch 404.

Mode progress treats an available nonempty image as completed render evidence,
even when a retained candidate still has an old RUNNING or FAILED label. Explicit
pending slot membership still counts as active work until the collector settles
it. This matches detail's image-first projection and prevents historical render
labels from keeping a fully selected Draft batch actionable after override imports.
Draft and Final pending work remain independent.

Draft and Final rankings are independent. Multi-candidate ranking compares an
available locked Draft for the same pipeline and view, including the costume for
Dressing. For Body-Reference Final rankings, Luna compares body matching and
ignores mannequin-head differences from the Draft. Luna weighs fidelity alongside
existing quality criteria. Changed comparison evidence is available for explicit review;
Re-evaluate refreshes the displayed mode on request. Single-candidate rankings remain
deterministic.

## Draft and Final rendering

Identity Keys offer one source per available pipeline, costume and view. Preview, Create and Update resolve the current locked Final for that category, falling back to Draft. Update re-crops from the current preferred lock, and the saved record identifies the mode actually used.

In the Identity Keys table, **Lock** publishes the saved crop to Image Inventory as `<Character> <Phase> IDKEY <Identity Key label>`. Updating a locked key refreshes the image, label and crop provenance on the same Inventory item. **Unlock** archives that item and keeps the saved crop available in the Identity Keys workflow. Unlock the key before deleting it. See [ADR 0048](../DECISIONS/0048-identity-key-publication.md).

`LocalAssetStoreService` has internal mode-specific selection records, private
Draft snapshots, and Final publication through the existing catalog transaction.
New locks also retain the selected candidate's prompt in the local record; Final
publication stores it with the Inventory image. Draft locks capture the currently
selected image bytes even if the candidate file was manually adjusted.
Legacy lock records are read as Draft. Individual selection/lock APIs accept an
explicit mode through `LocalModeSelectionService`; mode-scoped bulk lock APIs
and completion checks are also available internally. Assembly/Dressing source
resolution supports mode preference and fallback for Draft. New Final renders
require Final locks, including for an explicitly selected source batch. Assembly input preparation freezes the
requested mode's resolved references without replacing shared source snapshots;
Body and Head input preparation also project same-batch anchors by requested mode
and preserve saved reference order. Dressing input preparation resolves its
Assembly source per request and can reuse the saved prompt and bindings. The dashboard exposes separate mode controls and slots. See the
[completed plan](../../plans/completed/draft-final-rendering.md) for validation.

## Retired Overview autogenerate with edited heads (historical, 2026-10-27)

This automatic pipeline sequencing and batch reuse has been retired. The remaining
records below describe its former behavior for migration and rollback context only.

Dashboard Overview uses `LocalCharacterOverviewService` to sequence FRONT through
Body-Reference, Head-Image Edit, Character-Assembly and Costume-Dressing. New jobs
record `head_pipeline=head-image-edit`; recovered legacy jobs recheck the sequence
with that source. Owned legacy work uses the existing cancellation fences before
switching. Assembly creation explicitly freezes the edited head pipeline, and
batch reuse excludes Assembly/Dressing runs with legacy head ancestry. Only
Dressing is queried with a costume; Assembly is phase-scoped.

Existing locked Dressing images remain visible and complete. A legacy Assembly
FRONT lock is preserved and generation reports that it must be unlocked in
Character-Assembly before using edited heads. Head-Image Edit authoring validation
and human prompt/selection pauses remain in force; Autogenerate does not approve
these steps automatically. Disposable prepared checks verify actual batch creation,
edited Assembly source snapshots, compatible Dressing reuse, legacy lock protection
and new/recovered sequencing. They do not establish live model or render quality.

## Bulk pipeline locks (2026-10-27)

The Selected views area on Body-Reference, Head-Image, Head-Image Edit,
Character-Assembly and Costume-Dressing offers **Lock all** and **Unlock all**.
Lock all publishes the open batch's selected views, skipping selections already
locked by that batch. Its single confirmation includes required lineage changes
for Assembly/Dressing. Unlock all clears every recorded lock for the current
character/phase/pipeline (and current costume for Dressing), including other
batches and views outside the open batch. Published Inventory images are retained.
These affected workflows use the shared application confirmation dialog. Bulk
publication shows its readiness check and publishing state, and disables per-view
selection/publication controls until the aggregate action settles.

`LocalImagePipelineWorkflowService` owns bulk targeting, aggregate lock previews,
selection-change fencing and per-view outcomes through the existing adapter
guards. The action retains completed operations if another view fails, and the
dashboard reports the failed views and reasons. The shared controller prevents
duplicate bulk submissions and refreshes selections after completion. No data
format changes are required.

## Editing character and costume masters (2026-10-26)

Character setup exposes **Edit character template**; Costumes retains its **Open** action. Both open the complete canonical file in Template Editor, with view/search highlighting, a current-master diff and validation before saving. Every dimmed line remains editable. Saving a master leaves existing frozen asks and finished images intact; new asks use the saved master. Batch proposals and post-render adjustments retain their review boundaries. [Dashboard UI](DASHBOARD_UI.md#character-and-costume-template-editor-2026-10-26) owns the controls; [Prompts](PROMPTS.md#character-and-costume-source-editing-2026-10-26) owns validation.

## Costume-Dressing modes and adjustments (2026-10-26)

`CostumeRenderModeService` owns per-view settings, availability and ordered input preparation for slots, previews and Image Generator staging. FRONT retains its Assembly-based Doll-dressing behavior. Other views choose Doll-dressing (w/ Ref), Doll-dressing (no Ref), or Rotate. The first edits the matching Assembly with a selected same-batch costume view as design guidance; no Ref omits prior dressed views but retains authored resource images; Rotate edits the selected dressed view with Assembly second for target orientation, stance and framing. Sources are explicit: an unavailable chosen source blocks new work without nearest-view fallback. Rotation wording includes source, target, angular distance and direction.

Character Asset Container Candidate Boards expose the same three modes for non-FRONT views. Mode and reference view are saved per costume and target view, then captured with each prepared request. Existing container records default to Doll-dressing without reference. FRONT continues to use its matching published Assembly image. Head Image Construct and Head Image Edit share the saved cross-phase FRONT reference, while Apply phase change remains a per-request option. Head Edit selects its reference-capable FRONT render profile when the compiler attaches image inputs.

Costume-Dressing views run independently when their mode inputs exist; prompt improvement is optional. **Run ready views** queues remaining eligible candidates without Continue/predecessor stages. Per-view mode/reference settings persist; Retry uses frozen prompts, references, settings and seeds. Publication follows captured lineage rather than an unused FRONT prerequisite. Mode/reference changes do not rewrite existing candidates or locks.

Each view has a **Stage…** menu: **Stage in Image Generator** uses saved settings; **Stage no Costume ref** and **Stage Rotation** prepare alternatives without changing them. FRONT rejects the unsupported alternatives.

**Post Render Adjustments** opens `LocalCostumePostRenderService` through the existing post-render URL. `CostumeAdjustmentCriteriaService` saves stable criterion IDs/text and in_progress/accomplished status in the costume workspace, independently of batches and modes. Accomplished criteria remain visible and must be reopened and saved before text editing. Only unfinished criteria enter analysis.

Analysis proposes independently selectable costume prose-line changes with criterion links and view/mode scopes. Target and symmetric mirror are favored; other selected views, including a selected mirror, default unchecked. Intentional asymmetry suppresses mirror defaults. The operator adjusts scopes and accepts a cumulative source diff before four private target-view renders. Session seeds, render profile and ordered inputs are frozen; advisory AI assessment never changes human accomplishment statuses. Further rounds use the private trials and unfinished criteria. Earlier rounds remain inspectable. Explicit save promotes only the reviewed costume source to the governing master. New asks in any batch compile it; existing frozen asks and images remain unchanged. Partial progress may be saved while criteria remain unfinished.

Suggestions now address an eligible-line catalog by section, line number and original-line digest, so repeated prose can be edited independently. Models replace prose only; Zet preserves spatial annotations and generates view/mode tags. The review shows each source section and line. Protected scene-only/head-domain/resource content is excluded. Invalid findings receive specific diagnostics and at most one repair request; valid findings remain reviewable when repair fails, with omissions explained in the summary. Side-specific visibility and occlusion require asymmetric treatment even for fixed equipment. Existing saved suggestions remain readable. See [ADR 0035](../DECISIONS/0035-costume-suggestion-source-binding.md).

Character.md adjustments remain available for the other pipelines. Historical Costume-Dressing Character.md sessions are read-only. Prompt Generator Pilot pages/services/actions have been retired from Costume-Dressing and Head-Image Edit; stored images/session records and adopted-image publication provenance remain. Old continuations terminalize without dispatch. See [ADR 0033](../DECISIONS/0033-costume-post-render-adjustments.md), [Prompts](PROMPTS.md#costume-render-mode-conditioning-2026-10-26) and [Testing](../Testing.md).

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

FRONT renders, including image-to-image edits, compile the authored
`HEAD_EDIT_FRONT_DESCRIPTION` so explicit crop rules such as excluding shoulders
and clavicles reach the render request. Derived views omit that direct-FRONT
description and use their view-specific override with the selected FRONT source.

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

All five character pipeline pages display view sections and selected-view cards in
FRONT, FRONT_LEFT_3_4, FRONT_RIGHT_3_4, LEFT_PROFILE, RIGHT_PROFILE,
BACK_LEFT_3_4, BACK_RIGHT_3_4, BACK order. Individual view navigation and the
summary review panel use this order and skip absent views. Selected or locked
summary images open in the review panel and cycle through available summary images.
Batch actions open a dialog and close when an action is chosen; reports remain on
the summary page. Locked cards show a green “Locked” label, with green Lock and red
Unlock icons. This is presentation order; saved view lists and render scheduling
are unchanged. Each view has a Continue control below
its observations and Luna ranking status. It appears when the top Continue control
is available and enabled, shares its label and action, and updates during polling
without replacing unsaved observations.

Validation: the approved character-to-costume E2E scenario passed (1 test, 16.6s).
Disposable Chromium checks covered all four pipelines' view order, control placement,
readiness/polling/busy states, and preservation of unsaved observations. No maintained
tests were added; live inference was not exercised.

## Tsaeytte costume rear-view quality trial (2026-10-24)

The [active repair plan](../../plans/active/tsaeytte-costume-fix.md) and its private
evidence packet record matched-seed AI_Proxy renders against the accepted FRONT
hem and Joe-approved corrected visual targets. The Tsaeytte costume source now
states the rear hem relative to visible boot shafts and resolves view-specific
garment and jewelry visibility before prompt emission. The shared costume template,
compiler guidance, and rear-quarter costume orientation locks also use direct
view-specific wording. Existing selected and locked images remain unchanged;
the corrected visual targets are diagnostic inputs only. Image quality and
promotion decisions remain in the active plan.

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

The new character workflow uses persistent Asset Containers and manual per-view
Candidate Boards. It reuses the existing prompt compilers while keeping board,
selection and lock state independent of legacy runs. Traditional stage-driven
generation remains retired via [pipeline_retirement.py](../../zet/services/pipeline_retirement.py).

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
| Current costume Overview | [LocalCharacterOverviewService](../../zet/services/local_character_overview_service.py) reads `LocalAssetSourceService`; no generation, automatic pipeline selection, batch linking or recurring poller |

Inputs include character/phase, normalized requested views, costume qualifier when applicable, source batch/candidate selections, source templates, profile and seed controls. Runs retain specs, snapshots, candidate state, ranking jobs, human decisions, and selections. Outputs include candidate image artifacts and, after locking, approved library image/reference bindings.

1. Preview validates inputs and dependencies. Assembly uses body/head references; dressing uses an assembled character and costume source. Read the service's source resolution before assuming every input must already be locked: selected-batch workflows also exist.
2. Creation snapshots source material and records the run. Rendering queues work through the shared File Proxy; answer harvesting and view-specific evaluation progress persisted state.
3. Rendered candidates are available for Luna ranking and human review immediately. Front-anchor/order requirements differ by pipeline; use the owning service rather than a universal view loop.
4. Current human selection and image availability determine whether a finished image can be locked. Selection and locking are separate operations; publication captures the selected image and its prompt.
5. Lock publication preserves approved image bytes/checksum and a stable logical reference. Available published locks feed identity keys, turnarounds, costumes, phase comparison and scene references. Phase Comparison lists Head-Image-Edit when a locked edit exists in either selected phase and matches its views across those phases.

The shared review page skips unchanged human decisions. Review, selection, and rank
responses carry the same presented run fields as detail, allowing the page to merge
them directly without another detail request. Candidate images use the focused
resolver above; reference previews keep URLs stable for their saved content identity.

Reference thumbnails on all five character pipeline pages identify the owning
candidate, render mode and original ordered reference index. Assembly and Dressing
source previews resolve the displayed mode's current inputs through the same
resolver and Final lock checks used for new renders. Their source-image route
accepts an optional `render_mode`; without it, the route continues to serve the
saved run snapshot. Preview metadata includes the resolved mode, candidate ID and
checksum, and unavailable Final inputs are shown as errors rather than falling
back to Draft. Captions keep the source role separate from the `Mode/ID` label.
Candidate-specific references remain tied to their frozen render bytes. The
browser deduplicates references from occupied slots in the displayed mode.
Supplemental images retain their original input numbering, and polling refreshes
thumbnails when slot ownership changes. Legacy positional URLs default to Draft
and remain mode/slot scoped. This presentation lookup does not change frozen
render inputs.

### Costume-Dressing per-view readiness feedback (2026-10-28)

The batch view controls display Dressing's saved mode-specific `mode_reasons`,
prerequisite `stage_reason`, and availability of the selected reference beside
the affected view. A changed local mode/reference is preserved across polling and
marked as needing save before its readiness is presented. Saving refreshes that
view projection; submitted retries retain their frozen inputs. This is browser
presentation of the existing `CostumeRenderModeService` contract and does not
change render eligibility.

### Head Edit Refine prompt context (2026-10-28)

New Head-Image Edit refinement sessions retain the selected candidate's compiled
prompt, SHA-256, view/candidate identity and template revision as `review_context`.
An analysis copies that snapshot into its request record and includes the frozen
prompt in the advisory task. Older sessions without a retained prompt state that
authored criteria are unavailable instead of reading a potentially newer master.
This is prompt provenance, not proof that an advisory or resulting image is
artistically correct. See the [completed console remediation](../../plans/completed/console-error-remediation.md).

Detail presentation uses the loaded run's progression and reference recipes;
Body detail carries `character_progression` from `state.json` into that shared
projection when the field exists; legacy unstaged Body batches retain their
existing Start path. Slot prerequisites are computed once per view per response.
Compiler reference resolution still reads persisted recipes. Path conversion
reuses identical values within each document walk (see [data model](../DATA_MODEL.md)). A read-only profile
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

Costume Dressing also offers **Stage Rotation**. It uses the view's saved explicit
costume-reference view. Missing selections require an explicit source choice;
there is no nearest-view fallback.
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

Non-FRONT Costume Dressing views also offer **Stage no Costume ref** through the staging menu. It freshly
compiles the requested view using its matching Character-Assembly snapshot and
view-filtered template resources, without requiring or attaching a prior dressed
view. It follows the batch's accepted template revision and stages through the
same validated Image Generator handoff. This does not change batch prompts,
reference recipes, selections, candidates, or locks.

All four local character pages display eight stable slots per view. Initial FRONT/other-view counts are integers 1–8 (defaults 8/4); planned candidates awaiting an anchor are reserved, not empty. Add renders fills empty positions only. Generate/Regen use the current view prompt with fresh seeds; the view’s Recompile checkbox also applies to these actions and compiles current templates first. Already submitted asks retain their frozen inputs. Regen replaces an unselected candidate with a new identity; render Retry retains the failed render inputs/seed. Failed advisory review keeps its separate retry behavior.

All five character pipeline Regen view confirmations explain the selected mode, prompt recompilation choice, and applicable saved source settings. Selected and locked slots remain protected. Regen view stays available during active renders when the view has replaceable candidates. It writes a hidden cancellation marker into the exact running ask; the local image worker sends a prompt-ID-scoped interrupt through AI_Proxy and waits for terminal ComfyUI history before returning. The durable operation stays waiting until the collector settles the cancelled candidate, then reserves replacements with fresh IDs and seeds. Uncertain cancellation remains waiting and does not submit overlapping work. Other views are unaffected.

Costume-Dressing saved prompts include template revision and render mode provenance. Preparation reuses a saved prompt only when both match the accepted revision and current view mode; otherwise it recompiles before freezing new inputs. Retries still use their original frozen inputs.

[CharacterRenderSlots](../../zet/services/render_slot_service.py) owns atomic allocation and protection behind [LocalImagePipelineWorkflowService](../../zet/services/local_image_workflow_service.py). Detail includes `slots_by_view`, `slot_controls`, candidate slot numbers and action reasons. Render actions persist `slot_render_ids` before scheduling; an independent per-run collector submits/reconciles them without taking the batch runner lock. Other slots remain usable while renders run. Clear detaches running candidates so late answers cannot fill replacement slots. Startup recovery reattaches this collector. Candidate definitions added after creation live separately from mutable review state so rerun resets retain them. Clear detaches active membership and retains provenance/artifacts. Legacy galleries over eight remain visible; clear surplus unprotected candidates to reach capacity.

The batch summary and opened view poll every 30 seconds while work is active. View updates preserve unsaved observations, human decisions, focus and current candidate. Once a view has a complete or stale ranking, candidate cards and previous/next review navigation follow the saved Luna order, with unranked occupied candidates after ranked candidates in physical slot order; empty slots remain after candidates. Stale advice remains visible until Re-evaluate. This is presentation only: each card retains its physical slot label and its actions remain bound to that slot. Failed or never-started rankings leave cards and review navigation in physical slot order. Selected/locked outputs require explicit protection transitions; adding alternatives does not modify immutable library locks. Body ranking compares the valid, non-rejected candidate set. See [ADR 0007](../DECISIONS/0007-stable-render-slots.md) for the original slot design; the review contract is now ranking-only.

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

Re-evaluate is the single dashboard ranking action for all five pipelines. [LocalImagePipelineWorkflowService.reevaluate](../../zet/services/local_image_workflow_service.py) refreshes Luna ranking for existing harvested images, for one view or every rendered view in the batch. AI Observations run separately through their explicit action. Unrendered views are skipped. It preserves human decisions, notes and selections and does not invoke the render runner or retired defect gates. Existing active ranking work is reused; completed evaluation records receive a new identity and late updates remain fenced. The separate Rank images/Re-rank and Re-analyze buttons are removed; ranking and observations remain visible.

View-scoped Re-evaluate waits for renders in that view and render mode; independent
slot renders in other views or modes do not block it. The batch action still waits
for all pending slot renders. Stopped/paused batches and active legacy batch
execution remain blocked. `reevaluation_reason` owns these checks for both action
validation when the action is invoked. The dashboard leaves Re-evaluate available
and displays the current refusal reason after an attempt. A review with no saved ranking displays "Ranking not queued" with the
view action as recovery guidance; queued/running advice displays its current state.

Explicit Re-evaluate refreshes candidate file bookkeeping through
[reconcile_candidate_harvest](../../zet/services/image_harvest_service.py). Under
the run lock it checks every target file before refreshing missing or outdated
hashes. A current candidate's existing file is sufficient for local review; saved
hashes, receipts and historical requests do not gate availability. Recovered render
state enters human review without changing decisions, observations, selections or
image bytes. Cancellation, candidate/attempt replacement and evaluation ownership
still fence publication. Hashes continue to fence changed evaluation inputs and
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

**Improve governing templates** offers only the current phase's `Character.md` for Body Reference, Head Image and Head-Image Edit; Costume Dressing also offers the selected costume template. Head-Image Edit retains its `HEAD_EDIT_*` section restriction. The revision API exposes `editable_source_ids` independently of complete frozen compilation sources. Global sections and pipeline instruction templates are read-only context: requests, model corrections, decisions and acceptance cannot introduce edits to them, and promotion writes only changed governing templates. Historical project-source diffs remain readable, and continuing an old revision retains its frozen context.

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
opens the current canonical master in **Template Editor**, with shared validation,
view highlighting, diff and unsaved-change protection. **Save template** updates
that master; existing batch versions retain their frozen sources. **Restart from
current masters** incorporates saved master edits into a new review. **Use for new
renders** selects a saved READY version for the batch; **Update master templates**
retains the separate confirmed promotion. Historical project-template edits already
on disk can still be preserved through Restart's **Create template PR** recovery
action; this improvement panel no longer offers project-template updates. See
[update recovery](../GitHub_Task_Workflow.md#accepted-template-edits-and-update-recovery).
The status block before compiled prompts
reports pending corrections, selected batch sources, master
updates and drift from the captured baseline. **Start Front Renders** at the end
uses the same FRONT continuation and readiness checks as the top Continue control;
after FRONT opens, further generation uses the existing view controls.

[LocalCharacterProgressionService](../../zet/services/local_character_progression_service.py) owns explicit Continue boundaries: FRONT, both front quarters, both profiles, both rear quarters, then BACK. Body and Head pairs use the selected same-side predecessor; Costume-Dressing now uses independent mode inputs as described above. Body-Reference BACK uses selected FRONT; Head BACK defaults to the selected rear-left quarter and may use rear-right; Costume-Dressing reference choices are independent. Assembly runs its requested views without stage waits, using only matching body/head inputs. The Body rule also applies to future Generate/Regenerate actions in existing staged batches; saved renders and Retry retain their frozen inputs. Existing matching Body/Head/Assembly/costume inputs retain their roles and order. Body/Head previews include required ancestors for partial batches; Costume-Dressing preserves its requested views. Front-only batches remain front-only. New generation, supplemental slots, runner resume and automation respect the opened stages. Overview automation and Run All Remaining pause for human prompt/selection/Continue actions. Existing batches retain legacy sequencing until explicitly entering prompt improvement.

Prompt previews declare those future predecessor inputs through the same compiler contracts used for actual renders, even before any batch images exist. Shared reference descriptions keep preview and render prose identical for equivalent bindings; actual generation substitutes selected image paths and candidate provenance. Body task/image-input text is conditioned before its Qwen wrapper is added, and Head, Assembly and Dressing preserve their own ordered prerequisite roles. See [prompt preview compilation](PROMPTS.md#character-prompt-review-previews-2026-10-18) for the validation boundary and historical-review limitation.

Selected-image cards link to `/local-character-refinement`, a dedicated resumable page. [LocalCharacterRefinementService](../../zet/services/local_character_refinement_service.py) freezes its original image and chosen selected-view comparisons. All other available selected views are initially offered; the operator can include any subset or none. Shared true-up analysis distinguishes visible defects and continuity from occlusion and intentional asymmetry. Findings remain unchecked suggestions; custom-only edits need no successful report. Correction renders use exactly one edit-base image, selected findings and feedback; comparison images are analysis-only. Earlier accepted edits remain unless explicitly overridden. All work uses registered AI_Proxy continuations and existing Qwen image services.

**Use this image** explicitly places a new candidate identity in the original selection's occupied slot and selects it. Original/refinement images remain in session history; the adopted candidate has a separate gallery copy. Adoption checks the current selected identity and never changes published image bytes. Future stages use adopted selections. Changed predecessors produce advisory reference warnings without clearing selections or requiring re-review, regeneration, acknowledgment or new rankings. Missing images and invalid ownership remain errors. Generated images stay subject to the existing separate explicit publication action.

Routes extend `template-revisions` with decisions/acceptance, retain `activate`/`promote`, and add view `refinement` plus batch `refinements/{session_id}` detail, analysis, edit, retry, adoption and images. Business logic stays in services behind the shared workflow boundary. See [ADR 0025](../DECISIONS/0025-character-review-stages-and-refinement.md), [data ownership](../DATA_MODEL.md#character-template-revisions), and [Testing](../Testing.md). Prepared checks establish workflow behavior, not live visual quality.

## Style-unification batch review (2026-10-14)

Body and Head bootstrap from text; other views may use newly generated local front anchors. Dressing uses that local chain, with costume-only references remaining narrowly bound. Assembly uses matching body/head sources without a view anchor. Shared character instructions use the existing fine-grained head/body visibility tags to separate visible identity facts from rendering treatment. Prompt wording seeks dimensional anatomy and differentiated materials; it does not establish observed image quality.

Joe approved initial Tsaeytte batch review for FRONT (8), FRONT_LEFT_3_4 (4), and BACK_RIGHT_3_4 (4), through Canonical Adventure Gear, in existing galleries. Provisional selected-batch sources can advance this chain without replacing published locks. New images require explicit source-layer refresh before appearing in an already frozen Narrative assembly. Local implementation checks passed; live batch review remains pending rollout of the new prompt templates.

Local Head, Assembly and Dressing candidates track the staged ask's `target_output_file`, matching the background harvester's destination. A runner must not wait on a separate candidate filename after the generic harvester has consumed the answer. The live style-unification trial exposed this handoff race; existing successful outputs were recovered by matching ask receipts and seeds without rerendering.

Costume-Dressing batch lookup compares normalized workspace qualifiers, so a costume display name and its underscore slug resolve the same batch. Costume links also accept either identifier when selecting the existing gallery control. Other costume qualifiers remain isolated.


## Quick Character reconstruction and true-up (2026-10-15)

`QuickCharacterWizardService` offers source-style preservation or opt-in universe-style reconstruction. New sessions default to universe reconstruction in the UI, with preserve/change inputs, model choice, frozen style, editable brief and unseen-detail proposals/questions. Legacy sessions retain source-style semantics. The wizard remains independent of Body/Head/Assembly/Dressing prerequisites.

Shared reconstruction creates the edited target; front generation uses text only. Review shows original/candidate images and selectable corrections. True-up uses the styled candidate and retains intentional edits. Joe approves the front before three-quarter/profile generation from that anchor. Requested angle/visibility applies to head and torso together; hidden details are not automatically defects. Full body/portrait and left/right retain their existing output choices.

Intent/description changes invalidate approvals; a new front invalidates views using the prior anchor. Failed review retries separately; failed renders with saved inputs retry the submitted prompt/references/seed. Background submission is fenced against abandonment/revision/front changes. Transactional publication records target/style, actual correction lineage, comparison and seed, with source evidence distinct from approved outputs. Freydis's artistic acceptance is pending; disposable checks do not establish identity improvement. See [ADR 0013](../DECISIONS/0013-shared-reconstruction-target-and-true-up.md).

Operator trial update (2026-10-15): Joe accepted the Freydis improvement as sufficient to proceed. The wizard now emphasizes Generate, custom feedback, Try these changes and Use this image. Analysis, suggestions and earlier attempts are optional details; generating uses the current description without a separate approval checkbox. Failed automated review does not block choosing or refining a rendered image. Custom feedback composes directly without model compatibility approval; see PROMPTS.md and ADR 0013.


## Legacy Minor Characters alignment and true-ups (2026-10-15)

The [asset collection workflow](#minor-character-asset-collections) supersedes this historical description.

`MinorCharacterService` handles named universe-local workspaces, input analysis and publication. `MinorCharacterWorkflow` in `minor_character_workflow_service.py` owns current boards, stage prompts, rendering and review. New workspaces use the current workflow only; retired records are excluded without migration or file deletion. The Quick Character notes above describe preceding view/history rules, superseded by [ADR 0015](../DECISIONS/0015-minor-character-alignment.md).

Style alignment reconstructs identity, costume and details in universe style without enforcing an official view. Suggested changes/custom feedback refine it. Select a style image before generating any view. Every view independently uses this selected image with a short direction-only prompt, without the full character brief. Preview an aligned view and click **Continue to true-ups**, then **Try these changes** to refine it. Continue atomically selects the previewed rendered candidate and carries it in its existing slot, retaining matching checked suggestions and custom feedback. A separate Select click is optional; API callers omitting `candidate_id` continue with the existing selection. Inline guidance explains the transition and current image-task waits. Every rendered stage candidate can lock, including alignment images and carried selections. Draft locks and Style locks stay private to the workspace; Final Front, Three-quarter and Profile locks publish immutable Inventory images. Cards and review dialogs expose matching lock/unlock icon buttons. Unlock clears only the workspace lock, retaining the selection and any published Inventory images. Pending/failed review does not block selection or custom refinement.

Minor Characters offers five explicit views after Style alignment: Front, Front left 3/4, Front right 3/4, Left profile and Right profile. There is no side selector; each view can be generated and locked independently without completing the others. Existing current-workflow workspaces gain missing boards when read, preserving saved boards, selections, revisions and locks. Legacy `side` values remain stored for compatibility but do not restrict available views.

New Qwen Image 2.1 style prompts request one neutral character reference with explicit full-body or portrait framing. Direct style references keep their existing order and identify the first image as primary identity; multiple images use `<imageN>` roles. Reconstruction-based style generation still uses original pixels for analysis only. View prompts name the visible anatomical side instead of a screen-side facing direction, align head/torso/hips, and preserve identity and costume. True-ups edit the selected candidate as a canvas and preserve unaffected composition and design. Generic reference labels are not appended to Minor Character render prompts; each candidate retains the actual instruction for replay.

Each stage has one four-slot board. Refinement edits the previewed candidate and carries the selected image, if any, in its same slot as Prior selection; other slots clear. Repeated carry is allowed. Clear/Regen removes that slot's working selection. Additional renders replay the frozen recipe with fresh seeds. Current images retain their own prompt/kind. Revisions reject stale mutations and late results cannot restore discarded slots.
Restarting a view clears that view's working round and selection, returns it to alignment, and starts a fresh render from the selected style image. Restarting Style clears required changes, additional direction and analysis results, resets every stage's working board, and re-analyzes the retained original references. If any view work exists, Style restart requires confirmation that view images and revisions will be discarded. Immutable Inventory locks remain. The current board template candidate's final prompt is shown below custom feedback; it represents the latest round even when an older image is advanced.

Undo true-up restores one prior prompt/supporting state, including frozen findings, checked suggestions and feedback, with every slot and working selection cleared. There is no redo or image history. Regenerate from that recipe or choose different corrections using its private source binding. Private immutable inputs can remain for reproducibility, without discarded-image access. Inventory locks survive clear, refinement, undo and workspace deletion.

Paired review has independent navigation. Right arrows/keyboard keys move among rendered current slots. Small left arrows loop through original and occupied style slots during style work; during view work they loop through original, selected style and selected other views. Images deduplicate by checksum and unavailable entries are skipped. Comparison choice affects display only, independently of primary identity and reference order.

Main Minor Characters navigation saves edits and opens the complete list, including from an editor. Direct character links/history and Inventory handoffs remain. The All Minor Characters button and iteration history are removed. Board actions use `/api/minor-characters/{sid}/boards/{view}/{action}` and `/boards/{view}/slots/action`; mutations carry expected board revisions and services enforce eligibility. See [data model](../DATA_MODEL.md) and [prompts](PROMPTS.md). Disposable checks cover this workflow; S1-S3 are regression coverage, not artistic acceptance.

Minor Character detail recovery checks pending workflow ownership only when a
review is pending and shares that result across candidates. Public response
projection excludes private render payloads before copying while preserving
retry state, image URLs, and board ordering. The list projects names and locked
view metadata without serializing full candidate records.
Polling a queued/running render persists only a changed status or error; an
unchanged provider status does not rewrite the complete private session record.
View navigation reports its target while dirty edits save; failed saves remain
in the draft and keep their local error feedback.

Minor Characters status polling retries failed reads with a capped delay while work remains active. Mutations invalidate older in-flight polls; rejected mutations refresh the workspace while retaining the original error and never automatically repeat the write. Restart and generation controls also wait for pending slot actions. These browser recovery behaviors do not bypass server revision or active-work checks.

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

For multi-candidate non-front ranking, Luna receives the required selected FRONT as a separately labeled comparison. Ranking guidance prioritizes matching head-to-body proportions and identity, including relative head size, shoulder/neck scale, torso/limbs and silhouette, while accounting for perspective and visibility. Matching body/head inputs remain candidate-specific evidence. FRONT is never a render input or publication dependency and does not control target camera angle or hidden features. Rankings retain comparison provenance. Changing, clearing or rejecting FRONT supersedes pending evaluations without clearing saved ranking advice, downstream images or selections; late results cannot commit against a different FRONT. Newly queued images stale only their own view and mode ranking. The single-candidate shortcut remains deterministic. See [Testing](../Testing.md#assembly-front-ranking-validation-2026-10-20) for earlier validation and artistic limits.

## LLM purpose separation (2026-10-22)

Character descriptions and costume template wording use Qwen fragment guidance; prompt review and existing correction suggestions use review guidance. Source observations, evidence validation, candidate ranking and Body compliance remain separate skill-free roles. Shared reconstruction retains character-description/review role ownership. No LLM pass is added to deterministic compilation, alignment or correction composition. See [LLM roles](LLM_ROLES.md) for defaults, overrides and frozen guidance.

## Post-render Character.md improvement (2026-10-23)

AI Observations no longer start after ranking or Re-evaluate. Each view's Observations section offers an explicit run action; human notes are saved separately. Each rendered view has a **Post Render Adjustments** button (Costume-Dressing uses the costume workflow above; the other four pipelines use Character.md) opening `/local-character-prompt-improvement`. A view-scoped private session freezes one review image and its submitted prompt plus the batch source text; it snapshots that view's observations for each proposal. The operator can switch the representative within the view before analysis. Review suggestions are individually selectable and confined to `Character.md` but may change any valid location in that file; other active batch source overlays remain in place. The page uses the same side-by-side master/proposed source diff as prompt improvement.

The selected edits compile all eight text previews and two private renders of the chosen view with current ordered inputs, even if a suggestion cites another affected view. Trial images do not enter slots, selections, rankings, or Inventory. Another observation round can build on the trial. Cancel discards the private trial and leaves only explicitly saved observations. Keep requires completed trials and unchanged source/batch baselines, then writes `Character.md`, activates a batch version, and recompiles available renderable prompts. Unopened views compile from that version when generated. Assembly gains this post-render version path without changing its initial Run front gate. Frozen asks, Retry and locks remain unchanged.

The persistent review and promotion boundary is recorded in [ADR 0030](../DECISIONS/0030-private-post-render-character-prompt-trials.md).


## Long-hair framing and Assembly handoff (2026-10-27)

Head references show complete hair where practical, with body context for the
visible endpoint. Assembly may complete lower hair only to a body landmark
explicitly authored in `CHARACTER_ASSEMBLY_CHARACTER_REQUIREMENTS`. This includes
correcting a prematurely shortened source hem, while retaining hairstyle identity,
natural occlusion and underlying body/clothing design. See
[Prompts](PROMPTS.md#long-hair-across-head-and-assembly-2026-10-27) and
[ADR 0036](../DECISIONS/0036-long-hair-head-and-assembly.md).

For an existing Head batch with an accepted source version, a master edit alone
does not replace that version: make and accept a manual child Character.md revision
containing the revised hair wording in that head family's allowed sections
(`HEAD_EDIT_*` for Head-Image Edit), then Recompile before Generate/Regenerate.
Use the existing post-render Character.md revision workflow for Assembly batches
with an accepted post-render version; do not bypass acceptance or rewrite it on
disk. Batches without an accepted version compile from the current master.
Fresh Assembly requests refresh version-1 prompt caches automatically, but an old
accepted Character.md can still contain contradictory neck-only wording.

Assembly snapshots its chosen body/head inputs. Selecting or regenerating an
improved Head image does not refresh an existing Assembly batch: create a new
Assembly batch from the desired selected head family/batch to use those new bytes.
Retry replays its original frozen request. Existing selections, publications and
locked images are unchanged by master/template edits.

Disposable isolated compilation/preparation and the approved fast E2E suite check
software behavior. No live images were generated for this change; the back-left
hair endpoint still requires human visual acceptance after future rendering.


## Environmental universe style (2026-10-30)

Body Reference, Head Image, Head Image Edit and Costume Dressing choose universe style when creating a batch. The batch snapshot persists across subsequent view compilation. Overview automatic creation defaults canonical and rejects reuse of batches with a different variant or frozen style hash. Minor Characters stores universe_style_variant independently of source-style preservation, and includes it in analysis invalidation.

Character-to-Image-Generator staging uses the destination board's Draft or Final
mode when resolving selected and locked references, with the other mode as a
fallback. It stages the configured target and the pipeline's default aspect ratio
(square for Head, 2:3 for the other character pipelines); the generator can adjust
these before submission. This includes Dressing's no-reference and rotation
handoffs. Existing submitted requests retain their frozen inputs.

The character dashboard's render-quality control switches the Draft and Final
slot boards and their selections. The aspect-ratio control previews configured
dimensions, and individual slot generation can reuse a same-view seed from the
other mode. Locks and bulk locks operate on the displayed mode; Draft locks are
private and Final locks publish. View and batch regeneration act on occupied
slots in the displayed mode and report protected slots; failed-render Retry
reuses its frozen inputs. New batch candidates begin as Draft at their pipeline's
default ratio. Source-batch choices include Draft and Final selections and prefer
the requested mode with fallback. The [completed implementation plan](../../plans/completed/draft-final-rendering.md) records validation.

Minor Characters also stores independent Draft and Final boards, selections and
locks. New Draft locks and Style locks use private snapshots; Final view locks
publish to Inventory. An alignment uses the selected style in its own mode with
fallback to the other mode. Failed slot Retry keeps its frozen render payload,
seed and sizing. Legacy workspace boards and locks remain Draft.

Refinement and private post-render trial sessions retain their Draft or Final
mode. Refinement adopts into that mode’s selected slot, while comparison and
trial references prefer that mode with fallback. New edits and trials freeze
their configured sizing; retries retain the submitted sizing and inputs. Minor
Character render references are also copied into private candidate inputs and
checked against their saved hashes before reuse.

Minor Character Draft cleanup can target one view or the whole workspace. It
clears Draft selections and private locks, fences owned image requests, and
removes their output bytes after confirmation. A pending Draft render cannot be
created later by an already-running analysis. Final boards and Inventory copies
remain available.

Character pipeline batch and view controls also offer confirmed Draft cleanup.
The operation fences matching renders, removes batch-owned Draft output images
and private lock snapshots, and clears the batch's Draft selections, slots and
review state. Final work, downstream results and Inventory copies are retained.

Overview autogeneration prefers an available Final FRONT selection or lock,
falling back to Draft. Its Draft locks use private snapshots rather than
publishing through the legacy Inventory path.

Legacy dashboard lock requests without an explicit mode also lock Drafts
privately. Shared locked-source discovery prefers Final per pipeline, costume
and view; an existing explicit Draft source key still resolves to that Draft.
Head Image Edit phase-source selection follows the same preference.

Matching resumable Minor Character preparation and review continuations are
cancelled with the Drafts; attributed queued AI requests are fenced too. Older
in-flight requests without workflow attribution cannot be identified individually.

Candidate review can display the current view’s locked Draft snapshot, including locks from another batch. This is display-only and does not change selections, rankings, or render inputs. Minor Character reviews similarly use their workspace’s matching Draft lock.

## Render slot waiting and late images (2026-10-31)

`CharacterRenderSlots.collect` allows one hour from submission before its fallback
timeout, including queue time. Known unfinished requests remain pending through
the shared AI job service even beyond that grace period; provider errors and
missing asks still surface normally. This applies to both Draft and Final slots.
The shared detail projection clears render errors when a nonempty image is
available, including images harvested after an earlier timeout. Explicit harvest
reconciliation also clears the persisted render error, even when the saved hash
and status already match. Review errors remain independent.

Disposable isolated checks covered the grace period, pending-job guard, timeout,
provider failure, late completion, missing/empty images and persisted recovery.
All four approved fast E2E scenarios passed (47.2s). No live renders or production
state edits were performed; these results do not establish hosted deployment.

Background collection uses the shared AI job coordinator for Character Asset Container renders. It applies results through the same locked, revision-checked board reconciliation as foreground progress refresh. A pending application marker supports recovery after answer harvesting and protects the receipt until the board commit settles.

## Minor Character asset collections

Each named collection has Style Alignment and five view assets. Each asset
uses the shared eight-slot mixed-quality Candidate Board. The overview and
container show locked images and link to all six boards. Container Settings
edits the shared sections of MinorCharacter.md and selects the original
Inventory image. Each board owns the interview, prompt, aspect ratio and render
controls. Interviews start fresh from saved inputs, and accepted proposals save
to the relevant section of the same template.

Choose an Inventory image in Container Settings and click **Run Intake** under
**Template Improvement** to
fill blank Appearance, Framing, and Directions fields with observations from
that image. Intake saves supported observations to the template and leaves
existing entries and intentional changes in place. It can run before a
canonical universe style is set. Review or edit the saved fields, then use
**Write Prompt** in Style Alignment. Config's **Minor Character intake** role
controls the vision model used for this request.

Style Alignment analyzes the original image, optionally with a completed
candidate as feedback evidence. Its interview edits only the optional
`STYLE_ALIGNMENT_CHANGES` section, shown as Source-to-reference changes in
Asset settings. Put intentional changes from the source in this section.
Shared Appearance, Framing and Directions remain in Container settings.
The Style prompt uses both the shared description and the dedicated changes.
Downstream views compile their own inputs and omit the change section. Write Prompt describes the target character
and composes the universe canonical style into the displayed render prompt.
New Style renders use text-to-image. For each view, the shared compiler filters
template text for its orientation before prompt writing. A view interview
updates its refinement section. New view renders use the current locked Style
Alignment image. Captured requests remain available for retry.

See [ADR 0050](../DECISIONS/0050-minor-character-asset-collections.md) for the
name-and-source-only offline bootstrap.
