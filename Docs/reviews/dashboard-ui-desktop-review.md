# Zet Dashboard UI Review — Desktop

## 1. Executive Summary

The desktop dashboard already has the correct product shape: a dense, service-backed workbench with persistent character/phase context, direct table selection, split-pane review screens, and workflow-specific actions. The review does not recommend a broad redesign.

The highest-risk issue is data loss during task switching. Story and scene editors autosave when changing top-level pages, but clicking another story or scene row replaces the editor without first saving or warning. Source Editor, Zine, and settings pages also have no dirty-state guard when leaving the page.

The next desktop release should prioritize:

1. Preserve or explicitly discard unsaved work before selection/context changes.
2. Repair the Local Image Review gallery, whose portrait images are visibly clipped to a thin top strip.
3. Make disabled controls visually disabled; later semantic color selectors currently override `button:disabled`.
4. Add safeguards and scope text to destructive batch/clear/invalidation operations.
5. Make row-driven workflows keyboard operable.
6. Align desktop breakpoints with each layout’s actual minimum width.
7. Correct the Zine page/spread sequence and the broken hidden-image fallback.

Phases 1–4 below are incremental. Phase 1 fixes correctness, state, accessibility, and shared-component defects. Phase 2 resolves workflow hierarchy and requires a few product decisions. Phase 3 standardizes visual conventions after those decisions. Phase 4 adds regression protection.

## 2. Product and Viewport Assumptions

- Desktop is the authoritative, fully functional Zet interface.
- The supplied desktop baseline is 1920 × 911, per `Docs/UI/README.md`.
- Zet is a high-information workbench for a technically experienced, frequent user. Dense tables, raw paths, JSON, logs, and explicit pipeline states are useful and should remain available.
- Existing backend behavior and terminology are preserved unless a finding identifies concrete user harm.
- The supported dashboard is `zet/web`; retired Streamlit and standalone Render Console surfaces are out of scope.
- Reusable workflow behavior remains behind `ZetApp`, services, repositories, and models. Recommendations that alter persistence, stage transitions, queue mutation, or autosave need architectural review.
- Desktop decisions should establish shared semantics that a later reduced iPad interface can reuse. No detailed iPad design is included here.

## 3. Screenshot and Source Coverage

### Screenshot coverage

Twenty supplied captures were inspected, each at 1920 × 911:

- `01-onboarding.png`
- `02-assets.png`
- `03-identity-keys.png`
- `04-auxiliary-resources.png`
- `05-phase-comparison.png`
- `06-costumes.png`
- `07-expressions.png`
- `08-stories.png`
- `09-scenes.png`
- `10-zine.png`
- `11-scene-builder.png`
- `12-manifest.png`
- `13-prompt-review.png`
- `14-render-review.png`
- `15-render-console.png`
- `16-local-image-review.png`
- `17-turnarounds.png`
- `19-local-image-config.png`
- `20-pipeline-controls.png`
- `21-template-editor.png`

The sequence skips `18-ai-controls.png`. AI Controls was reviewed from source only; its rendered layout, overflow, loading, and populated queue states need a new desktop baseline.

### Source and documentation coverage

- `zet/web/templates/index.html`: all desktop pages, controls, forms, tables, dialogs, and empty-state markup.
- `zet/web/static/zet.css`: layout grids, scroll constraints, action colors, image viewers, breakpoints, and responsive rules.
- `zet/web/static/zet.js`: page activation, selection, editor save behavior, action enablement, dialogs, queue/review navigation, and rendering.
- `zet/web/app.py` and `zet/web/pipeline_controls_router.py`: route/API surface and service boundaries where UI recommendations may affect behavior.
- `Scripts/capture-dashboard-ui.mjs` and `package.json`: current capture process and viewport set.
- `tests/test_web_app.py`, `tests/test_zine_web.py`, and related web/service tests: current regression scope.
- `Docs/UI/README.md`, `Docs/Old/Dashboard_Functionality_and_UI_Direction.md`, and `Docs/Old/FastAPI_Dashboard_Migration_Plan.md`: desktop intent, service boundary, and the “one click should do one predictable thing” direction.

### Evidence limitations

- Captures represent one live data set and one desktop size. Loading, server error, focus, confirmation, and intermediate mutation states are primarily code evidence.
- The screenshot runner captures the current viewport only and does not assert layout, accessibility, state, or image completeness.
- Keyboard tab order, screen-reader announcements, browser zoom, and widths below 1920 require runtime verification.

## 4. Highest-Priority Desktop Findings

