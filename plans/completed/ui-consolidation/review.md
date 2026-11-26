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
| UI-19 | P2, accessibility confirmed; fixed and verified | Recent Renders repeated the accessible name `Review latest` for every board row. The short visible label remains, and each button now includes its board name in the accessible name. | 96fd Reconstruction resume exposed duplicate names; direct f64b Test inspection at desktop and tablet landscape verified board-specific names. |
| UI-22 | P2, pixels | Recent Renders presents a long list of links and counts with little visual recognition. Use a shared thumbnail row/card, readable scope and latest activity, plus Open board / Review where supported. Preserve the existing event-driven updates and do not add idle polling. | Sweep Desktop `page-recent-renders`; `zet.js` Recent Renders rendering/events; shared board harvest service. |
| UI-20 | P2, pixels and source; implementation complete | A directly opened Template Editor showed a large empty editor and instructions to open a template without an obvious chooser in that view. WP27 adds an in-place template picker and clear empty/loading/unavailable state while retaining the draft on a failed source switch. | Sweep Desktop `page-template-editor`; approved template-edit scenario and disposable chooser/open/conflict checks; `template_editor.js`; `SourceEditorService`. |
| UI-21 | P2, pixels and source | Costumes uses generic Open/Add New alongside Costume Wizard, while shared primary/secondary emphasis varies in neighboring settings pages. Name actions by outcome, make wizard versus existing template import clear, and apply the same form/action/status anatomy. Universe lists/settings and Help use different content widths and heading/action placement. | Sweep Desktop `page-costumes`, `page-universes`, `page-help`; `index.html`, costume handlers, shared page/form styles. Markdown imports remain file inputs, not image inputs. |
| UI-23 | P2, responsive navigation; visual check pending | At 1180x820 on Recent Renders, the responsive section selector appeared visually blank because the current route had no matching option. The Recent Renders option is present in Test release 2250. Confirm the selected label and return navigation when browser UI access is available. | Direct f64b Test route check; 2250 release source; `responsive-section-menu` and `RESPONSIVE_TOOL_PAGES` in `zet.js`. |
| UI-24 | P2, responsive context visibility; local fix pending Test | At 1133x610, Story and Scene header selectors truncated long selected names. Give the context controls more width at landscape-tablet breakpoints and check names, overflow, and task content height in Test. | Retained fresh Narrative tablet-landscape screenshot `fresh-narrative-final-assembly-tablet-landscape`; local layout change in `zet.css` needs visual verification. |

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

The implementation was staged to Test at revision `3254602ce7f2b9b02ee67875f7769099be3f05f3` / boot `3b880b6502b24ddfa6ac836c8ef11b3a`; its active-release record matches and the deployment log reports 20/20 approved E2E scenarios passed. Production remains on `aa8737b1d81ff7c28999fc03463586a309109b0f`. The final route sweep on the preceding UI revision covers 22 dashboard pages at desktop 1920x911 and landscape tablet 1133x610, with 44 captures, zero activation errors and zero horizontal overflow. These are emulated viewports; no physical tablet or touch interaction was tested. Retained run reports and captures are under `E:\Zet\Zet_Tester\runs\ui-review-2026-11-24\`.

Fresh staged workflows completed for Character/costume, Minor Character, Image Generation and Narrative. The Character run completed Body Reference, Head Image Edit, Assembly, Costume Wizard and Costume Dressing with locks verified. It noted that the rendered blouse remained longer than the source and embroidery was denser/higher; treat this as a design-fidelity correction for that output, not a shared UI defect. Narrative backdrop, subscene and assembly all rendered, reviewed, locked and survived reload. The layouts and inputs worked in landscape emulation, but portrait selectors were cramped; portrait is outside the agreed target and should not drive a redesign without a product need.

The Image Generation Reconstruction comparison report completed and identified three major and one minor drift findings in the candidate gown: lost corset/embroidery/gemstone details, missing sleeves/ribbons, simplified skirt construction, and missing waist jewelry. The requested watercolor medium, wooden dress form and pale blue background were satisfied. If source fidelity is expected, apply the listed corrections and generate a new candidate before locking; retain this as an output-quality observation rather than a UI defect. The comparison action first surfaced `Permission denied` while saving its report, although a COMPLETE report later appeared on disk. Read-only ACL inspection found inherited Modify access for Authenticated Users on both the parent and report directory; no permission changes were made. The tester process identity and original write failure were not reproduced, so investigate the report-write lifecycle before treating this as fixed.

The first fresh Minor Character run found that switching to Style failed because reparenting the production workspace detached its form controls. Mounting into `#mc-authoring` restored ownership, and a new run completed on the staged release with Style and three official views selected, locked, published and refreshed. Preserve the form-boundary invariant when changing the shared shell.

