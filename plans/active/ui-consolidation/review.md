# UI evidence and implementation review

This document supports the [UI consolidation brief](../ui-consolidation-and-workflow-alignment.md). Findings below come from captured pixels, captured UI structure, and focused source inspection. Prior reports are leads to investigate, rather than final defect diagnoses.

## Review boundary

The initial captures referenced below used `d6143b9f4c7550e8b3ec3dd56cc86c3ebb5b60d1`. The [staged Test evidence update](#staged-test-evidence-update-2026-11-25) records the later implementation release and supersedes that initial release identity for acceptance evidence. Existing changes in the checkout include capture tooling and documentation; this review makes no application changes.

Evidence roots, relative to this file:

- [Fresh Character run](../../../../Zet_Tester/runs/ui-review-2026-11-24/2026-11-24T22-26-16-196Z-3d860f4f/resume-2026-11-24T22-55-50-296Z-07ef981b/evidence/manifest.json), abbreviated C below.
- [Fresh Minor Character run](../../../../Zet_Tester/runs/ui-review-2026-11-24/2026-11-25T00-55-58-771Z-e10062cb/evidence/manifest.json), abbreviated M.
- [Fresh Narrative run](../../../../Zet_Tester/runs/ui-review-2026-11-24/2026-11-25T02-09-38-251Z-217738d2/resume-2026-11-25T02-20-40-427Z-fd91bfc6/evidence/manifest.json), abbreviated N.
- [Fresh Image Generation run](../../../../Zet_Tester/runs/ui-review-2026-11-24/2026-11-25T03-02-22-304Z-cae1334f/evidence/manifest.json), abbreviated G.
- [Direct journeys](../../../../Zet_Tester/runs/ui-review-2026-11-24/direct-character-library-journeys/browser-session/evidence/manifest.json), abbreviated D.
- [Structural page sweep](../../../../Zet_Tester/runs/ui-review-2026-11-24/direct-page-sweep/evidence/manifest.json), referred to as the sweep. Its per-profile manifests contain actual capture paths.

Use each state record's URL, viewport, scroll position, and UI structure as the authority. A capture's complete status establishes artifact collection, not that the requested page or workflow loaded correctly.

## Evidence corrections and missing observations

1. D `fresh-candidates-tablet-landscape` and `fresh-candidates-tablet-portrait` actually show Zine, with an unsaved-change navigation guard. They cannot establish tablet Candidates coverage.
2. D `universe-settings-desktop-final` and the following two settings captures also remain on Zine. Use the earlier settings captures or `confirmed-universe-settings-*` with the actual recorded dimensions.
3. D `confirmed-universe-settings-desktop`, `fresh-animation-empty-desktop`, `fresh-animation-one-shot-desktop`, and `narrative-text-editor-text-entered-desktop` are actually 810x1080. D `fresh-character-overview-desktop` is 1280x720. Desktop coverage must use other verified captures or be recollected.
4. The four fresh workflow families completed, but stable tablet captures do not establish every intermediate wizard, pending state, review modal, or touch interaction on tablet. Width emulation with DPR 1 and zero touch points does not establish physical tablet target sizing, clipboard permission, pinch behavior, or browser chrome effects.
5. Turnarounds requires all eight current source views. The campaign intentionally generated only three. Disabled generation is consistent with service readiness; the review should improve prerequisite guidance and then verify a complete eight-view source separately.
6. Candidates is an importer of configured Adventure Log Markdown briefs. It is not the gallery of generated Narrative image candidates. An empty Source list does not show a failure to collect the new assembly.
7. Zine slots are text inputs with a datalist, not fixed select controls. Fill from Story assigns each available scene once, beginning with the front. With one scene, missing interior pages are expected. The captured validation error does not prove that a valid page assignment cannot be saved. The existing approved Narrative Zine scenario exercises valid repeated source assignments.

## Initial prioritized findings

P1 means a blocked or misleading production interaction requiring an early fix. P2 means substantial usability or consistency work. P3 means supporting polish. Priorities below are review proposals.

| ID | Priority and confidence | Observed issue and proposed outcome | Evidence and source owner |
| --- | --- | --- | --- |
| UI-01 | P1, source confirmed | Compare initializes its new independent-side controls and then calls the legacy phase loader, which dereferences controls no longer present. Remove the obsolete active loading path and surface side loading failures locally. Verify menu entry, direct URL, context changes, and each comparison side. | Sweep Compare failures; D `fresh-character-compare-*` shows the new interface can render before the old path fails. `zet.js`: `activatePage`, `initializePhaseComparisonControls`, `loadPhaseComparison`, `loadCompareSide`; `index.html` Compare markup. |
| UI-02 | P1, source confirmed | Text editing is enabled for an unlocked, unselected assembly candidate even when another candidate is locked. Finishing implicitly selects the edited candidate and fails at the selection guard. Present save and selection as explicit, separately explained outcomes; retain the draft and allow a safe exit. Do not silently unlock or replace the current published selection. | D text-editor captures and report; `narrative_candidate_board.js` edit-text eligibility; `scene_text.js` `save`/`finish`; `NarrativeSceneTextService.confirm`; shared board service `select`. |
| UI-03 | P2, source confirmed | Candidates sets Loading before fetching sources and returns without clearing it when none exists. End with a meaningful no-sources state and configured-source guidance. Rename the navigation destination to explain its import purpose and avoid confusion with image candidates. | D `fresh-narrative-candidates-empty-desktop`; `zet.js` `loadSceneCandidates`; `SceneCandidateSourceService.list_sources`; `NarrativeCandidateImportService`. |
| UI-04 | P2, pixels and source | Narrative places a long expanded authoring section before Render Controls and results. On landscape tablet the initial viewport contains no render actions or candidates. Give all main workspaces a common preparation/render/review layout that prioritizes the board when returning to production. Preserve full access to direction and placement tools. | D `fresh-narrative-final-assembly-tablet-landscape`; N final captures; `narrative.js` target editor; `narrative.css`; comparison with Minor Character collapsed inputs and shared board hosts. |
| UI-05 | P2, pixels and source | Candidate review puts actions and long advice in the same scrolling rail. Keep navigation, zoom, selection/lock and their local feedback reachable while advice and provenance scroll. Reduce title noise by moving full candidate IDs to copyable details while retaining accessible identity. | D `narrative-assembly-review-locked-desktop`; G `img2img-candidate-review`; `candidate_board_component.js` review renderer; `candidate_board.css` `.zcb-review-layout`, `aside`, header. |
| UI-06 | P2, source confirmed | Image input behavior is split. `image_input.js` supplies file selection and async clipboard; Inventory selection is a separate callback in Image Generation and other pages. Character Wizard's paste action tells the user to press Ctrl+V. Introduce one input component with browse, paste, Inventory, preview, replace/remove, status, and context fencing. | `image_input.js` `attach`; `character_wizard.js` reference handlers around line 357; `image_generation.js` reference picker; costume reference handlers in `zet.js`; inspect all consumers before implementation. |
| UI-07 | P2, source confirmed | Shared full-size viewing already attaches wheel zoom, so zoom is not wholly absent. It lacks the Candidate Board's explicit Zoom In/Out/Reset controls. Add one reusable viewer shell with buttons, touch panning/zoom strategy, labels, close/focus behavior, and optional navigation/actions. Migrate specialized viewers through adapters. | `zet.js` full-size overlay construction and `enableFullscreenImage`; `review_image_zoom.js`; `candidate_board_component.js` zoom controls; Character Hub and Inventory consumers. |
| UI-08 | P2, pixels and source | Feedback mixes raw lifecycle labels such as READY, DRAFTING and Finish with neutral paragraphs. Wizard stages have different progress presentations; the effective model is absent from visible Costume Wizard summaries. Use a shared local operation presentation with readable stage, affected object, queue/running distinction, durable failure, and optional details. | C wizard and costume report/captures; M proposal captures; G reconstruction captures; `character_wizard.js`, costume wizard in `zet.js`, `image_generation.js`, Narrative controller, shared board lifecycle formatter. |
| UI-09 | P2, source confirmed | Small fixed choices remain hidden in selects, including scene-text Tail and universe style; large dynamic context lists also use selects. Replace suitable small sets with native radio groups and independent proposal acceptance with checkboxes. Keep searchable pickers for large lists. Choice changes must not dispatch a render or accept an AI proposal. | D scene text/style captures; N inputs; `scene_text.js`; `narrative.js`; shared board field renderer and `interview_proposals.js`. |
| UI-10 | P2, pixels and source | Compare uses narrow side-by-side selectors with clipped long context values; review cards wrap action rows unevenly. Responsive rules must use available height and pointer capability as well as width. Keep full context discoverable and 44px touch action targets without shrinking images into unusable strips. | D Compare tablet captures; C landscape locked board; `candidate_board.css`; `zet.css` shell and Compare layout. Existing coarse-pointer CSS is a foundation, not a physical-device result. |
| UI-11 | P2, pixels and source | Similar actions use differing text, glyph decoration, palette overrides, spacing, and button emphasis. Consolidate semantic tokens and explicit shared action definitions; document Draft/Final quality colors separately from primary/danger and keyboard focus. | C correction and wizard captures; G reconstruction and review; `UI_STYLE_GUIDE.md` vs `candidate_board.css` Final palette; `image_card_ui.js`; page-specific rules in `zet.css`/`narrative.css`. |
| UI-12 | P2, pixels and source | Zine editing exposes long raw source tags and an ambiguous Scene field instead of a visual source chooser. Partial Fill from Story reports Filled without listing missing required slots. Add thumbnail/title picking, visible completion requirements, and local page validation. Recheck actual creation with valid fresh assignments before alleging a storage defect. | D Zine captures; `zet.js` `loadZineStorySources`, `fillZineFromStory`, `saveZine`; `index.html` datalist inputs; `ZineService` required slots. |
| UI-13 | P2, source confirmed prerequisite | Turnarounds shows MISSING and 3/8 counts with view names but no direct next action. Explain the missing views near Generate, link to each source board, and show the selected task's source previews. Validate complete-source generation before proposing changes to required-view semantics. | D Turnarounds captures; `zet.js` `renderTurnaroundTable`; `TurnaroundService` readiness and `TURNAROUND_VIEW_ORDER`. |
| UI-14 | P2, source and workflow reports | Character preview/compile, Narrative Write Prompt, Image Generation direct text/reconstruction, and Minor Character interview all connect inputs to the shared board differently. Expose one visible sequence and readiness summary while retaining the actual compiler and domain service contracts. Distinguish next-render prompt and references from the frozen production record of a reviewed image. | Four fresh reports; `character_asset_container.js`, `narrative.js` and its adapter, `minor_characters.js`, `image_generation.js`; Candidate Board integration contract. |
| UI-15 | P1, source confirmed | Both the text editor's Close action and Escape run `finish(true)`. When confirmation fails, neither provides a separate discard/leave path. A draft save also happens before confirmation, so a failed finish can already have persisted text changes. Provide Close with Save draft / Discard unsaved changes / Keep editing as applicable, keep Finish explicit, and state what was saved when a later step fails. | `scene_text.js` `finish`, `oncancel`, `save`; `NarrativeSceneTextService.confirm` writes finished bytes before selecting. This qualifies the earlier report's claim that text was simply discarded. Recheck persisted state during implementation. |
| UI-16 | P2, pixels and source | Config mixes process management, model discovery, rendering settings and legacy backend values in a long form with a distant Save action. Process rows expose Start, Stop and Restart together without matching their visibility to running state. Group settings by purpose, show per-section save state, and put process feedback in the affected row. Confirm which settings are active before removing stale controls. | Sweep Desktop `page-local-image-config`; `zet.js` `renderProcessRows`, `runConfigProcessAction`, `renderPipelineControls`; config/process services. No process action was executed. |
| UI-17 | P2, pixels and source | Pipeline Controls exposes a reset form alongside a message that legacy pipelines are unavailable. Pipeline Inspection shows No matching pipelines in an empty diagnostic layout. Make active workflow support explicit; remove obsolete active navigation/actions after checking consumers, or present an informative unavailable state with a route to supported tools. Do not restore retired pipelines to fill the page. | Sweep `page-pipeline-controls` and `page-pipeline-inspection`; `zet.js` `loadPipelineControls`, `loadPipelineInspections`; corresponding service/router owners. The full legacy caller audit is an implementation prerequisite. |
| UI-18 | P2, pixels and source | Queue rows combine raw exceptions, stage, recovery instructions and ages measured in thousands of minutes in a very wide Details cell. Use a compact state/target summary with a local recovery action and expandable technical details. Preserve failed job history and durable queue semantics; a failed historical row is not evidence that this campaign's rendering failed. | Sweep Desktop `page-ai-controls`; `ai_queue.js` row formatter and action lifecycle; AI job service. |
| UI-19 | P2, pixels | Recent Renders presents a long list of links and counts with little visual recognition. Use a shared thumbnail row/card, readable scope and latest activity, plus Open board / Review where supported. Preserve the existing event-driven updates and do not add idle polling. | Sweep Desktop `page-recent-renders`; `zet.js` Recent Renders rendering/events; shared board harvest service. |
| UI-20 | P2, pixels and source | A directly opened Template Editor shows a large empty editor and instructions to open a template without an obvious chooser in that view. Add an in-place template picker and clear empty/loading/unavailable state. Preserve conflict handling and the user's unsaved text. | Sweep Desktop `page-template-editor`; `template_editor.js`; `SourceEditorService`; existing template-edit scenario. |
| UI-21 | P2, pixels and source | Costumes uses generic Open/Add New alongside Costume Wizard, while shared primary/secondary emphasis varies in neighboring settings pages. Name actions by outcome, make wizard versus existing template import clear, and apply the same form/action/status anatomy. Universe lists/settings and Help use different content widths and heading/action placement. | Sweep Desktop `page-costumes`, `page-universes`, `page-help`; `index.html`, costume handlers, shared page/form styles. Markdown imports remain file inputs, not image inputs. |

## Reusable foundations to retain or improve

- `candidate_board_component.js` and `candidate_board.css` already centralize render controls, stable slots, review, comparisons and actions. Consolidate around this owner rather than introducing a second board.
- `image_card_ui.js` supplies shared SVG vocabulary and action decoration. Explicit action metadata would reduce dependence on inferred text and page selectors.
- `review_image_zoom.js` supplies shared wheel zoom and programmatic steps; extend its interaction contract for viewers and touch rather than implementing page-local zoom engines.
- `interview_proposals.js` is a candidate owner for shared before/after presentation, acceptance checkboxes, diff expansion and apply feedback. Domain services keep proposal validation and persistence ownership.
- `image_input.js` can evolve from a clipboard decorator to the common image-acquisition presentation, with adapters translating a file or Inventory reference into each workflow's existing input model.
- `AIWorkflowService`, image-production services, workflow repositories and publication guards retain backend ownership. Shared UI code must not discover library files or orchestrate pipelines itself.

## Canonical surface coverage

The page sweep has 21 successful destinations at each of three viewport profiles and a failed Compare attempt per profile. These are top-of-page structural samples. The fresh run and direct journey manifests supply deeper production states; they do not fill every unsupported or untouched state below.

| Surface | Evidence inspected or available | Planned treatment |
| --- | --- | --- |
| Character Overview | Sweep plus fresh direct overview | Shared context, thumbnail cards and viewer; retain direct board links and safe management dialogs. |
| Character Asset Containers | Fresh Character run, all four pipeline families | Common preparation/board layout; shared readiness and prompt handoff; guided missing references. |
| Minor Characters | Fresh intake, Style refinement, three published views | Same wizard and board anatomy; retain private Style lock versus published official views. |
| Identity Keys | Fresh crop, save, publish and Inventory detail | Unified preview/viewer, local processing state and explicit save/publish actions. |
| Turnarounds | Fresh incomplete source state | Guided eight-view prerequisites, shared preview/viewer and aligned generation/promotion language. Complete generation needs a valid eight-view source. |
| Costumes and Costume Wizard | Structural costume list and fresh wizard/test/acceptance | Consistent intake, proposed changes, private test, accept and downstream handoff. |
| Image Inventory | Fresh item list and details; structural page | Shared input picker, search/filter visibility, card actions, detail sections, organization and full-size review. Organization subviews need deeper acceptance inspection. |
| Image Generation and Reconstruction | Fresh text/image generation, reconstruction and correction | Align prompt, references, status and board; preserve correction ancestry and explicit Inventory publication. |
| Narrative Stories, scenes and targets | Fresh authoring, all target kinds and locked assembly | Expandable preparation with board priority; common proposal review; direct source/placement editing. |
| Narrative crop, lettering and animation | Text editor and one-shot animation; existing finishing scenario | Fix selection/finish/exit semantics; shared editor chrome, clear stage/preview/save feedback, touch and non-drag controls. Crop and exported animation are not fully inspected by top-level captures. |
| Candidates importer | Valid desktop capture; tablet labels are invalid | Correct source-empty/loading/error states, clarify import role, inspect populated source/import/review as a separate validation task. |
| Zine Maker | New form, fill and incomplete validation | Visual page-source chooser, requirements and partial-fill feedback; validate complete fresh assignments and print preview. |
| Universes, New Universe and settings/species | Structural captures, direct settings/style dialog | Shared forms, scope confirmation, inline validation and save status; inspect species dialog with long labels during implementation. |
| Template Editor | Structural empty state and source/test inspection | In-place chooser, common editor action/status bar, unsaved/conflict retention. |
| AI Queue | Structural populated historic failures and source | Readable compact activity rows, explicit recovery, local mutation feedback and expandable diagnostics. |
| Config | Structural process/settings form and source | Purpose-based sections, active setting audit, consistent per-section save and process row status. |
| Pipeline Inspection and Controls | Structural empty/unavailable state and source | Audit current ownership, retire stale active entry points or connect useful diagnostics to current workflows. |
| Help/manuals | Structural rendered manual | Consistent readable width, obvious manual picker, local copy/download acknowledgements and contextual help links. |
| Recent Renders | Structural populated links and event source | Thumbnail-first activity rows with direct board/review entry; preserve event-driven updates. |
| Compare | Fresh independent-side controls plus legacy error | Fix loader path and per-side failures; responsive context controls and unified image viewing. |
| Shared dialogs and task capture | Viewer, review, style/text and unsaved-change captures; source | One accessible dialog foundation, reusable action vocabulary, safe close/focus behavior and shared image acquisition. Never submit a task during validation. |

## Prompt and render handoff today

| Workspace | Current behavior | Consequence for alignment |
| --- | --- | --- |
| Character | `prepare_candidates` compiles the current masters and resolved ordered references for each new request. Preview compiles through the same focused service. | Deterministic compilation can remain automatic. Show current input readiness and make the submitted prompt/reference snapshot inspectable. |
| Minor Characters | `prompt_current` and a service-side prompt-basis comparison require Write or Save Prompt for current inputs before generation. | Expose why a prompt needs updating and use the same input/prompt readiness language as other workspaces. |
| Narrative | Write Prompt is an explicit authoring action. Render normally uses saved prompt text; the adapter blocks an assembly-mode mismatch but does not present a common input-to-prompt freshness contract. | Define what changing direction or sources does to the existing prompt and to render availability. Retain manual edits and explicitly applied interview proposals. |
| Image Generation | Direct prompt editing is saved by `flush` before board actions. Reconstruction has separate analyze, apply-prompt and compare/correct actions. | Avoid forcing a model-writing stage on direct text input. Show saved/manual state and any pending reconstruction proposal consistently. |

The shared presentation should show Inputs incomplete / Inputs saved / Prompt needs update / Prompt ready / Queued / Rendering / Ready to review. A single global busy flag would hide important distinctions. Concurrent independent slot renders and safe image inspection should stay usable.

Joe selected explicit Update prompt before render when relevant preparation changes. Render shortcuts must not trigger AI prompt rewriting automatically. Deterministic compilation and saving directly edited prompts remain distinct supported paths.

## Proposed common workspace contract

Joe selected one workspace with expandable preparation. The detailed layout and shared interfaces are specified in the [proposed design](design.md).

1. A compact context header identifies universe, subject/scene, pipeline/view and current selected/locked state.
2. Preparation contains structured inputs, references, wizard/interview and proposed changes. It remains available without leaving the current scope.
3. A render area shows input readiness, the next-render prompt, quality/count controls, and separate prompt/render/review activity.
4. The shared stable candidate board opens the same review shell everywhere. Reviewing a candidate never changes next-render sources or selects the image implicitly.
5. Candidate details show the exact prompt and ordered captured inputs used for that image. Selection, lock/publication and advisory assessment retain distinct meanings.

A presentation model can expose scope, preparation sections, readiness, prompt state, operation state, actions and the existing board model. Each workflow adapter keeps the compiler, API, saved-draft and source-binding semantics specific to its domain. No single merged storage schema or universal compiler is implied.

## Source navigation

| Responsibility | Primary inspected owners |
| --- | --- |
| Shared board and review | [component](../../../zet/web/static/candidate_board_component.js), [styles](../../../zet/web/static/candidate_board.css), [glyphs](../../../zet/web/static/image_card_ui.js) |
| Shared image acquisition and zoom | [image input](../../../zet/web/static/image_input.js), [zoom engine](../../../zet/web/static/review_image_zoom.js) |
| Character workspace and wizard | [container adapter](../../../zet/web/static/character_asset_container.js), [wizard](../../../zet/web/static/character_wizard.js), [compiler service](../../../zet/services/character_container_prompt_service.py) |
| Minor Character | [controller](../../../zet/web/static/minor_characters.js), [service](../../../zet/services/minor_character_service.py) |
| Narrative workspace and board | [controller](../../../zet/web/static/narrative.js), [board adapter](../../../zet/web/static/narrative_candidate_board.js), [generation service](../../../zet/services/narrative_generation_service.py) |
| Image Generation | [controller](../../../zet/web/static/image_generation.js) |
| Lettering | [editor](../../../zet/web/static/scene_text.js), [service](../../../zet/services/narrative_scene_text_service.py) |
| Shell and auxiliary pages | [shell/controller](../../../zet/web/static/zet.js), [template](../../../zet/web/templates/index.html), [global styles](../../../zet/web/static/zet.css) |
| Queue and source editing | [Queue](../../../zet/web/static/ai_queue.js), [Template Editor](../../../zet/web/static/template_editor.js) |
| Existing validation boundary | [Testing](../../../Docs/Testing.md), [approved E2E files](../../../tests/e2e) |

## Review standards

Use native control semantics and explicit keyboard behavior. Native radio groups fit mutually exclusive small choices; proposal checkboxes represent independent choices. See [W3C radio group pattern](https://www.w3.org/WAI/ARIA/apg/patterns/radio/).

Use the W3C [modal dialog pattern](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/) for focus entry, containment, Escape and return. Usable touch targets, visible focus, text contrast, status announcements and alternatives to dragging should be checked against [WCAG 2.2](https://www.w3.org/TR/WCAG22/). Zet's proposed 44px touch target is a product target; WCAG 2.2 AA's minimum target criterion is 24px with exceptions.

## Implementation verification gaps

- Inspect deeper auxiliary states that the top-level sweep did not capture, including Inventory organization, populated importer, species editing, valid Zine preview, and physical touch behavior. These are evidence gaps to validate, not assumed defects.
- The [design](design.md) and [packet breakdown](implementation.md) assign wizard/input/viewer consumers and explicit storage adapters. Verify the catalog Import and use route with each domain's eligibility; no silent publication is allowed.
- Validate the specified async unknown-outcome and stale-response contract with prepared failures and late results; source inspection alone does not establish its runtime behavior.
- Follow the packet validation map. Existing scenarios cover important task boundaries but do not establish the full visual/touch matrix or every failure case.

## Staged Test evidence update (2026-11-25)

The implementation was staged to Test at revision `1cec0a6e9261fe9e27420bd95403d1c9eec46a1d` / boot `63142226cd5943658cbda8d077305b29`. Production remained on its earlier revision. The final route sweep covers 22 dashboard pages at desktop 1920x911 and landscape tablet 1133x610, with 44 captures, zero activation errors and zero horizontal overflow. These are emulated viewports; no physical tablet or touch interaction was tested. Retained run reports and captures are under `E:\Zet\Zet_Tester\runs\ui-review-2026-11-24\`.

Fresh staged workflows completed for Character/costume, Minor Character, Image Generation and Narrative. The Character run completed Body Reference, Head Image Edit, Assembly, Costume Wizard and Costume Dressing with locks verified. It noted that the rendered blouse remained longer than the source and embroidery was denser/higher; treat this as a design-fidelity correction for that output, not a shared UI defect. Narrative backdrop, subscene and assembly all rendered, reviewed, locked and survived reload. The layouts and inputs worked in landscape emulation, but portrait selectors were cramped; portrait is outside the agreed target and should not drive a redesign without a product need.

The Image Generation Reconstruction comparison report completed and identified three major and one minor drift findings in the candidate gown: lost corset/embroidery/gemstone details, missing sleeves/ribbons, simplified skirt construction, and missing waist jewelry. The requested watercolor medium, wooden dress form and pale blue background were satisfied. If source fidelity is expected, apply the listed corrections and generate a new candidate before locking; retain this as an output-quality observation rather than a UI defect. The comparison action first surfaced `Permission denied` while saving its report, although a COMPLETE report later appeared on disk. Read-only ACL inspection found inherited Modify access for Authenticated Users on both the parent and report directory; no permission changes were made. The tester process identity and original write failure were not reproduced, so investigate the report-write lifecycle before treating this as fixed.

The first fresh Minor Character run found that switching to Style failed because reparenting the production workspace detached its form controls. Mounting into `#mc-authoring` restored ownership, and a new run completed on the staged release with Style and three official views selected, locked, published and refreshed. Preserve the form-boundary invariant when changing the shared shell.

### Recommended follow-up order

1. Resolve or reproduce the reconstruction report-save error using a disposable Test report; do not alter permissions without identifying why the initial write failed.
2. WP02 and WP03 passed focused disposable browser/API checks using completed-image fixtures. The explicit focus-restoration and saved-draft confirmation-error changes remain to be staged to Test. Inspect the remaining deeper states listed above.
3. Correct the costume and gown source-fidelity outputs only if those exact assets are needed; record new candidates and compare them before locking.
4. Keep landscape tablet as the acceptance target. Revisit portrait selector layout only if portrait becomes a supported task profile.
