# UI consolidation design

This is the proposed implementation design for the [brief](../ui-consolidation-and-workflow-alignment.md), informed by the [review](review.md). The user has chosen full tablet production, one workspace with expandable preparation, and explicit prompt updates before rendering. The remaining details are recommendations for approval with the whole plan.

## One production workspace

Use the existing shared Candidate Board as the results and review component. Place a small reusable workspace shell around it. The shell arranges domain-owned preparation sections, summarizes readiness, and exposes the current context; it does not compile templates, find files, or dispatch queue work.

| Area, in reading order | Contents and behavior |
| --- | --- |
| Context | Universe, subject or story/scene, pipeline/target/view, selected/locked summary, and direct scope navigation. Full names remain available when the compact header cannot show them. |
| Preparation | Expandable Inputs, References, Interview and suggested changes, and optional Placement sections. Each header summarizes incomplete/unsaved/pending state. Open missing required inputs for a new asset; retain the operator's open/closed choices thereafter. |
| Next render | Input readiness, prompt state and explicit Write prompt / Update prompt where applicable. The prompt editor/preview and advanced settings expand here. Keep the effective ratio, Draft/Final shortcuts and a compact activity summary reachable near the board. |
| Candidates | Stable slot order, consistent cards and actions, useful queued/running/failed placeholders. Keep review, select, lock and regeneration available as allowed by the workflow. |
| Image review | Full-screen overlay with candidate identity, previous/next, comparison, zoom and decisions. Advice and provenance scroll separately from essential actions and their feedback. |

At desktop width, an open preparation panel may use a bounded side area if that leaves useful image space. At landscape tablet width, preparation expands within the same workspace and can be closed without losing text, pointer position, or save state. Do not maintain two independent desktop/tablet DOM trees or switch routes solely for layout.

For a ready board at 1133x610, the first viewport must expose context, render shortcuts/activity and at least one usable candidate row without traversing authoring prose. Expanding an input should bring that input into reach by deliberate action; polling must not scroll or collapse it. A compact sticky action/status area must not cover focused content or consume most of the short viewport.

## Inputs, prompts and renders

**AI prompt updates are explicit.** Changed prompt-relevant preparation marks an AI-authored prompt as needing an update. Render shortcuts explain the blocker and point to Update prompt; they never silently ask an AI writer to replace the prompt and queue images.

**Deterministic compilation remains automatic.** Character compilation can continue at preparation/render time. A shared Preview prompt action shows the current compiled text and resolved reference order. If saving input edits is required, say so before preview or render rather than quietly using older saved settings.

**Direct prompt entry remains supported.** Image Generation and editable authored prompts show Unsaved / Saving / Saved / Save failed. Explicit Save prompt can adopt an operator-edited prompt for the current inputs without forcing a fresh AI request. Preserve the previous text until a replacement has succeeded and been accepted where the workflow uses proposals.

| Event | Proposed visible result | Required persistence/guard |
| --- | --- | --- |
| Open a new asset | Required inputs shown, clear missing prerequisites | No inferred creative defaults that change scope. |
| Edit preparation | Unsaved beside the section and its header | Preserve edits through layout changes; guard navigation. |
| Save prompt-relevant inputs | Prompt needs update for authored text; current compilation available for deterministic paths | Compare workflow-owned input revisions/basis, not a browser timestamp. |
| Receive interview suggestions | Before/after suggestions with acceptance checkboxes | Unapplied suggestions do not change saved inputs or render requests. |
| Apply selected suggestions | Save only selected changes, report count and affected sections | Retain service revision/exact-text validation. Unselected changes remain inspectable without silently applying them. |
| Update prompt | Writing prompt, then ready or an explicit error | Bind job to scope and saved input basis. A late result cannot overwrite newer edits; keep it as a reviewable result where useful. |
| Render ready prompt | Reserve requested slots, then Queued / Rendering / Collecting | Freeze exact prompt, settings and ordered image bytes through existing services. |
| Update inputs during an active render | Next render changes; active request remains bound to its snapshot | Do not rewrite in-flight or completed production records. |
| Retry a failed request | Retrying the original request, if supported | Preserve frozen retry inputs and attempt fencing. Regenerate is separately labeled and uses current prepared inputs. |
| Review a completed candidate | Prompt used for this image and Captured inputs, in order | Inspecting and comparing never changes next-render sources, selection or locks. |

