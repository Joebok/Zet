# Narrative dashboard scenes

Narrative provides prose-oriented authoring and generation independent of Scene Builder's templates, schemas, and pipeline records. It shares universe configuration, the image library, and infrastructure, not the structured-scene authoring lifecycle. [ADR 0002](../DECISIONS/0002-independent-narrative-workflow.md) records this boundary.

## Implementation and interfaces

| Module | Responsibility |
| --- | --- |
| [models/narrative.py](../../zet/models/narrative.py), [NarrativeRepository](../../zet/repositories/narrative_repository.py) | Story, scene, element, target and candidate defaults; atomic JSON persistence, constrained IDs and repository workflow lock |
| [NarrativeSceneService](../../zet/services/narrative_scene_service.py) | Authoring CRUD, scene elements, targets, references, image selection/locking and protected deletion; `ZetApp.narrative_scene_service` |
| [NarrativeGenerationService](../../zet/services/narrative_generation_service.py) | `start`/detail polling, persisted interview/synthesis/render jobs, candidate slots, retry/replay and domain result application |
| [narrative_prompt_service.py](../../zet/services/narrative_prompt_service.py) | `llm_request`, `assemble_prompt`, structured request schemas and deterministic prompt/reference packaging |
| [narrative_interview_service.py](../../zet/services/narrative_interview_service.py) | Field purposes/authority, old-reply normalization and validated whole-field review proposals |
| [NarrativeProxyService](../../zet/services/narrative_proxy_service.py) | Common proxy dispatch/collection for every text/image provider; [narrative_qwen_workflow.py](../../zet/services/narrative_qwen_workflow.py) supplies image workflows |
| [NarrativeReferenceService](../../zet/services/narrative_reference_service.py) | Pinned backdrop inputs, local reuse/crop actions and independent imported subscenes |
| [NarrativeAssemblyService](../../zet/services/narrative_assembly_service.py) | Source/layer binding, editable extraction/cutouts, deterministic composition and frozen assembly snapshots |
| [narrative_router.py](../../zet/web/narrative_router.py), [narrative.html](../../zet/web/templates/narrative.html), [narrative.js](../../zet/web/static/narrative.js) | HTTP/browser presentation and calls into Narrative services; context capture integrates with shared [task_capture.js](../../zet/web/static/task_capture.js) |

## Shell route compatibility (2026-10-28)

The shared shell's story list projects native Narrative IDs as `slug`. When opening
Narrative from a `story_slug` route, `zet.js` recognizes those IDs directly and
translates them to `story`/`scene`. Only actual legacy locations need migration
lookup. `/api/narrative/legacy-location?optional=true` returns null for an absent
mapping; the shell displays a migration notice and opens Narrative without the
stale legacy parameters. Default/required lookups still return 404. Other storage
and migration errors propagate. No persisted format changes.

Disposable isolated browser/API checks passed native links, missing optional
mappings and strict lookup failures; the four approved fast scenarios passed.

## Data and job lifecycle

Responsive cards and image review follow [Dashboard UI](DASHBOARD_UI.md). Existing
targets with images prioritize viewing on compact screens, with direction and
generation inputs available in disclosures. These visual conventions preserve
Narrative's independent records and selection/lock lifecycle. Cards show render
status once and use shared image-action icons. Prompt/source provenance, copying,
assembly layers and raw-composite links live in the review disclosure, collapsed
on opening/changing candidates. Pending/failed occupied slots can open details;
selection and locking still require an image.

Narrative JSON persistence uses the shared portable library-path codec for explicitly typed library-owned references, including frozen snapshots. Target-relative filenames and immutable job/transport artifacts keep their existing semantics. The offline updater excludes migration journals and historical free text; see [DATA_MODEL](../DATA_MODEL.md) and [ADR 0011](../DECISIONS/0011-portable-library-references.md).

Inputs include scene intent/visual settings, named elements/library asset IDs, target narrative/staging/physical context/framing, model selection, candidate slot controls, and assembly layers. Targets include backdrop/subscene/assembly behavior. Outputs are authored prose, generated prompts with provenance, durable job/candidate records, image files, selections and locked images. Storage is under universe `NarrativeStories/`; [DATA_MODEL](../DATA_MODEL.md) owns identifiers/formats.