| ID | Severity | Viewport | Screen or workflow | Finding | Evidence | User impact | Recommendation | Effort | Dependencies | Confidence |
|---|---|---|---|---|---|---|---|---|---|---|
| D-01 | Critical | Desktop | Stories, Scenes; also Source Editor/Zine/settings navigation | Switching a story or scene row replaces unsaved editor text. Only top-level page navigation calls the autosave path; row selection loads another document directly. Other editors have no dirty-state leave guard. | `08-stories.png`, `09-scenes.png`; `zet/web/static/zet.js:1559`, `:1585`, `:2340`, `:2778`, `:3053`, `:1614` | A primary editing workflow can silently lose work. | Track dirty state. Before row, story, character/phase, or page changes, save and block on failure, or ask to Save/Discard/Cancel. Do not silently overwrite. | Medium | Product choice on autosave versus explicit prompt; persistence/API review | High — code-confirmed; screenshot confirms adjacent row/editor workflow |
| D-02 | High | Desktop 1920×911 | Local Image Review | Portrait renders are clipped to a thin strip at the top of tall dark cards; most of each image is unavailable for comparison. | `16-local-image-review.png`; source images are 640×800; nested constrained grids at `zet/web/static/zet.css:1364–1418` | The main purpose of the review screen—visually comparing outputs—is unreliable. | Give gallery cards an explicit preview area/aspect strategy, let images render fully with `object-fit: contain`, and avoid shrinking the image track inside the constrained pane. | Small | CSS only; verify with portrait, landscape, and mixed sets | High — screenshot, source, and source-image dimensions |
| D-03 | High | Desktop | Manifest, Render Review, Source Editor, all workflows | Disabled controls retain active green, blue, purple, or red fills because semantic selectors occur after and override `button:disabled`. | `12-manifest.png`, `14-render-review.png`, `21-template-editor.png`; `zet/web/static/zet.css:155`, `:495–560`; JS correctly disables empty-state actions at `zet/web/static/zet.js:5111`, `:6629` | Empty states look actionable; users cannot reliably distinguish unavailable transitions. | Put the disabled rule after semantic action rules or use a higher-specificity shared disabled selector; retain cursor and add non-color cues. | Small | Shared CSS; visual regression across every action type | High — screenshot + code |
| D-04 | High | Desktop | Local Image Review, Source Editor, AI Controls | Destructive operations have insufficient scope/confirmation: Local Image Review “Clear” immediately deletes all images for the task; Source Editor prechecks clearing condensed prompts and local renders on recompile; AI cleanup/stop actions run directly. | `16-local-image-review.png`, `21-template-editor.png`; `index.html:1028`, `:1370`, `:1139`; `zet.js:4938`, `:6370`, `:7168` | Accidental clicks can remove review artifacts or alter worker state; recovery may require costly regeneration. | State the target/count, default invalidation off, confirm destructive actions, and report what changed. Keep single-item fail/promote actions fast where scope is already explicit. | Medium | Product approval; service response may need counts/preview data | High — code-confirmed |
| D-05 | High | Desktop | Pipeline Controls batch reset | The batch reset is below the fold, acts immediately, and has no impact preview or confirmation, including when “Include locked assets” is enabled. | `20-pipeline-controls.png`; `index.html:1332–1351`; `zet.js:5925` | A broad stage transition can be launched without seeing affected assets, especially after scrolling past the context table. | Add a preview/dry-run count, explicit affected pipeline/locked scope, and confirmation before POST. Keep results visible beside the control. | Medium | Backend/service support for preview is preferable; architectural review required | High — code-confirmed; screenshot confirms action is outside initial viewport |
| D-06 | High | Desktop | Assets, Stories, Scenes, Prompt Inspection, Render Console, Manifest, Turnarounds, other tables | Selection rows are click-only `<tr>` elements with no focusability, role, keyboard handler, or current-selection semantics. | `index.html` table markup; repeated `row.addEventListener("click", ...)` including `zet.js:1333`, `:2340`, `:2778`, `:4658`, `:5982`, `:6615`; no row key handlers | Keyboard users cannot enter the primary task-selection path; screen readers do not receive selection state. | Use a real button/link in the identifying cell, or implement a keyboard list/grid pattern with roving focus and `aria-selected`. Prefer native controls. | Medium | Shared row-selection helper; accessibility regression tests | High — code-confirmed |
| D-07 | High | Desktop | Scene Builder dialogs | The three custom modal overlays are plain `div`s without `role="dialog"`, `aria-modal`, labelled relationships, focus entry/return, focus trap, or consistent Escape handling. | `index.html:684–752`; `zet.js:3472`, `:3909`, `:4204`; only toolbar/fullscreen Escape paths exist | Keyboard and screen-reader users can lose context or interact behind the modal during a primary builder workflow. | Replace with native `<dialog>` or implement complete dialog behavior; focus the first useful control and restore the trigger on close. | Medium | Browser behavior verification; no backend change | High — code-confirmed |
| D-08 | High | Desktop 1001–1540 px | Scene, Turnarounds, review/split layouts | Responsive collapse occurs only at 1000 px, but grid minimums exceed common desktop widths. Turnarounds requires roughly 1500 px before gaps; Scenes roughly 1240 px before gaps/padding. | `zet/web/static/zet.css:630–650`, `:1422`, `:1979`; only `@media (max-width:1000px)` collapses these layouts | 1280/1366/1440 desktop windows can horizontally clip or force awkward page overflow. | Set component-specific breakpoints based on actual minimums; preserve desktop density with resizable/two-column fallbacks before a one-column stack. | Medium | Runtime checks at 1280, 1366, 1440, 1600 | High — code-confirmed; runtime dimensions pending |
| D-09 | High | Desktop | Zine Maker | The two-column DOM/grid sequence visually misgroups Front, pages, and spread toggles: “Use Page 1…” appears under Front; later pairs alternate alignment. | `10-zine.png`; `index.html:656–668`; `zet.css:1834` | Users can assign scenes or spread flags to the wrong page pair. | Group explicit units: Front, Pages 1–2 + spread toggle, Pages 3–4 + toggle, Pages 5–6 + toggle, Back. Keep page order top-to-bottom. | Small | CSS/HTML only; preserve payload IDs | High — screenshot + code |
| D-10 | Medium | Desktop | Auxiliary Resources, Render Console | Images marked `hidden` still render as broken-image alt text because `.image-preview { display:block }` overrides the hidden presentation. | `04-auxiliary-resources.png`, `15-render-console.png`; `index.html:325`, `:972`; `zet.css:1671` | Empty and paste states look broken and add unexplained rows. | Add a shared `[hidden] { display:none !important; }` or targeted `.image-preview[hidden]`, then test all hidden panels. | Small | Shared CSS; audit hidden custom components | High — screenshot + code |
| D-11 | Medium | Desktop | All action bars/forms | Action meaning is inferred from ID substrings. This styles benign `Clear` and `Cancel` as destructive, `Refresh / Regenerate` as danger, and `Save Costume`/`Save Expression` as “new” brown because their IDs contain `create`. Dynamic Delete buttons remain neutral. | `03-identity-keys.png`, `04-auxiliary-resources.png`, `06-costumes.png`, `07-expressions.png`, `10-zine.png`; `zet.css:495–560` | Color no longer predicts consequence, so frequent users must reread every button. | Require explicit `primary-action`, `update-action`, `danger-action`, `navigation-action`, and neutral classes. Remove ID-substring styling after migration. | Small | Shared markup/CSS audit | High — screenshot + code |
| D-12 | Medium | Desktop | Stories | Story markdown validation appears directly under the New Story row. In the capture, “Title must be filled in” visually reads as an error for a populated New Story Title input rather than the selected story document. | `08-stories.png`; `index.html:525–535`; `zet.js:2352`, `:2524` | Users may edit the wrong field or think the validator is stale. | Move validation into the selected-story editor header and label it “Story markdown validation”; associate it with the editor. | Small | Presentation only | High — screenshot + code |
| D-13 | Medium | Desktop | Prompt Inspection, Render Console, Local Image Review | Narrow task lists force long ask IDs into clipped, indistinguishable single-line cells. Global table cells use `white-space: nowrap`. | `13-prompt-review.png`, `15-render-console.png`; `zet.css:364–376`; fixed 260 px sidebars at `:630`, `:1356` | Similar jobs cannot be distinguished without selecting each row or horizontal scrolling. | Display a concise task label plus status/time; preserve full ID in a secondary line/title/copy action. Allow wrapping in task-list cells. | Small | May need existing task metadata only | High — screenshot + code |
| D-14 | Medium | Desktop | Scenes, Identity Keys, Assets, Zine | Several labels obscure the action or state: “Scene” means Save Scene; “List” clears the identity editor; “Status” is a view mode; “Refresh / Regenerate” conflates reload with output replacement. | `02-assets.png`, `03-identity-keys.png`, `09-scenes.png`, `10-zine.png`; corresponding IDs in `index.html` | Extra interpretation slows repeated use and increases transition mistakes. | Use verb-object labels: Save Scene, Back to List/New Identity Key, Show Status/Show Locked Image, Regenerate Print Layout. | Small | Confirm exact regenerate side effects | High — screenshot + code |
| D-15 | Medium | Desktop | Scene Builder | Many labels literally end in ellipses and the existing help dictionary is not exposed by `builderCaption`; visible examples include gaze, movement, motion cue, focal point, and element override. | `11-scene-builder.png`; `zet.js:795`, `:3629`, `:3657–3663`, `:3725` | Expert users still cannot tell accepted values or the full meaning of dense fields. | Use short complete labels and restore an adjacent, keyboard-accessible help affordance or persistent concise help text. | Small | Content pass; no data model change | High — screenshot + code |
| D-16 | Medium | Desktop | All asynchronous workflows | Loading, success, and error messages are not live regions; controls lack `aria-busy`. A `success` class is emitted but has no CSS definition. | Message containers throughout `index.html`; `zet.js:552–678`; `zet.css:569–590` has info/error/warning only | Screen-reader users miss completion/failure; sighted feedback changes styling unpredictably. | Add a shared status component with `role="status"`/`aria-live`, alert semantics for blocking errors, busy state, and defined success styling. | Small | Shared component convention | High — code-confirmed |
| D-17 | Medium | Desktop | Image viewers/fullscreen | Most image viewers open fullscreen only by mouse click. Images are not focusable controls; the fullscreen overlay has no labelled Close button. | `zet.js:833`, `:6952–7009`; `index.html` image viewers. Only Phase Comparison boxes implement arrow-key behavior. | Keyboard users cannot inspect images, and Escape/click behavior is undiscoverable. | Wrap images in buttons or make explicit “Open full size” controls; add a Close button, focus management, and return focus. | Medium | Shared image-viewer helper | High — code-confirmed |
| D-18 | Medium | Desktop | Manifest, Render Review, Template Editor, empty tables | Empty pages show large work areas and blank dark `pre` bars without a clear explanation or next step; tables have no empty row. Disabled controls look active because of D-03. | `12-manifest.png`, `14-render-review.png`, `21-template-editor.png`; clear functions in `zet.js:5111`, `:6629` | Users cannot distinguish “nothing queued,” “not loaded,” and “select something.” | Use explicit empty-state text in each pane/table, hide irrelevant detail blocks, and identify the upstream action that creates work. | Small | D-03 first | High — screenshot + code |
| D-19 | Medium | Desktop 1920×911 | Global header/navigation | The 80 px branded header plus navigation consumes about 132 px before page content. The active Character Assets subpage is not shown in the select because its value resets to blank. | All captures; `zet.css:25–99`, `:180–233`; `zet.js:1637` | Less vertical room remains for images/editors; subpage location is carried only by the page heading. | Reduce the header height after workflow fixes and let the asset menu display the active subpage while retaining the Character Assets group identity. | Medium | Phase 3; retain character/phase controls | High — screenshot + code |
| D-20 | Medium | Desktop | Stories/Scenes/Source Editor | Long editors live inside independently scrolling panels and their action headers are not sticky. Save/validation controls scroll away during long edits. | `08-stories.png`, `09-scenes.png`, `21-template-editor.png`; `zet.css:656–679`, `:1186` | Frequent save/status checks require returning to the top of a nested pane. | Keep the editor toolbar/validation summary sticky within its pane; avoid adding another page-level scroll. | Small | Runtime scroll verification | Medium — code + initial screenshot; long-scroll behavior to verify |
| D-21 | Medium | Desktop | Image Config | Numeric settings omit units/ranges in visible labels, the Save action is visually detached above the panels, and the Zines column is mostly empty while image-generation fields scroll below the fold. | `19-local-image-config.png`; `index.html:1224–1310` | Configuration is harder to validate and save confidence is low. | Show units/help beside values, place a sticky page-level save bar with dirty/saved state, and use a denser balanced layout without hiding fields. | Small | Confirm units from service/config documentation | High — screenshot + code |
| D-22 | Medium | Desktop | Toolbar and menus | The To Do and Controls icon buttons rely on glyph/title text rather than robust accessible names. The popup menu exposes expanded state but no menu relationship or focus movement. | All captures; `index.html:57–65`; `zet.js:1749–1758` | Icons are ambiguous and menu keyboard behavior is incomplete. | Add `aria-label`, `aria-controls`, focus-on-open/return-on-close, and Escape/arrow behavior appropriate to the chosen disclosure pattern. | Small | Shared navigation component | High — code-confirmed |
| D-23 | Low | Desktop | Assets, config, pipeline tables | Raw snake_case headings and dense unformatted timestamps are inconsistent with the otherwise human-readable interface. | `02-assets.png`, `20-pipeline-controls.png`; table headings in `index.html` | Scan speed is reduced, especially across ten-column tables. | Render readable labels and compact local timestamps while keeping raw values available in title/detail/copy affordances. | Small | Confirm timezone display | High — screenshot + code |
| D-24 | Low | Desktop | Onboarding, Costumes, Expressions, Pipeline Controls | Several sparse pages use large split panels or a narrow half-width table despite abundant desktop space, while the longer content falls below the fold. | `01-onboarding.png`, `06-costumes.png`, `07-expressions.png`, `20-pipeline-controls.png` | Desktop space is not consistently allocated to the active task. | After correctness work, set content-appropriate max widths and rebalance panel proportions; do not convert technical lists into card grids. | Small | Phase 3 only | High — screenshot-confirmed |