### Recommended follow-up order

1. The reconstruction report-save error did not recur: the report later persisted COMPLETE, and read-only ACL inspection found inherited Modify access. Do not change permissions based on this single transient error; retain the incident for monitoring if it recurs.
2. WP02 and WP03 passed focused disposable browser/API checks using completed-image fixtures, and their changes are present in the current staged Test release. Inspect the remaining deeper states listed above as follow-up evidence, not as confirmed defects.
3. Correct the costume and gown source-fidelity outputs only if those exact assets are needed; record new candidates and compare them before locking.
4. Keep landscape tablet as the acceptance target. Revisit portrait selector layout only if portrait becomes a supported task profile.

### Read-only disposition of remaining page states (2026-11-25)

On the current healthy Test release, the Inventory organization endpoint returned zero collections and zero keywords, and Narrative candidate-source discovery returned no configured sources. The populated Inventory organization and populated importer states therefore have no existing Test data to inspect; the empty states are configuration/data conditions, not demonstrated UI defects. Do not invent an Adventure Log source or add persistent organization data solely for screenshots. The approved 20-scenario deployment suite passed its Narrative Zine preview and Universe/Species editing scenarios, so those behaviors have existing functional coverage, although their interaction states were not captured in the final pixel sweep. No physical tablet is available in the current evidence set; landscape emulation remains the agreed acceptance target.

## Image Inventory observations and deferred scope (2026-11-25)

Joe requested that further Image Inventory work move to a separate, more focused effort. This plan records the current observations and does not schedule additional Inventory implementation. The shared image picker, input adapters, and existing page changes already completed in this plan remain in scope as delivered work.

Read-only inspection used the updated Production release `3254602ce7f2b9b02ee67875f7769099be3f05f3`, which is the same code revision as Test. Production contains 214 images, 19 entities and 10 reference sets. The image-catalog organization endpoint reports no collections or keywords. The Image Inventory search page shows nine cards across at 1920px; long logical-reference tags wrap across several lines and make cards uneven. At 1133x610, the responsive selector and organization tabs remain reachable; the Entities view shows a left list and a wide details pane that asks the user to choose an item. Entity, Variant, Reference Sets and Facets views were captured without edits.

Production has one configured read-only candidate source, Moonsea Adventures, with 11 candidate rows. The populated importer displays source-changed, imported, passed and available states together. Several source-changed rows show a Review source changes action; these are outstanding source-reconciliation tasks, not confirmed importer defects. The source path and record content are campaign data and remain unchanged.