The element library-image picker seeds its editable search from the current Name field, including unsaved edits. `NarrativeSceneService.library_options` queries at most ten approved catalog images before hydration and omits unavailable files; searches may return fewer than ten images.

1. Author creates a story, scenes, elements, and targets with stable IDs. Target visual settings combine scene defaults and target overrides.
2. `start` chooses interview/synthesis/generate/render or a supported replay action. All text/image work uses File Proxy; its trusted registration selects Codex, Ollama or ComfyUI execution. Jobs persist model/provider provenance and a baseline for result application.
3. Submission snapshots ordered reference bytes. Assembly submission binds server-owned source layers and freezes an assembly snapshot; replay uses saved job inputs. Backdrop crop/unchanged operations use local actions instead of requesting generation.
   Qwen Image 2.1 render references are prepared in the local render-job workspace under the configured per-image and aggregate pixel budgets. Prepared source hashes/order and effective machine settings accompany the saved graph; pending ComfyUI submissions resume that graph and its snapshots after configuration changes.
4. Proxy/Codex results advance jobs and candidate slots. Interviews store pending proposals without changing authored inputs; the user reviews and applies selected replacements. The shared AI coordinator collects in the background, including when this page/universe is not open. Published attempts survive dashboard restart; ambiguous execution is never silently replayed. Matching legacy Codex attempt outputs can be adopted without execution.
5. The user selects/locks outputs. Protected deletion and pinned sources prevent accidental removal/mutation of images used by the workflow.

## Interview review and field guidance

Appearance notes hold identity, anatomy, clothing, intrinsic size and equipment changes shared
across targets using an element. The moment holds the visible event, individual expression,
pose, gaze, gestures, interaction, arrangement and relative heights. Physical context describes
ground, contact, support and conditions affecting the action; framing describes cropping and
required visibility. These are prose guidance, not restrictions on editing.

The interview receives assigned elements, shared visual values, local overrides and their
effective values/sources. It proposes moment, assigned-element appearance and visual-context
replacements, with conflict findings and up to two questions. A local override intentionally
replaces shared context; that difference alone is not a conflict. Text requests receive
reference metadata, not images, and cannot verify visual anatomy, pose or height.

The Old/New review defaults moment/appearance rows to Accept and visual rows to Override.
Buttons select actions; Apply commits complete field replacements. Bulk Accept All (override),
Accept All (shared) and Reject All affect only rows without an explicit user choice. Shared
writes the scene value and clears the corresponding override on this target. Appearance
acceptance affects every target using that element. No extra confirmation or generation gate
is added. Closed pending reviews can be reopened; selections survive polling and close/reopen
within the mount. Reload keeps the pending review but resets uncommitted choices to defaults.

`POST /api/narrative/stories/{story}/scenes/{scene}/targets/{target}/interview-review`
delegates to `NarrativeSceneService.apply_interview`, taking `job_id` and proposal-ID/action
`choices`. It validates choices before writing selected current fields under the repository
lock. Repeating a successfully applied request is harmless. Individual files use atomic writes;
multi-file updates are not a transaction. A failed write leaves the persisted review pending
for retry. Old completed interviews remain historical; newly received old-format replies become
review proposals. Superseded attempts cannot expose an applicable review.

Local overrides include Save inputs for all dirty target fields and a collapsed active-field
summary. Shared/effective visual values update after saves, polling and review application.

Completed image tiles and image reviews show a muted Different prompt label when their recorded
prompt differs from the current editor text, including unsaved edits. Only line endings are
normalized. Reverting text removes the label. Missing prompts show Prompt not recorded;
local crop/reuse is labeled separately. This is text comparison, not a reference, input or
render-quality check. See [ADR 0009](../DECISIONS/0009-narrative-interview-review.md).

## Assembly and reference boundaries

**Use current selection** saves pending assembly edits, fetches the source target's
selected candidate, then updates the current layer object so an intervening poll
or save cannot discard the selection. It clears extraction corrections while
retaining placement; the saved layer remains pinned until explicitly changed.