## 5. Desktop Findings by Category

### Confirmed from screenshots and code

- **State and action semantics:** D-03, D-10, D-11, D-12, D-14, and D-18 are visible in the supplied captures and trace to shared CSS/markup/JavaScript.
- **Layout correctness:** D-02 and D-09 directly prevent reliable image/page review. D-13 and D-20 create repeated friction in narrow task lists and long editors.
- **Information hierarchy:** D-19, D-21, D-23, and D-24 show inconsistent allocation of high-value desktop space.
- **Form clarity:** D-12, D-14, D-15, and D-21 show validation, label, and unit ambiguity rather than merely stylistic differences.

### Confirmed from code only

- **Data preservation:** D-01. `selectStory` and `selectScene` load a different document without the save-before-navigation path. Runtime should verify the exact reproduction, but the overwrite path is unambiguous.
- **Destructive scope:** D-04 and D-05. Clear/invalidation/reset actions invoke mutation endpoints without a confirmation or preview.
- **Keyboard and modal accessibility:** D-06, D-07, D-16, D-17, and D-22.
- **Intermediate desktop widths:** D-08. The CSS constraints are confirmed; exact browser overflow at each target width still needs screenshot/runtime verification.

### Confirmed from screenshots only

- No high-priority finding relies on screenshot evidence alone. Visual findings were traced to source where possible.
- D-24’s degree of wasted space is screenshot evidence; its correction should remain low priority and be validated after workflow changes.