Backend ownership is necessary for prompt freshness. Reuse Minor Character's prompt-basis concept and existing Narrative source snapshots/revisions; add narrowly scoped optional metadata only where the current record cannot express the contract. Compute basis from the saved effective inputs, relevant template/style revisions and reference identities for new work. Do not add recurring scans of completed images or the full library.

Older authored prompts without a recorded basis show Freshness not recorded. Let the user inspect and explicitly save/adopt or update that prompt for a new request. Preserve existing images, selections and locks. Rendering eligibility and source advisories remain distinct.

## Standard action and state vocabulary

| Meaning | Label and presentation |
| --- | --- |
| Persist edited fields | Save inputs, Save prompt, Save settings, or Save draft, according to the object. Use primary teal only for the relevant next action. |
| AI authoring | Write prompt initially; Update prompt when inputs changed or the operator requests replacement. State the model in a compact effective-model label. |
| Apply proposed edits | Apply selected changes, with a count. Use checkboxes and readable before/after rows; keep full diffs optional. |
| Queue new images | Draft 1, Draft 4, Final 1, Final 4, with consistent glyphs and counts. Show exact disabled reasons and available slots. |
| Automated advice | AI review, with the actual model shown as supporting text. Replace raw Started/Finish with Queued / Reviewing / Review complete / Review outdated / Review failed. Keep ranking advisory. |
| Choose a working result | Select / Deselect. Selection does not imply publication. |
| Protect/publish the workflow result | Lock / Unlock. Explain private locks such as Minor Character Style and private wizard tests; show Inventory publication separately where it occurs. |
| Publish Image Generation output | Add to Inventory / Update Inventory. Preserve its independent per-candidate publication model; do not disguise it as a workflow lock. |
| Replace or recover work | Regenerate Draft, Upscale Draft, Regenerate Final, Retry, Cancel queued render. Never interchange their consequences. |
| Destructive operations | Clear slot, Delete drafts, Delete non-selected, Archive image, or Delete workspace. Use explicit object/scope; keep protected-effect previews and per-effect approvals. |
| Supporting actions | View image, Open workspace, Compare, Copy, Download, Refresh. Refresh reads state; it does not rerun creative work. |

AI review is the proposed user-facing label replacing Luna Review; model attribution remains visible. This removes a model-specific action name from workflows that can use another model. Preserve stable action keys for adapters and revise affected existing selectors when the label changes.

## Visual system

Use the existing light theme, Segoe UI/system type, and semantic CSS tokens as the foundation. Revise the style guide once these rules are accepted, then enforce it through shared components rather than repeated page overrides.

- Teal is the primary action and selection accent. Green confirms success, amber signals attention, red signals errors or destructive actions, and purple marks keyboard focus. Draft uses the existing soft teal; Final/upscale use the existing deep violet quality token. Quality and focus must remain distinguishable by shape, label and placement.
- Use sentence case, one SVG glyph vocabulary, consistent 8px control/card corners, a 4px spacing scale and restrained borders. Use larger spacing between unrelated groups. Replace Unicode/emoji controls as affected screens migrate.
- Target 16px body text and 14px field labels/supporting instructions. Reserve 12px for minor metadata; do not put prerequisites or recovery instructions into tiny metadata text.
- Keep familiar repeated image actions compact, with accessible names and a way to reveal their labels on touch. Show text on uncommon or consequential actions. Build the same action order in cards and viewers from explicit action definitions.
- Prefer native radio groups for two to four short, stable choices. Use searchable selection for long or growing lists such as Inventory, species and models. View navigation can use visible labeled choices when space permits; do not replace every long select with an oversized radio list.
- Use consistent field/action/status anatomy, readable line lengths, empty/loading/error treatments and primary/secondary emphasis on settings and auxiliary pages as well as generation pages.
- Treat contrast and focus as measured acceptance checks. Token reuse and a screenshot alone do not prove accessibility.

## Async feedback