Layer controls/identifiers come from the client, but filenames, metadata, and source-byte binding are server owned. Assembly modes influence prompt provenance; a prompt generated for one mode cannot silently render another. New final assemblies and older records without a saved mode default to `harmonize_composite` (Harmonize placed composite); other target kinds default to `finish_composite`. Extraction uses OpenCV/NumPy/Pillow and its own lock. Imported subscenes/backdrops retain independent snapshots; they are not live links to another target's changing candidate.

`harmonize_composite` (Harmonize placed composite) freezes the same placed image,
including extraction corrections, tolerance, scale, fit and depth. Qwen receives
only that composite; the entire dimension-validated output is retained, allowing
subject relighting, color changes, edge repair, shadows and foreground integration.
The frozen composite remains available for candidate comparison and retry; this
mode does not save finishing masks. Layout preservation is prompt guidance and can
drift. `finish_composite` instead restores original subject pixels and retains
generated changes only through its exterior edit mask. `assemble_references`
supplies original sources with text placement; extraction corrections are not sent.

## Subscene transparency

Subscenes show **Use transparent background**, checked by default, after Physical
Context. The boolean `use_transparent_background` persists with target inputs and
copies with imported subscenes. Missing fields on existing targets read as checked;
existing prompts/images and historical job snapshots are not rewritten.

Checked transparency intentionally overrides visible scenery in shared/local
Setting and other prose for interview and Write Prompt, without deleting those
inputs. Camera, perspective, subject lighting, physical relationships, required
props and supports remain relevant. The effective-context display explains the
suppression. Interviews receive the policy and must not erase shared Setting just
to obtain transparency or propose changing the checkbox. Write Prompt suppresses
visible scenery in its effective setting and appends explicit RGBA/zero-alpha
instructions, excluding painted checkerboards and opaque mattes/floors. These are
model instructions, not validation or a guarantee of actual transparent pixels.

Unchecked follows authored visual context, with no injected neutral-background
requirement. Changing the checkbox requires Write Prompt to update existing text;
Render continues sending the editable prompt exactly as entered. New text jobs
freeze the preference. A different preference, or an old job lacking the flag,
prevents automatic prompt replacement/current interview review on completion.
Existing completed history remains readable. See [ADR 0010](../DECISIONS/0010-narrative-harmonization-and-transparency.md).

The scene overview and scene-page target selector keep final assembly targets after backdrops and subscenes, even when a new target is added later. This is presentation ordering; stored target order remains unchanged.

Qwen reference sizing and prefix-cache placement are configured under
`[ComfyUI.QwenImage21]` in `config.toml`; see
[PROMPTS](PROMPTS.md) for limits and image handling. Pixel budgets are tunable
workload settings, not a prediction of VRAM fit or render duration. The metadata
records configured cache device/precision separately from ComfyUI's runtime status.

## Failure modes and extensions

Unknown record IDs, missing selected source files, stale jobs/results, occupied slots, protected images, unavailable proxy-side Codex executable, external proxy errors, invalid structured text results, and assembly-mode/provenance mismatch are relevant failure cases. Inspect persisted target job errors and text-attempt artifacts before retrying. An HTTP read can reconcile job state, so it is not necessarily a pure file read.

Add Narrative fields to model defaults, author patch/validation lists, prompt/job snapshots, result application and UI together. Keep queue protocol changes in shared infrastructure and Narrative-specific job semantics here. The retired Scene Builder staging facade has been removed; do not recreate it as a shortcut.

## Tests and design notes

[fast.spec.mjs](../../tests/e2e/fast.spec.mjs) S1 saves/reloads story, scene and element authoring; S3 runs interview proposal/review/Apply and synthesis, prepared backdrop/subscene renders, a failure/retry, source selection/locking and final assembly through persisted publication/display. The [live check](../../tests/e2e/live.spec.mjs) uses prepared prerequisites then real final-assembly synthesis/rendering. These scenarios do not exhaustively verify frozen-input rejection, protected deletion, source import or Codex restart branches. See [Testing](../Testing.md) for live opt-in and coverage approval and [DEVELOPMENT](../DEVELOPMENT.md) for results.

[Narrative approach](../../Docs-Joe/Narrative_Scene_Approach.md), [phase 1](../../Docs-Joe/Narrative_Scenes_Phase_1.md), [phase 2](../../Docs-Joe/Narrative_Scenes_Phase_2.md), and [references](../../Docs-Joe/Narrative_Scene_References.md) preserve intent and specifications; check code before treating recommendations as implemented behavior.