Desktop and landscape captures are retained at `E:\Zet\Zet_Tester\runs\ui-review-2026-11-24\production-readonly-image-inventory-3254602\`. They are read-only page observations and do not constitute a complete interaction or touch audit.

## Pre-merge Test evidence (2026-11-25, revision f9fc7b0e)

All new evidence manifests in this campaign identify Test revision `f9fc7b0e1c60c5e76800c4629fb55ed6b1137440` and boot `bb4e7d0b15344574a598b70494ada5af`, matching `/api/health` and `state/active-release.json`. The 20 approved E2E scenarios passed during the Test release update. The cases were run serially with new unique workspace names; no prior workflow outputs were reset. Landscape tablet means the Zet_Tester 1133x610 CSS-pixel emulation, not a physical tablet.

| Workflow | Outcome on f9fc | Retained report |
| --- | --- | --- |
| Character and costume | Character creation, Body Reference correction, Head Image Edit, and Assembly FRONT plus both three-quarter views completed and were published. Costume Wizard reached Ready and its private FRONT render completed, but the clothing mismatch correction could not be submitted because the helper could not uniquely target `Upper body and waist > Refine section`. Costume acceptance and Costume Dressing remain incomplete. | [Character report](../../../../Zet_Tester/runs/ui-consolidation-f9fc-20261125/2026-11-25T19-23-59-245Z-12b9e6c4/report.md), [evidence manifest](../../../../Zet_Tester/runs/ui-consolidation-f9fc-20261125/2026-11-25T19-23-59-245Z-12b9e6c4/evidence/manifest.json) |
| Minor Character | Complete. Style was privately locked; Front, Front Left 3/4, and Front Right 3/4 were published and verified after refresh. Initial left-angle output faced the wrong way and was corrected through the allowed evidence-based refinement. Desktop, landscape and portrait viewport captures were inspected; landscape remained usable with vertical scrolling. | [Minor Character report](../../../../Zet_Tester/runs/ui-consolidation-f9fc-20261125/2026-11-25T20-53-15-925Z-322e521f/report.md), [evidence manifest](../../../../Zet_Tester/runs/ui-consolidation-f9fc-20261125/2026-11-25T20-53-15-925Z-322e521f/evidence/manifest.json) |
| Image Generation | Txt2img, img2img, and canonical/environmental style variants completed and were visually inspected. The run stopped at Reconstruction because the case expected an entry point before selecting a completed candidate. Source inspection shows the action is enabled on the selected candidate board; correct the case prerequisite and rerun Reconstruction/compare-and-correct before counting it complete. No candidates were added to Inventory. | [Image Generation report](../../../../Zet_Tester/runs/ui-consolidation-f9fc-20261125/2026-11-25T21-39-58-780Z-86ff0fe5/report.md), [evidence manifest](../../../../Zet_Tester/runs/ui-consolidation-f9fc-20261125/2026-11-25T21-39-58-780Z-86ff0fe5/evidence/manifest.json) |
| Narrative | Both new references were verified in the approved catalog. A first attempt stopped at inaccessible Details scoping; the retry used IDs and provenance from a read-only authoritative catalog check. It created the story and scene shell, then stopped before references or AI work because both effective model selectors stayed `general:latest`; field-specific helper selection did not work. | [Narrative report](../../../../Zet_Tester/runs/ui-consolidation-f9fc-20261125/2026-11-25T22-22-53-495Z-6af9c9dc/report.md), [resume report](../../../../Zet_Tester/runs/ui-consolidation-f9fc-20261125/2026-11-25T22-22-53-495Z-6af9c9dc/resume-2026-11-25T23-02-13-408Z-077fef36/report.md), [evidence manifest](../../../../Zet_Tester/runs/ui-consolidation-f9fc-20261125/2026-11-25T22-22-53-495Z-6af9c9dc/evidence/manifest.json) |

The f9fc workflow row above records the initial Test campaign only. The workflow
evidence was refreshed on Test `f8feb44` after deployment; its reports and a
later Wizard-only run on Test `3c6d66a` are indexed in
[Testing.md](../../../Docs/Testing.md). Costume Dressing was corrected from the
saved source and freshly rendered and reviewed. The `3c6d66a` Costume Wizard
run identified `codex:gpt-6-luna` for the section-authoring asks, while the
private image-render model remained unexposed. Its render followed the written
no-blouse-embroidery direction even though the supplied reference contains
bodice embroidery, indicating that the earlier placement mismatch reflected
conflicting inputs. Pointed ears were not visible and the neckline ruffle was
weak or absent in the new Wizard test render.

### New actionable findings

1. **Full-size image viewer close is obscured by zoom controls (high confidence).** Reproduced in the Costume Wizard and Inventory preview. The Close and zoom toolbar occupied the same upper-right corner; `zet.css` gave `.fullscreen-image-tools` z-index 10004 and `.fullscreen-image-close` z-index 10002. The merged fix moves Close to the safe-area-aware upper-left. The fresh 96fd Zet_Tester run verified that Close and zoom remain separate at desktop and tablet-landscape.
2. **Inventory card actions lack a named card scope (high confidence).** The live `image-catalog-card` is an unnamed `article`, and every Details button has the same accessible name. The tester could verify titles, IDs and Approved status but could not scope Details to verify provenance. Give each card a programmatic name from its title and make repeated actions identify their image, then verify keyboard/screen-reader and per-card operation.
3. **Narrative model picker controls are ambiguous (high confidence for the observed dashboard/helper contract).** The custom picker hid the labeled text input and inserted a button whose text was only the current model; Interview and Prompt writing controls therefore exposed the same name when both inherited the same value. The required `codex:gpt-6-luna` could not be selected through Zet_Tester. The merged fix adds each source field label and current value to its replacement button's accessible name. A fresh 96fd case independently set both selectors, saved, and verified persistence after reload at desktop and tablet-landscape.
4. **Costume section action was not uniquely addressable in the wizard.** Current Test `3c6d66a` reproduced the helper scope collision: Upper body and waist matched its heading and two field labels, so no refinement was submitted. The local fix gives each repeated section action and proposal checkbox an accessible name that includes its section. `node --check`, the approved Costume Wizard scenario, and a disposable assertion for distinct Refine button names passed. This fix still needs a merged Test deployment and direct browser/landscape verification; do not treat the image-fidelity mismatch as evidence that the UI action itself failed for a person.
5. **Reconstruction case prerequisite is incomplete, not yet an app defect.** The source action is intentionally attached to a selected completed candidate. Update the case to generate/select a baseline candidate before entering Reconstruction, then complete its analysis and compare/correct stages.

WP32's current Test release is 2250. The 20 approved E2E scenarios passed during deployment. Fresh AI workflow evidence was captured on f64b; 2250 adds two UI-only changes since that evidence: the Recent Renders compact-menu option and a board-specific accessible name for the Costume Hub template-edit button. No pipeline behavior changed. The Recent Renders option is confirmed in the deployed release source, but browser UI access is currently failing before a visual check. A local CSS change now gives context selectors a full row at landscape-tablet widths; it awaits Test visual verification. Costume Wizard model provenance remains unavailable in visible task/queue records, and its accepted preview has a remaining overskirt embroidery mismatch. Image Inventory findings are retained for the separately deferred effort, not implementation work in this plan. Production is out of scope. See the release and evidence record in [Testing](../../../Docs/Testing.md).

### Current-release workflow evidence (2026-11-26, revision f64b)

Test revision `f64bafc3ec125122354b1c08eb06da094eb2e69e` / boot
`ba42a0de1bf448fdbd1627b9d38346fd` matches the active-release record. The
deployment log reports all 20 approved E2E scenarios passed. New AI work was
run for this release. The complete Character FRONT report is
[retained here](../../../../Zet_Tester/runs/ui-review-2026-11-24/2026-11-26T06-36-01-676Z-eae544e0/resume-2026-11-26T06-55-51-770Z-91c2c197/report.md).

The Body Reference baseline stayed in Slot 2; the accepted corrected FRONT
ranked Slot 4 #1 and was locked. Its waist/hip change was modest, with age and
pose retained. Head Image Edit FRONT retained violet eyes, pointed ears, and
the short black bob. Assembly FRONT was ranked and locked, with slight
softness at the hair/neck edge. The accepted Costume Wizard draft completed
its private render and two correction/retest cycles. Its final overskirt
embroidery remained higher and sparser than the reference. Costume Dressing
FRONT completed a fresh four-image batch; Slot 4 #1 was locked and remained
locked after Refresh. Costume Wizard model provenance remains unverified
because no visible task or queue entry exposed it.

The first checkbox attempt failed because Template Improvement was collapsed.
Expanding the disclosure via the current accessibility tree exposed the
visible checkbox; the prompt preview showed the accepted waist/hip correction
and it saved successfully. This is a Zet_Tester targeting limitation, not
evidence of an application checkbox failure. During Costume Wizard's third
private render, Test displayed storage reconnect/unavailable feedback; after
the prescribed five-minute wait the same render returned `TEST_READY` without
resubmission.

Direct Recent Renders inspection verified board-specific `Review latest`
accessible names and no horizontal overflow at 1180x820. The responsive
section selector looked blank on that route and needs a follow-up visual
check. Earlier tablet observation: Story and Scene header selectors truncate
long selected names. These navigation findings remain open. Image Inventory
observations are intentionally retained for its separate effort and are not
scheduled here. Production was not accessed for this evidence pass.

### Targeted verification of viewer and model controls (2026-11-25, revision 96fd)

Test release `96fd8790ad714a867ad433390e46a638db016e6b` / boot
`0ec1054cd14e432e8f7aedeb5783add1` was health-verified. The focused Narrative
setup case confirmed both model controls can be set independently to
`codex:gpt-6-luna`, saved, and reloaded with those effective values intact. The
full-size viewer Close remained distinct from zoom controls in desktop and
1133x610 tablet-landscape captures. Report and captures:
[targeted Zet_Tester report](../../../../Zet_Tester/runs/ui-review-96fd/2026-11-25T23-39-59-669Z-dd25c46a/report.md)
and [evidence manifest](../../../../Zet_Tester/runs/ui-review-96fd/2026-11-25T23-39-59-669Z-dd25c46a/evidence/manifest.json).

New observation: at 1133x610, Story and Scene header selectors truncate their
selected names. The authoring model values remain legible. Consider moving or
reflowing context selection controls within the responsive shell while keeping
the active story/scene names discoverable without hover.

### Full Narrative workflow verification (2026-11-25, revision 96fd)

The fresh Zet_Tester run completed story and scene setup, backdrop creation,
transparent subscene preparation, final assembly, candidate review, and all
three locks. The Interview and Prompt writing models were independently set
to `codex:gpt-6-luna` and survived reload. Both exact approved Inventory IDs
were bound to the subject elements. Async progress was visible through
interviews, prompt writing, Draft 4 and Luna Review. Candidate full-screen
zoom in/out/reset worked. All three selected locks persisted after returning
to the scene overview and reopening each target.

Visual findings: the backdrop is coherent but adds a centered table and chairs
that reduce open floor. The subscene has a solid purple matte despite the
explicit transparent-background prompt, a significant output quality defect.
The final assembly is cohesive and follows left/right staging, though hands
around the teapot and cup are crowded. These are generated-image outcomes, not
workflow blockers. A prompt-model selection action initially matched multiple
visible controls in the helper; the fresh snapshot resolved the target and the
saved prompt provenance was correct, so retain as a targeting observation.

Evidence: [full Narrative Zet_Tester report](../../../../Zet_Tester/runs/ui-review-96fd-full-narrative/2026-11-25T23-53-15-866Z-2c54d219/report.md)
and [evidence manifest](../../../../Zet_Tester/runs/ui-review-96fd-full-narrative/2026-11-25T23-53-15-866Z-2c54d219/evidence/manifest.json).

### Image Generation Reconstruction workflow (2026-11-26, revision 96fd)

The selected completed candidate correctly exposed the Reconstruction action.
The configured `image-analysis:latest` role, source and prompt controls were
visible, and the analysis recovered from a temporary storage banner after the
prescribed waits and refresh. The first reconstructed candidate omitted the
gown. Universe-style continuation generated a gown image. Compare first showed
Permission denied while still marked RUNNING; its report later settled to
COMPLETE with two major findings, and the live view reached READY without
resubmitting. One finding was selected and one Draft correction rendered with
the baseline as its ordered input. The corrected candidate restored the gown
and was reviewed at desktop and tablet landscape. Luna ranking and ranking-based
selection were not part of this Image Generation case's Compare and Correct
acceptance. The tester's extra attempt to invoke `Review latest` targeted a
Recent Renders full-screen preview, not Luna ranking. Direct dashboard
follow-up selected the corrected draft in Slot 4 and verified persistence after
reload; no lock or Inventory publication was made. A separate direct dashboard
inspection confirmed the repeated Recent Renders accessible names, and a local
board-specific label fix is pending release verification.

The comparison write warning remains under observation. Read-only inspection
found the report directory and report file present with inherited Modify access
for Authenticated Users; no ACL changes were made. Do not classify it as an
access-control denial without reproducing the actual writer identity and
failing operation. Evidence: [initial Reconstruction report](../../../../Zet_Tester/runs/ui-review-96fd-reconstruction/2026-11-26T00-41-37-454Z-09b3dc96/report.md),
[resume report](../../../../Zet_Tester/runs/ui-review-96fd-reconstruction/2026-11-26T00-41-37-454Z-09b3dc96/resume-2026-11-26T01-21-49-509Z-a7a55f53/report.md),
and [completed comparison JSON](../../../../Zet_Library_Test/ZetTester/_state/ImageReconstruction/84737e290e7c4f80ac4f6f1e50a6d141/reports/f189bd908a534cea8c22da474ab25b5b/report.json).

### Costume Wizard and Dressing workflow (2026-11-26, revision 96fd)

The Costume Wizard produced and accepted a new outfit template, and its private
FRONT test render confirmed identity and most clothing details. The render did
not show the requested exposed midriff, and embroidery appeared on the blouse
as well as the lower panels. A fresh Costume Dressing FRONT batch also failed
those visual requirements. Template Improvement accepted three relevant edits,
but the compiled board prompt retained earlier embroidery-near-hem text and a
separate instruction to embroider the blouse. This is a prompt handoff defect
to resolve or explicitly explain before another render; no corrected batch was
submitted, and the existing baseline candidate remains intact and unlocked.

The wizard exposed one configured model (`codex:gpt-6-luna`) rather than
separate selectors for its substeps. Its draft and section readiness persisted
after reopening. The wizard had no section-level suggestion checkboxes. Costume
Wizard and Dressing were usable through the tested workflow, but keyboard/touch
confirmation of section-action targeting remains outstanding. The run's full
checkpoint and evidence details are in the [Costume workflow report](../../../../Zet_Tester/runs/ui-review-96fd-costume/2026-11-26T01-51-36-444Z-38d8ec08/report.md).