Use one small operation-status presentation across action groups and dialogs. It consumes workflow state; adapters retain all domain actions and polling.

| State | Message behavior |
| --- | --- |
| Submitting | Acknowledge immediately beside the initiating action and prevent duplicates. |
| Queued | Identify the object/count and say it is waiting. Do not claim rendering has begun. |
| Running | Show the actual stage and known progress, with elapsed time when available. Never invent percentages. |
| Succeeded | Confirm the actual effect: Prompt saved, Four drafts queued, Selected slot 3, or Locked and published. |
| Failed | Retain the error locally, summarize the impact, and show a valid recovery action. Expand technical details separately. |
| Outcome unknown | Reconcile the request/status before suggesting resubmission. Preserve the draft and request identity. |
| Paused or unavailable | Keep the last known state, explain the affected work, and retain scope. Distinguish storage, connection and validation problems. |

Show local status in the same viewport/scroll region as its action. A compact board activity summary can mirror it when preparation is collapsed. Put modal feedback inside the modal. Keep active progress and failures until resolved; successful feedback may quiet down once the changed object remains visible.

Disable only duplicate/conflicting work. Independent completed candidates remain reviewable while other slots render. Scope every pending action and result by universe, workspace, view/target, revision and attempt where supplied. Poll compact state only while relevant visible work is active, refresh details when it settles, and preserve focus, zoom, comparisons, disclosures and draft text on updates. Keep existing system-level recovery monitoring under its owning service rather than moving it into every page.

## Images and image inputs

**One viewer foundation.** Extend `review_image_zoom.js` and extract the useful full-size shell from `zet.js` into a focused viewer module. The Candidate Board review and viewing-only overlays share image containment, navigation, explicit Zoom in/out/Reset, zoom indicator, touch pan/zoom, Escape, focus return and safe sizing. Candidate review adds decisions, comparisons and frozen provenance through its existing adapter.

Click/tap or keyboard activation of a static thumbnail opens this viewer. Provide Open workspace as a separate action where a thumbnail currently doubles as navigation. Input previews also offer full-size viewing. Editing canvases retain their placement/crop gestures and provide a dedicated expand/view action that does not steal those gestures.

Choose a documented touch interaction: pinch zoom and drag to pan inside the image area, with visible zoom controls as an equivalent path. Do not consume page scroll or browser zoom gestures outside that area. When zoom exceeds fit, provide panning to inspect every edge. Image changes reset to fit unless the comparison-only change explicitly preserves zoom.

**One image input component.** Every active image acquisition surface offers Choose image, Paste image and Image Inventory. It also owns label/caption, preview, replace/remove, acquisition status, keyboard paste/drop, file constraints, and stale-scope cancellation. Clipboard permission/failure uses local instructions and preserves the previous input.

The shared component returns an acquisition result to an adapter; it does not publish or choose file paths. Existing managed-upload handlers consume files, while Inventory adapters resolve eligible source IDs/reference keys within the current universe. Preserve ordered bindings and labels. Selecting a different source while a read is pending invalidates the older result.

Minor Character currently requires an approved Inventory source ID. Its file/paste path should present an explicit Import and use confirmation through existing catalog services, reusing duplicate detection and recording provenance. It must not silently add or overwrite Inventory content. Narrative element sources should use their existing Inventory/reference rules with the same explicit import path when a file must become a catalog source. Character/Costume wizard and Head inputs can keep managed private sources. Task screenshot inputs can copy an eligible Inventory image as an attachment, without adding a creative source binding.

| Migration group | Existing owner | Required outcome |
| --- | --- | --- |
| Character Wizard references | `character_wizard.js` | Replace Ctrl+V-only instructions and native duplicate handlers with all three acquisition paths and shared preview. |
| Costume Wizard references and private trials | `zet.js` costume handlers | Common acquisition and preview; preserve captions, private revision and accepted costume handoff. |
| Head FRONT/phase references | `character_asset_container.js` | Common input component plus existing phase/reference mode semantics and private upload validation. |
| Minor Character source and Style reference | `minor_characters.js`, collection service/router | All acquisition paths with explicit catalog import when required; retain private Style versus published official views. |
| Image Generation references and Reconstruction | `image_generation.js` | Actual async Paste button, shared picker, visible ordered reference slots and clear source replacement. |
| Narrative element/reference images | `narrative.js`, reference/catalog services | Common picker/import presentation, preserved source kind and immutable submitted snapshots. |
| Inventory add/import/replace | `zet.js`, catalog services | Common acquisition; explicit replacement/publication effect and no action against the source asset merely because its bytes were chosen. |
| Task screenshots | `task_capture.js` | Common acquisition and safe viewer; keep captured task context and external submission explicit. |