### Requires runtime verification

- Whether focus indicators remain sufficiently visible on every browser/control after semantic colors are corrected.
- Exact tab order through split panes and dynamically inserted Scene Builder fields.
- Browser zoom at 125%, 150%, and 200%.
- 1280, 1366, 1440, and 1600 px layout behavior, especially Scenes and Turnarounds.
- Screen-reader announcement timing for loading, validation, and mutation outcomes.
- Scroll containment and sticky-toolbar behavior on very long story, scene, prompt, path, log, and JSON content.
- Confirmation focus return and interruption behavior.
- Populated AI Controls layout, because `18-ai-controls.png` is absent.

### Functional usability and workflow clarity

- Preserve selection while mutations refresh data. Existing Assets behavior already attempts this and should become the convention.
- A task-switch action must have one predictable result: save, discard after confirmation, or cancel. Silent replacement is unacceptable.
- Destructive controls must identify scope: one image, all local images for the selected ask, harvested queue items, locked assets, or an entire pipeline.
- Action bars should separate task transitions from editing controls. “Save Scene” and “Stage Render” should not read like peer tabs.

### Layout, resizing, overflow, and scrolling

- Retain split panes on wide desktop; they are appropriate for Zet.
- Replace a single global 1000 px breakpoint with layout-specific thresholds.
- Keep list, editor, and detail panes independently scrollable where simultaneous context is useful, but keep the active toolbar/status visible in each pane.
- Do not make every page full width by default. Sparse creation forms should use content-sized regions; dense tables and image comparisons should use available width.