## Dashboard, migration and Candidates (2026-10-12)

The dashboard Stories workspace mounts the existing editor through
`mountNarrative` in [narrative.js](../../zet/web/static/narrative.js), with explicit
unmount/save, listener cancellation, polling cleanup and task-provider restoration.
Canonical URLs use `/?page=narrative&workspace=story` plus universe/story/scene/target
IDs. `/narrative` redirects for existing links and approved scenarios. Story navigation
contains Stories, Candidates and Zines; migration provenance maps old story/scene links.

Scene defaults include service-owned `legacy_image`, `source_provenance`, and
`migration`; elements optionally use `reference_key` instead of `asset_id`. Scene
and target serializers resolve current logical references; stale/archived/missing
bindings show issues and cannot supply render references. Submitted jobs still freeze
resolved IDs, ordered files and bytes. [NarrativeSceneService](../../zet/services/narrative_scene_service.py)
updates only the changed consumer's recorded entity usages on reference changes. Legacy image assets survive scene deletion.

[NarrativeMigrationService](../../zet/services/narrative_migration_service.py) and its
[CLI](../../zet/scripts/migrate_narrative_scenes.py) consume the reviewed
[manifest](../../Config/Legacy_Narrative_Migration.json). Preparation/dry-run do not
write creative data. Apply/resume are offline, back up the destination, journal stable
IDs and preserve existing/edited destinations. Verification checks counts, order,
required targets, membership and image checksums. The image reviews seed prose staging,
not measured geometry or a functioning pipeline. Targets start without jobs, prompts,
selections, candidates or assembly layers. Full legacy scene documents/Markdown and
story settings remain in provenance. See the [archive guide](../../Archive/scene-builder/README.md)
for backup and rollback boundaries.

[SceneCandidateSourceService](../../zet/services/scene_candidate_source_service.py)
parses existing read-only Adventure Log Markdown. [NarrativeCandidateImportService](../../zet/services/narrative_candidate_import_service.py)
creates resumable stubs with provenance, exact visible participants, backdrop/subject/
assembly inputs and unresolved-reference notes. `/api/narrative/candidate-sources`
and `/api/narrative/candidates` own listing/import/passed/review actions. Default story
slugs resolve through migrated provenance. Passed/import reservations are universe-local.
Repeated imports open existing destinations; all three celestial-rift associations
remain distinct. Source review compares recorded/incoming briefs; acknowledgement
changes only provenance, preserving authored fields and target images.

Selected final assemblies feed discovery, story summaries and zines through
`finished_sources`; `NARRATIVE` image tags bind an explicit candidate. Legacy images
are separately labeled and never count as newly completed assemblies.

## Universe-style adoption (2026-10-14)

Scene `use_universe_style` defaults true on creation; records missing the flag normalize false to preserve their saved style. Legacy scene migration also explicitly retains its authored style. The scene editor retains saved custom style and displays the universe alternative. When enabled, current universe style supplies inherited style; a nonblank target override replaces it. Target detail reports the effective source and universe style snapshot. Applying an interview style proposal to Shared explicitly chooses that custom scene style and disables universe inheritance.

Synthesis, including composite harmonization, receives the effective style. Job detail/provenance freeze that source and text; retries reuse frozen inputs. A Render job attributes style to its saved prompt provenance, rather than claiming to adopt newer settings. Write Prompt is required to adopt subsequent style changes. Rendering does not silently rewrite existing prompts. See [ADR 0012](../DECISIONS/0012-universe-style-and-reconstruction.md). Existing S1/S3 and disposable compatibility/override checks passed; live artistic fidelity is unverified.

Shared transport, receipts, foreground/background collection and model selection are owned by [Shared AI jobs](AI_JOBS.md).

## Interrupted submission recovery (2026-10-17)
Text request/schema intent is saved before publication. SUBMITTING jobs reattach to existing transport or resume publication using saved request/candidate identity; replacement execution stays behind the common logical AI job interface. Storage exceptions suspend work instead of becoming permanent provider/content errors. See [storage recovery](STORAGE_RECOVERY.md).