## Wizards and proposed changes

Align Character, Costume, Minor Character intake/Style and Reconstruction around the same visible stages: References and goal, Analyze/interview, Review suggested inputs, Optional private test where supported, and Accept/save into the production workspace. Keep workflow-specific sections and eligibility rules; do not add a new private rendering stage to a workflow that has none.

Use shared section headers, step status, model attribution, before/after proposal rows and acceptance checkboxes. Apply selected changes is an explicit batch action with a visible result. Keep current facts editable, do not overwrite them with an arriving proposal, and retain rejected/unselected suggestions as history when useful. Private tests must show which draft revision they used and whether they match the current draft.

After acceptance, open the corresponding production workspace in the same context with its preparation summary and board ready for the next allowed action. Acceptance never silently queues a new production render or locks a candidate.

## Auxiliary pages

- Compare: remove the active legacy loader, use independently scoped left/right state, retain the view position, show side-specific loading/errors and unify the viewer. Use readable selectors and explicit identical-source labeling when both sides are the same.
- Candidates: label the destination Scene imports or an equally clear import label. Distinguish no configured source, unavailable source, no matching briefs and imported items. Keep provenance/acknowledgement and import idempotency.
- Identity Keys/Turnarounds: shared source thumbnails/viewer and local progress; clear crop/save/lock semantics; named missing view links. Full sheets retain eight-view requirements; partial sheets follow their existing allowed-source contract.
- Zines: visual source cards/picker, required-slot completion, honest partial-fill summaries, editable assignments and a reachable print preview. One source may be reused where already supported. Keep finished source bytes unchanged.
- Inventory: active filter chips and clear-all, shared cards and viewer, named detail sections, full reference tag available on demand, searchable organization pickers and consistent image publication/replacement messages.
- Template Editor: in-place character/costume chooser, useful empty state, reachable Save/Validate status and conflict recovery. Preserve the existing source service and unsaved edit protections.
- Config/Queue: group by purpose, compact status and recovery, expandable technical details, row-local process feedback, and per-section save state. Inventory/backend settings require an active-consumer audit; do not remove fields based on names alone.
- Pipeline tools: the inspector reads legacy pipeline directories rather than current NarrativeStories/container storage. Replace useful diagnostics with scoped current-service projections and remove unsupported reset actions from the active path after checking callers. Preserve legacy files and compatibility redirects; do not revive retired workflows.
- Recent Renders: compact thumbnail rows with scope, count, latest activity, and separate Review/Open board actions. Preserve current event-driven updates.
- Universes/species/manuals/tasks: common page/form/dialog anatomy, readable content width, explicit scope and save state, local validation, and consistent copy/download feedback. External task submission remains an explicit final action.

## Validation and done criteria

The implementation must pass existing affected E2E scenarios, a final complete approved suite, and disposable interaction/layout checks for states those scenarios do not assert. Add no permanent tests or dependencies without separate approval.

At desktop 1920x1080 and 1366x768, and landscape tablet 1133x610 and 1024x768 CSS viewports, check a representative ready board, pending render, failure, open preparation, long names, full-size review, input picker, proposal review, and unsaved-change guard. Include coarse-pointer emulation in disposable checks. Validate keyboard focus and reflow; width-only screenshots are insufficient. Treat physical tablet clipboard/touch validation as a documented handoff check if hardware is unavailable.

Before final rollout, recapture fresh states on the implemented Test release with correctly named routes/profiles and before/after links to the original evidence. A complete bundle must also match the intended route, dimensions and visible state. Do not repeat expensive generation solely for color/layout comparisons; use isolated prepared fixtures for UI mechanics and declare live pipeline verification separately.