### Navigation and task switching

- Keep top-level workflow navigation visible.
- Let the Character Assets selector show the active subpage instead of resetting to its group placeholder.
- Later shortcut work should build on accessible native controls: Previous/Next task, focus task list, Save, and open full-size image are strong desktop shortcut candidates after correctness.

### Forms, validation, and input affordances

- Put validation adjacent to the object it validates and name the object explicitly.
- Use dirty/saving/saved/error status for text and settings editors.
- Show units, valid range, and consequence for technical numeric settings.
- Preserve native file input capability, but hide the separate broken preview element until a valid blob/source exists.

### Accessibility

- Row selection, modal interaction, image zoom, toolbar disclosures, and asynchronous announcements are the priority accessibility defects.
- Native buttons, links, `<dialog>`, labels, and status regions should be reused before introducing custom widget behavior.
- Status must not be color-only. Pair color with text/icon and preserve a visible focus ring.

### Visual refinement

- The existing palette can remain, but action semantics must be class-driven.
- Raw technical data remains appropriate; improve headings and timestamp formatting without hiding the original values.
- Reduce header height and unused panel space only after Phase 1/2 behavior is stable.

## 6. Desktop Phase Plan

### Phase 1: Desktop Correctness and Consistency

**Goal**

Eliminate data-loss paths, broken rendering, misleading disabled states, destructive-action ambiguity, keyboard blockers, and fragile desktop resizing.

**Included findings**

D-01 through D-12, D-16 through D-18, and the correctness portion of D-22.

**Files or components likely affected**

- `zet/web/static/zet.js`
  - page/selection lifecycle
  - story/scene/zine/source-editor dirty state
  - row selection rendering
  - Local Image Review gallery
  - destructive action handlers
  - Scene Builder modal open/close
  - shared message/status behavior
- `zet/web/static/zet.css`
  - disabled precedence
  - hidden image behavior
  - action classes
  - gallery sizing
  - layout-specific breakpoints
  - focus and status states
- `zet/web/templates/index.html`
  - dialog semantics
  - status/live-region markup
  - explicit action classes
  - empty-state content
  - Zine slot grouping
- `zet/web/app.py` or focused backend services only if impact previews/counts are required for D-04/D-05.

**Dependencies**

- User approval of the save-on-switch behavior in Open Decision O-01.
- Architectural review before adding batch-preview or autosave service calls.
- Existing IDs/payload keys for Zine slots must remain stable.

**Acceptance criteria**

- Editing a story or scene and choosing another row cannot silently lose text.
- Leaving Source Editor, Zine, Image Config, or other dirty forms warns or explicitly preserves work according to O-01.
- All disabled actions are visually and semantically disabled in empty and loading states.
- Every image in Local Image Review is fully visible at a useful size; portrait and landscape images can be opened full size.
- Hidden previews do not show broken alt rows.
- Zine controls read in page order and each spread toggle is visually bound to its page pair.
- Clear, invalidate, stop/archive, and batch reset actions state scope and require confirmation where approved.
- All primary selection tables are operable with keyboard and expose selection.
- Scene Builder dialogs trap/restore focus and close predictably.
- Scenes and Turnarounds do not horizontally clip at approved desktop widths.

**Verification steps**