NarrativeRepository routes writes through incremental usage tracking, including
reference-bearing job snapshots; unchanged reference sets avoid derived writes.
Pending observations retry without invalidating committed authoring. Image
availability follows [ADR 0023](../DECISIONS/0023-streamlined-image-integrity.md);
required missing references fail only their dependent operation. Confirmed deletion
may leave authored references unresolved; it does not silently remove them.

## Prompt-writing role (2026-10-22)

Interview and prompt writing are separate model roles, preserving explicit per-target choices. Synthesis receives repo-managed Qwen guidance selected from planned downstream generation/edit/composite intent while keeping the existing scene/rendering response fields and deterministic reference binding. [LLM roles](LLM_ROLES.md) owns model inheritance, skill adapters and frozen request provenance.

## Manual scene text (2026-10-29)

Final assemblies have Scene text authoring and a full-viewport placement editor. Add/reorder entries, use restricted bold/italic markup, choose no tail or a straight tail, draw boxes and move/resize them. Tail tips stay in image space while the attachment can move around the bubble. Text uses a fixed effective size; overflow prevents confirmation. Full screen is optional; the viewport editor remains available without browser fullscreen.

In an empty raw placement editor, typing text, choosing a tail or dragging on the image creates the first entry automatically. Add scene text creates subsequent entries. Text typed before placement is saved with the entry even if no box has been drawn yet.

`NarrativeSceneTextService` owns revision-fenced drafts, candidate placements, preview and confirmation. `scene_text_render_service` uses Pillow for both previews and final PNGs. `scene_text_style_service` resolves universe settings and field-level story overrides; scenes/targets cannot override appearance. Installed approved font families must have all four faces. Universe Settings and the story editor expose style controls and previews.

Raw placement seeds freeze with assembly snapshots but never enter AI image inputs. Candidate placement changes are independent. Confirm and select validates current text/style/source identity and saves a new finished PNG before atomically changing the target's pointer/selection. Original artwork remains unchanged. Locked candidates require unlock to replace lettering; direct select/lock cannot bypass confirmation. Draft edits retain the preceding finished output and show pending changes.

The target `/scene-text` GET and `/scene-text/{save,preview,confirm}` POST actions take an optional candidate ID. `/candidates/{candidate}/image` retains artwork; `/finished-image` resolves the latest confirmed PNG, falling back to artwork for records with no confirmed revision. Story thumbnails, discovery, NARRATIVE references and zines use finished images. A missing confirmed PNG is an explicit error. Candidate deletion removes its owned lettering directory under the existing protection check.

Disposable checks cover persistence, stale confirmation, formatting/shapes/overflow, original-byte preservation, a Chromium placement/confirmation/lock journey, keyboard resizing, viewport fitting and fullscreen exit. Physical touch/pen devices and browser-fullscreen denial remain unverified. See ADR 0037.

### Finished scene-text editing
The primary Scene text action edits the selected rendered candidate; raw-composite drafts remain separate. Candidate drafts accept optional shared entries plus candidate placements in one revision-fenced save. Save and close (including Escape) saves the draft and confirms a new finished PNG; validation failures keep the editor open and retain the preceding finished output. Save draft does not publish lettering. Unlock permits re-editing over the original artwork, never over a lettered PNG. Review has a clean-image toggle; finished revision URLs refresh thumbnails.

## Backdrop linking and exact crops (2026-10-29)

Backdrops pin source bytes separately from `backdrop_link_mode`: `unmodified` reuses bytes locally, `reference` supplies the pinned full image or crop, and `regenerate` excludes source images and adaptation instructions. Copy-current/generation actions explicitly replace inputs and install local visual overrides; subsequent authoring uses normal scene/interview behavior. New backdrop links do not automatically seed inputs. Imported subscenes retain their independent-copy behavior.

Reference crops use integer source-pixel x/y/width/height after EXIF orientation. Preview, local reuse and generated attachments share the same lossless crop. Output dimensions never resize the rectangle. Changing source dimensions resets the crop to the full source; same-sized refreshes retain it. Apply operation writes a fresh prompt and generates one candidate. Generated edits can reinterpret pixels. Expand toward appears only for Expand.

Jobs freeze prepared crop bytes in the existing ordered reference snapshots. Retries retain those bytes. Mode/crop changes fence current prompt/interview application; historical candidates remain unchanged.