1. Use seeded documents to edit without saving, then switch rows, stories, character/phase, and top-level pages.
2. Capture empty, one-item, loading, validation-error, and populated states.
3. Load mixed 640×800, 800×640, square, and very large local images.
4. Tab through each table-driven workflow and select a row with Enter/Space.
5. Open/close each Scene Builder dialog by keyboard and verify focus return.
6. Exercise destructive confirmations, cancel them, then confirm and verify reported scope.
7. Capture 1920×911, 1600×900, 1440×900, 1366×768, 1280×800, and 1920×768.
8. Run existing web/API tests and the new browser tests from Phase 4.

**Explicit exclusions**

- No navigation redesign.
- No iPad layout work.
- No change to pipeline stage semantics or data models.
- No conversion of dense tables into card grids.
- No general typography/palette polish beyond what correctness requires.

### Phase 2: Desktop Workflow and Information Hierarchy

**Goal**

Make current selection, validation, next action, and destructive scope obvious while reducing repeated navigation and task-switching friction.

**Included findings**

D-13 through D-15, D-19 through D-22, plus confirmed product choices from O-01 through O-05.

**Files or components likely affected**

- `index.html`: action labels, grouping, editor toolbars, settings help.
- `zet.js`: concise task labels, dirty/saved status, sticky toolbar state, active subpage value, confirmation copy.
- `zet.css`: sticky pane headers, task-list wrapping, balanced settings/forms, compact header structure.
- Backend service/API only for batch previews, undo/retry metadata, or richer task summaries.

**Dependencies**

- Phase 1 shared state/action conventions.
- User approval for autosave behavior, batch preview/confirmation, and regeneration language.
- Architectural review for any new preview/undo endpoint.

**Acceptance criteria**

- Each screen identifies current item, current state, and primary next action without relying on button color.
- Task lists remain distinguishable with long IDs and similar names.
- Story/scene validation is clearly associated with the selected document.
- Scene Builder labels are complete and help is keyboard accessible.
- Source Editor and Image Config show dirty/saving/saved/error state.
- Action toolbars remain visible during long edits.
- The active Character Assets subpage remains visible in navigation.
- Technical settings show units and consequences.

**Verification steps**

1. Conduct task walkthroughs: select asset → inspect prompt → render → review; story → scene → builder → render; zine fill → edit → regenerate.
2. Test with maximum-length story/scene/task names and Windows paths.
3. Verify toolbar behavior with long documents and 768 px-high windows.
4. Validate that action text remains correct in loading, empty, selected, and completed states.
5. Confirm no recommendation moved business logic into `zet/web`.

**Explicit exclusions**

- No renaming of established domain terms such as asset, manifest, LOCKED, RENDER, or REGENERATE.
- No hiding expert controls.
- No new frontend framework or design-system dependency.
- No iPad capability reduction decisions.

### Phase 3: Desktop Visual Refinement

**Goal**

Apply a compact, consistent desktop visual language after behavior and hierarchy are settled.

**Included findings**

D-19, D-23, D-24, and final polish arising from D-03/D-11/D-16.

**Files or components likely affected**

- Primarily `zet/web/static/zet.css`.
- Small semantic class/label changes in `index.html`.
- Formatting helpers in `zet.js` for timestamps and display labels.

**Dependencies**

- Phase 1 action/state classes.
- Phase 2 toolbar and navigation grouping.
- Approved desktop baselines.

**Acceptance criteria**

- Header/navigation uses less vertical space without wrapping at 1280 px.
- Spacing uses a small consistent scale for pane padding, row height, action gaps, and section separation.
- Heading hierarchy is consistent across page, panel, and subsection levels.
- Selected, focused, disabled, loading, warning, success, and destructive states are visually distinct.
- Tables use readable labels and compact timestamps while retaining raw values on demand.
- Sparse forms use a sensible maximum width; dense workflows continue to use the viewport.
- Borders and dark image/code surfaces are used consistently, without decorative gradients beyond existing brand treatment.

**Verification steps**

1. Compare all desktop pages side-by-side at 1920×911 and 1366×768.
2. Verify 200% zoom and Windows high-contrast/forced-colors behavior.
3. Check contrast for all text/status/action combinations.
4. Review vertical rhythm and alignment with loading, error, long-name, and empty states.

**Explicit exclusions**

- No wholesale rebrand.
- No decorative card conversion.
- No major animation.
- No phone/iPad visual redesign.

### Phase 4: Desktop Regression Protection

**Goal**

Make desktop correctness, workflow state, keyboard operation, and visual conventions testable and repeatable.

**Included findings**

All desktop findings, with first priority on D-01 through D-12 and D-16 through D-18.

**Files or components likely affected**

- `Scripts/capture-dashboard-ui.mjs` or a separate Playwright test runner.
- `package.json` scripts.
- New browser test files under the repository’s established test location.
- Existing `tests/test_web_app.py`, `tests/test_zine_web.py`, and service tests for API contracts.
- Screenshot baselines under an approved test-artifact location; keep documentation captures separate if possible.

**Dependencies**

- Stable Phase 1/2 behavior.
- Deterministic seeded fixture data.
- Approval before adding an accessibility-test dependency; keyboard/role assertions can start with existing Playwright.

**Acceptance criteria**

- Tests reproduce and prevent unsaved-switch data loss.
- Disabled appearance and actual `disabled` state are both asserted.
- Local image cards display the complete image bounds.
- Empty/load/error/validation/destructive-confirmation states have deterministic coverage.
- Keyboard tests select tasks, operate dialogs, open/close images, and return focus.
- Visual baselines cover the authoritative 1920×911 desktop and smaller desktop widths.
- The capture set includes AI Controls and fails when a discovered page is not captured.
- Existing backend/service tests continue to pass.

**Verification steps**

1. Run Python tests with `python3`.
2. Run Playwright workflow/accessibility tests.
3. Generate and inspect baseline diffs at every approved desktop size.
4. Verify no screenshot is captured before images/fonts/async page state are settled.
5. Confirm browser tests fail when a control appears enabled in an empty state or a layout overflows horizontally.

**Explicit exclusions**

- Phase 4 does not redesign UI.
- Documentation screenshots are not a substitute for deterministic assertions.
- Do not add a large UI framework.
- iPad and phone regression suites remain separate later phases.

## 7. Desktop Design Conventions to Standardize

### Action semantics

| Role | Visual/interaction convention | Examples |
|---|---|---|
| Primary completion | Green; one dominant completion action per task region | Save Story, Save Scene, Save References |
| Update/execute | Blue; reruns or advances work | Generate, Refresh, Recompile, Promote |
| Create | Brown only when creating a new object | New Character, Add Story, Create Identity Key |
| Navigation/view | Purple/neutral; no data mutation | Previous, Next, Open Editor, Show Image |
| Destructive | Red plus explicit scope; confirmation for broad or hard-to-recover actions | Delete Story, Clear 19 Local Images, Reset Pipeline |
| Disabled | Neutral gray, reduced emphasis, `disabled`, and unavailable text when useful | No selected task, no candidate image |

Use explicit classes. Do not infer semantics from ID substrings.

### Selection and focus

- One selected item per list; use text/outline plus background, not color alone.
- Selection must be reachable and operable by keyboard.
- After refresh/mutation, preserve selection when the item still exists; otherwise select the nearest predictable item and announce it.
- Focus remains on the initiating control unless a modal/detail transition intentionally moves it.

### Pane and toolbar behavior

- Wide desktop: list + work area + context/actions when simultaneous comparison is useful.
- Keep the current item/action toolbar sticky inside long panes.
- Use independent pane scrolling only where it preserves context; avoid nested scroll regions without a visible reason.
- Component-specific breakpoints should be based on actual minimum content width.

### Status and validation

- Every async action supports: idle, loading, success, warning, error, and disabled/unavailable.
- Status messages use shared markup, styling, and live-region behavior.
- Validation names the object and sits adjacent to the affected editor/form.
- Dirty/saving/saved state is persistent and separate from repository-level “Uncommitted story changes.”

### Tables and technical content

- Preserve dense tables and raw technical detail.
- Humanize display headings and timestamps; retain raw values through detail/title/copy.
- Long identifiers wrap or use a concise primary label plus full secondary value.
- Empty tables contain an explanatory row rather than a blank body.
- Paths, prompts, JSON, logs, and errors wrap or scroll within their own bounded region and remain copyable.

### Images

- Preview containers declare the intended fit; portrait, landscape, square, and very wide turnarounds remain fully inspectable.
- Empty, loading, missing, and failed-image states are distinct.
- Full-size viewing uses a labelled native control, Close button, Escape, focus entry, and focus return.

### Forms

- Labels are complete, associated, and do not end with unexplained ellipses.
- Numeric controls show units/range/consequence.
- Broad destructive checkboxes default off.
- Save bars show dirty/saving/saved/error state and remain visible for long forms.

### Desktop decisions that affect later iPad design

- Shared action roles, status semantics, terminology, and confirmation scope should be finalized on desktop first.
- Dirty-state and selection lifecycle should be shared behavior, not recreated in an iPad presentation layer.
- Native keyboard-accessible controls also provide a stronger base for touch adaptation.
- Desktop split panes should not be encoded as a universal responsive stack; later iPad work should choose reduced sequential workflows.

## 8. iPad Capability Matrix

Deferred. This desktop-only review does not classify iPad workflows. Phase 5 should begin only after desktop action semantics, dirty-state behavior, and status conventions are approved.

## 9. iPad Responsive Strategy

Deferred. The only desktop prerequisite recorded here is to avoid treating the 1000 px desktop collapse as the iPad design.

## 10. Phone Critical-Failure Notes

Not assessed. Phone captures were outside the assigned desktop scope.

## 11. Testing and Regression Strategy

### Current protection

- Python tests exercise substantial API/service behavior.
- `Scripts/capture-dashboard-ui.mjs` discovers `main > section.page` elements and captures three viewport sizes.
- The capture runner does not seed state, assert UI behavior, verify image completeness, test keyboard access, or compare baselines.
- The missing `18-ai-controls.png` shows the need for a completeness assertion tied to discovered page names.

### Recommended browser test layers

1. **DOM/state tests**
   - Disabled and enabled rules.
   - Selection preservation.
   - Dirty-state transitions.
   - Empty/loading/error/success rendering.
   - Correct Zine field grouping.

2. **Critical workflow tests**
   - Story edit → switch story.
   - Scene edit → switch scene/story.
   - Source edit → navigate away/recompile with invalidation off/on.
   - Local images → generate → review → clear/cancel.
   - Manifest empty/populated → save.
   - Render Review empty/populated → promote/fail.
   - Pipeline reset preview → cancel/confirm.

3. **Keyboard/accessibility tests**
   - Tab order through global context, navigation, list, editor, and action pane.
   - Row selection with keyboard.
   - Dialog focus trap/return and Escape.
   - Image viewer open/close.
   - Accessible names for icon-only controls.
   - Live status/error announcements.

4. **Visual regression tests**
   - 1920×911 authoritative baseline for every desktop page.
   - 1600×900, 1440×900, 1366×768, 1280×800, and 1920×768.
   - At minimum: empty, populated, long-content, validation-error, disabled, loading, and modal states.
   - Mixed portrait/landscape/square images and very wide turnaround sheets.

### Recommended screenshot baselines

- Keep the existing 20 captures as review evidence, not as the only automated baseline.
- Add `18-ai-controls.png`.
- Add deterministic named states, for example:
  - `desktop-1920-assets-populated`
  - `desktop-1920-render-review-empty`
  - `desktop-1920-local-images-mixed-aspect`
  - `desktop-1366-scenes-long-names`
  - `desktop-1280-turnarounds-populated`
  - `desktop-1920-scene-builder-dialog`
  - `desktop-1920-source-editor-dirty`

### Existing tests to extend

- `tests/test_web_app.py`: retain API mutation and enablement prerequisites; add any batch-preview contract.
- `tests/test_zine_web.py`: preserve IDs/payload mapping while testing new visual grouping in browser tests.
- Service tests: cover mutation scope/counts if confirmation previews require new service responses.

## 12. Open Decisions Requiring User Approval

| Decision | Options | Recommendation | Why approval is required |
|---|---|---|---|
| O-01 Unsaved editor switching | Autosave before every switch; or Save/Discard/Cancel prompt | Autosave Story/Scene/Builder on row/page/context switch and block on failure; prompt for Source Editor, Zine, and settings | Changes persistence timing and user expectations |

Confirm: Autosave Story/Scene/Builder on row/page/context switch and block on failure; prompt for Source Editor, Zine, and settings

| O-02 Local image clear | Immediate; confirmation; recoverable trash | Confirm with selected task and image count; prefer recoverable move if backend supports it | Removes generated artifacts and may incur regeneration cost |

Confirm with selected task and image count. Recoverable trash or not out of scope.

| O-03 Source recompile invalidation | Default on; default off; separate action | Default off and state exactly which condensed/local artifacts will be invalidated | Current checked default removes review aids |

Remove Source Recompile button, not used.

| O-04 Batch pipeline reset | Immediate; confirmation; preview + confirmation | Preview affected/skipped/locked counts, then confirm | Broad pipeline and queue state transition; backend/service impact |

Confirm: Preview affected/skipped/locked counts, then confirm

| O-05 Regenerate/fail language | Keep combined labels; split reload vs regenerate | Separate pure refresh from output replacement and state the side effect | May reveal two distinct backend behaviors |

Regenerate is the term and the action to take. There isn't a "refresh" option- every fail state means the process has to go through the pipeline and compiler again.

| O-06 Header compaction | Keep 80 px brand; compact persistent header | Compact after Phases 1–2 while keeping context selectors always visible | Global visual/navigation change |

Confirm Compact after Phases 1–2 while keeping context selectors always visible

| O-07 Accessibility dependency | Playwright-only; add axe-core | Start with Playwright keyboard/role assertions; add axe-core only if dependency approval is granted | Repository instruction requires package approval when unavailable |

Confirm Start with Playwright keyboard/role assertions; add axe-core only if dependency approval is granted

## 13. Recommended Implementation Order

1. **D-01 data preservation** — approve O-01, implement dirty state and guarded task/context switching, and add tests first.
2. **Shared correctness CSS** — D-03 disabled precedence, D-10 hidden images, and D-11 explicit action classes.
3. **Primary visual workflow repair** — D-02 Local Image Review and D-09 Zine ordering.
4. **Destructive safeguards** — D-04/D-05 after O-02 through O-04 and architectural review.
5. **Accessibility foundations** — D-06 row selection, D-07 dialogs, D-16 live status, D-17 image controls, D-22 toolbar names/focus.
6. **Desktop resize correctness** — D-08 with 1280–1600 px baselines.
7. **Workflow hierarchy** — D-12 through D-15, D-18, D-20, and D-21.
8. **Desktop visual refinement** — D-19, D-23, and D-24.
9. **Regression suite completion** — deterministic screenshots, AI Controls baseline, keyboard checks, and critical workflow tests.
10. **Stop for desktop acceptance** before beginning iPad capability definition.
