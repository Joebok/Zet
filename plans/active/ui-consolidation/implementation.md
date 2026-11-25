# Implementation packets and validation

This is the approved implementation breakdown for the [brief](../ui-consolidation-and-workflow-alignment.md) and [design](design.md). Work is sequential and uses one agent. Each packet owns one bounded result. Progress and actual validation are recorded below as packets complete.

New filenames below are proposed modules, not existing APIs. Prefer extending the named existing owner when it provides the needed behavior. Add a module only when it has a clear reusable responsibility. Do not add a UI framework, icon package, state library, or test dependency.

## Delivery order

| Wave | Packets | Reviewable outcome |
| --- | --- | --- |
| 1. Defects | WP01-WP04 | Compare loads, lettering confirmation preserves selection integrity, the editor can always exit safely, and empty imports stop claiming to load. |
| 2. Shared foundations | WP05-WP11 | Shared actions/tokens, operation status, review controls, viewer, image acquisition, proposal review and expandable production shell. |
| 3. Production migrations | WP12-WP20 | Character, Minor Character, Narrative, Image Generation and wizards follow the agreed flow and prompt-readiness rules. |
| 4. Site completion | WP21-WP31 | Inventory, derived images, finishing, Zines, navigation, settings, editors, Queue and diagnostics use the same conventions. |
| 5. Acceptance | WP32 | Existing regressions pass and a corrected before/after evidence package demonstrates desktop and landscape tablet usability. |

Review a Character board as the first shared-layout pilot before migrating the other three main workspace families. Keep existing APIs/services behind adapters throughout. Do not switch all pages to an unvalidated generic controller in one change.

## Validation commands and boundaries

Commands below are planned validation, not results from this planning task. Run them from the Zet root on the implementation checkout.

- **J:** `node --check` on each changed JavaScript module, for example `node --check zet/web/static/candidate_board_component.js`. Apply the same syntax check to any new module before browser loading it.
- **P:** First verify Python 3 with `py -3 -c "import sys; assert sys.version_info.major == 3"`, then parse changed Python using that interpreter, for example `py -3 -c "import ast,pathlib; ast.parse(pathlib.Path('zet/services/narrative_scene_text_service.py').read_text(encoding='utf-8'))"`.
- **C:** `npm.cmd run test:e2e -- --grep "character-to-costume|Character candidate board"`.
- **M:** `npm.cmd run test:e2e -- --grep "Minor Character"`. This existing journey covers collection management; it is not complete Style/render coverage. Use disposable prepared checks for those gaps.
- **N:** `npm.cmd run test:e2e -- --grep "narrative interview|Narrative finishes"`.
- **G:** `npm.cmd run test:e2e -- --grep "Image Generation"`.
- **W:** `npm.cmd run test:e2e -- --grep "Character Wizard|Costume Wizard"`.
- **L:** `npm.cmd run test:e2e -- --grep "Inventory image edit|Character template editor|universe style and species"`.
- **F:** `npm.cmd run test:e2e -- --grep "Narrative animation|Narrative zine|Narrative finishes"`.
- **Q:** `npm.cmd run test:e2e -- --grep "unified AI queue|Character recovery"`.
- **ALL:** `npm.cmd run test:e2e` and `git diff --check` at final acceptance. Repair assertions/selectors in existing scenarios only as needed to preserve their approved task purpose.

Each packet also requires a disposable UI/service check or manual inspection for its named acceptance state. Reuse the existing isolated fixture from `tests/e2e/server.py` and the current Playwright dependency. Keep temporary scripts/results under `.codex_tmp/ui-consolidation/` or a dedicated ignored evidence run; record their actual commands and results in the packet log. Do not create permanent scenarios or a snapshot suite by default.

A Test release capture must verify its actual revision/boot against `/api/health`. An isolated fixture check must be labeled as such; it cannot claim to be a new live workflow run. No deployment, production-library reset, real process restart, external issue submission or live AI work is needed for the prepared checks. Run live pipeline verification only when separately requested.

## Implementation progress

Updated 2026-11-25. No permanent test scenarios were added; disposable specs were removed after use.

| Packet | State | Actual result and validation |
| --- | --- | --- |
| WP01 | Implemented | Compare now initializes its independent-side UI; each side and its image request reports failures locally. Legacy controls and listeners are removed. Disposable isolated browser check verified one aborted side leaves the other available without page errors. `node --check zet/web/static/zet.js`; `git diff --check` passed. |
| WP02 | Implemented and verified | Disposable isolated browser/API check seeded two completed candidates, finished lettering on the unlocked unselected candidate, verified the other candidate remained selected and locked with unchanged image bytes, and verified explicit selection of the second candidate was rejected. The actual scene-text save/preview/confirm endpoints and file repository were exercised; no AI services were called. |
| WP03 | Implemented and verified | Disposable browser check passed failed-confirm recovery, Save draft success with preview failure, Close/Escape exit and focus return. Earlier checks passed dirty discard/continue and failed-save recovery. Close explicitly restores the invoking control without scrolling it into view and restores page scroll. A failed confirmation now says the draft was saved and the finished image was not saved. JavaScript syntax and focused disposable browser/API check passed; temporary spec removed. Latest staged Test release includes the changes and passed the Narrative finishing scenario in the 20/20 approved suite. |
| WP04 | Implemented and verified | Empty source configuration clears Loading and shows configuration guidance; destination is labeled Import Candidates. Disposable isolated browser check verified the empty-source message. An isolated Markdown source imported through the real service and Narrative repository, created the scene with its three targets, and a repeat import returned the existing completed scene without changing its bytes. The fixture used a temporary library and was removed. |
| WP05 | Implemented | Added render-mode tokens and a common image-action role/order registry; Candidate Board Draft/Final/Upscale styles use the shared values. Updated the style guide. Syntax and diff checks passed; Character-to-costume and candidate-board safety passed (2/2). |
| WP06 | Implemented; response-loss checked in three workspaces | Added shared operation-state text rendering and wired Candidate Board feedback to it. Character, Minor Character, Narrative and Image Generation adapters refresh authoritative detail after action failures and label transport-loss outcomes as unknown. Disposable browser checks dropped successful mutation responses after server commit in Character, Narrative and Image Generation; each board refreshed to the committed state and showed Status unknown. The 20-scenario approved suite passed. Minor Character failure injection remains unexercised. |
| WP07 | Implemented | Review navigation/close stay in the header; zoom, decisions and feedback remain fixed above the scrolling advice rail. Full candidate identity has separate visible text and a Copy control. An initial regression against the existing heading assertion was corrected by retaining position and quality there. Character, Narrative and Image Generation runs passed after correction; latest Character subset passed (2/2). |
| WP08 | Implemented and verified | Shared zoom supports pointer pan/pinch and the full-screen viewer has zoom/reset controls and visible image-load failure. Disposable browser checks covered zoom/reset/Escape; Joe confirmed the physical tablet gesture check. |
| WP09 | Implemented foundation | Added a reusable Image Inventory picker and optional callback path in shared image-input controls. Disposable isolated browser check selected a mocked Inventory item successfully. Consumer adapters are still to be migrated in WP17-WP20 and WP31; no claim that all active inputs are unified yet. |
| WP10 | Implemented; stale-field conflict checked | Proposal acceptance checkboxes and small-choice radios are shared through `interview_proposals.js`; Minor Character and Narrative consume them. Existing Minor Character, Narrative interview and finishing scenarios passed (3/3). Disposable service checks rejected duplicate field proposals and missing decisions, accepted explicit rejection, and blocked stale values without writes. A disposable browser workflow verified the stale edit stays visible, the conflict message appears, and rejecting that proposal allows other proposals to apply. No permanent scenario was added. |
| WP11 | Implemented foundation | Added `production_workspace.js` and shared responsive shell styles in `zet.css`; per-scope explicit disclosure choices persist in session storage. Disposable Character profile check passed at 1920x1080 and 1133x610. |
| WP12 | Implemented pilot | Character asset container mounts the shell around existing preparation and results while preserving deterministic compilation. Character board regressions passed (2/2); disposable shell check passed at desktop and landscape viewport. Head-input picker migration remains in WP31. |
| WP13 | Implemented; landscape route check passed | Minor Character board places preparation in the shared expandable shell, with the board as the result surface. Fresh Zet_Tester Style and three official views completed, locked, published and survived refresh. A read-only 1133x610 route check activated Minor Characters without page errors or horizontal overflow. Prompt-current guard and private Style versus published view behavior remain service-owned. |
| WP14 | Implemented | Narrative target prompts now carry an effective-input digest. Detail reports ready/stale/unknown/missing, render rejects stale/unknown, manual Save Prompt adopts the current inputs, and late writers cannot replace text or auto-stage renders after input changes. Python/JavaScript syntax passed; approved N passed (2/2); disposable isolated API/browser check passed stale rejection, manual adoption, no render side effect and late-result fencing (1/1). No maintained scenario was added. |
| WP15 | Implemented | Narrative backdrop/subscene/assembly boards use the production shell; editable shared scene direction and target inputs stay on the board route, async message stays visible when preparation is closed, and assembly mode uses radios. Approved N passed (2/2); disposable 1133x610 check passed direct scene save, prompt-stale update, disclosure behavior and visible render action (1/1). `node --check zet/web/static/narrative.js` passed. Physical tablet behavior remains unverified. |
| WP16 | Implemented | Image Generation and Reconstruction use the production shell, short-choice radios, ordered Browse/Paste/Inventory inputs, named create/rename/conflict dialogs and visible scoped status. Reconstruction preparation opens while nested source/intent stays user-expandable; direct prompt rendering remains intact. Approved G passed 2/2 after correcting a disclosure interaction regression; disposable input/form/reconstruction check passed 1/1. `node --check zet/web/static/image_generation.js` passed. Physical tablet behavior remains unverified. |
| WP17 | Implemented | Character Wizard reference slots use shared Browse/Paste/Inventory controls; Inventory selections enter the established file upload and caption flow. Suggested replacements use accept checkboxes with explicit Save draft edits; closing draft edits saves them before exit, and unsubmitted intake edits require confirmation. Approved W passed 2/2; disposable 3-method acquisition passed 1/1; JavaScript syntax passed. |
| WP18 | Implemented | Costume Wizard references use shared Browse/Paste/Inventory; section suggestions use acceptance checkboxes and Save Draft; private test renders show draft revision and open in the shared zoom viewer; acceptance message points to Costume-Dressing. Approved W passed 2/2; disposable Inventory/viewer check passed 1/1; `node --check zet/web/static/zet.js` passed. Physical tablet behavior remains unverified. |
| WP19 | Implemented | Minor Character source settings keep Image Inventory selection and add shared Browse/Paste controls. New files enter Image Inventory only on explicit Import to Image Inventory and use; a rejected or canceled import leaves the previous source bound. Approved M passed 1/1; disposable paste/import/source bind and browse-preview check passed 1/1; JavaScript syntax passed. |
| WP20 | Implemented | Narrative scene elements retain their Inventory picker and now share Browse/Paste import controls. Import selects the new library asset in the draft element; Save element commits its asset ID, while closing leaves the scene unchanged. Approved N passed 2/2; disposable paste/import/save binding check passed 1/1; JavaScript syntax passed. |
| WP21 | Implemented | Inventory result counts and active filters remain visible when filter controls are collapsed; search text now has a removable chip, and long tags/filter labels wrap. Existing detail organization, replacement scope, and full-size viewing remain service/controller-owned. Approved L passed 3/3; disposable 1133x610 empty-search/chip clear/overflow check passed 1/1; `git diff --check` passed. |
| WP22 | Implemented | Identity Key source options now label Draft/Final; Overview workspace links have explicit accessible context; missing views on eligible Local Turnaround rows link to the source workspace. Compare side state/navigation is unchanged, full readiness still depends on eight views, and partial-sheet controls remain available. Approved Character workflow regression passed 1/1; disposable missing-view route and eight-view readiness checks passed 1/1 each; both changed scripts pass `node --check`; `git diff --check` passed. Disposable specs were removed. |
| WP23 | Implemented | Scene text uses labeled tail radios and direct percentage position/size fields alongside existing drag editing; animation transitions use labeled radio groups and zoom targets have direct coordinate fields alongside pointer/keyboard controls. Confirmed lettering and saved/exported animation contracts remain unchanged. Approved F passed 3/3; disposable 1133x610 geometry/save/close check passed 1/1; changed JavaScript modules pass `node --check`. An initial disposable assertion targeted the wrong request shape and was corrected; no application defect was found. |
| WP24 | Implemented | Zine slots now offer a finished-scene thumbnail/title picker, with source tags retained for direct edits. Overall required-slot progress and per-page-pair fill counts are visible; missing or unreadable page images report at their fields. Shared full-screen zoom remains on the print preview. Approved Zine journey passed 1/1; disposable landscape picker/preview/incomplete-required-slots check passed 1/1; `node --check zet/web/static/zet.js` and `git diff --check` passed. Disposable spec removed. |
| WP25 | Implemented; route check passed | Recent Renders uses shared thumbnail activity rows with separate Review latest and Open board actions. Harvest publishers attach the latest preview path to snapshots; legacy rows without it show an unavailable preview and retain the board route. Responsive shell navigation collapses into the section selector at the 1360px breakpoint and preserves view state. Approved Character and Narrative regressions passed sequentially, 2/2 each. A read-only 1133x610 Test route check activated Recent Renders without page errors or horizontal overflow. |
| WP26 | Implemented; route check passed | Universe creation and settings share clear style headings, local progress/error feedback and responsive action layouts. Settings requests are fenced so old responses cannot replace the current universe. Species load/save feedback preserves drafts on conflict; a failed catalog reload restores available Edit/Add actions. Approved L passed 3/3. Read-only 1133x610 Test checks activated Universes and Universe Settings without page errors or horizontal overflow. The focused conflict interactions were covered by existing scenario service checks; no settings were changed during this route check. |
| WP27 | Implemented | Template Editor now has an in-place current-character/phase source chooser, clear empty/loading/unavailable feedback, and keeps the previous draft open when a source switch fails. Manual copy and download report locally; narrow editor and diff layout remain readable. Approved L passed 3/3; disposable chooser/open/long-text/unavailable-source/manual-copy-rejection/master-conflict checks passed 3/3; JavaScript syntax and `git diff --check` passed. Disposable spec removed. |
| WP28 | Implemented | Config settings now have task groups and per-group saved/unsaved state while retaining the supported single-form save. Process rows expose concise state and collapsed command details; actions disable when unavailable for current state and show affected-row progress/errors. Approved Q passed 2/2; disposable mocked process states and failed settings/process requests passed 1/1 without contacting a real process; `node --check zet/web/static/zet.js` and `git diff --check` passed. Disposable spec removed. |
| WP29 | Implemented | Queue states use readable current/completed/failure labels; owning-workflow links are on the target; ages and expanded failure/recovery detail are visible. Quiet polling defers table updates while focus remains in its rows and preserves facet options unless they change. Delete pending/failure feedback stays on the retained row. Approved Q passed 2/2 after updating the existing queue assertion to its new human-readable status label; disposable slow/stale storage, retained focus, expanded failure, and mocked delete failure passed 1/1; `node --check zet/web/static/ai_queue.js` and `git diff --check` passed. Disposable spec removed. |
| WP30 | Implemented | Pipeline Inspection now includes confined, read-only Character Asset Container records and Narrative story folders while retaining labeled legacy diagnostics. Pipeline Controls no longer offers legacy batch reset; current work points to the owning board. A disposable temporary-storage check passed for current/legacy listings, text preview, and invalid/traversal paths; Python AST, JavaScript syntax and `git diff --check` passed. No resets or migrations were run. |
| WP31 | Implemented | Dashboard task evidence and Pipeline Inspection images now open the shared zoom viewer. Character refinement and post-render adjustment images use a standalone zoom/pan/reset viewer with keyboard access; Character cross-phase FRONT inputs now offer Browse, Paste, and Image Inventory. Disposable browser zoom/Escape/Inventory acquisition passed; approved Character-to-costume and Character candidate-board safety journeys passed (2/2); changed JavaScript syntax checks passed. No task was submitted. |

The failed disposable render and initial disposable assertion/navigation mistakes are validation findings, not permanent tests. WP02 and WP03 passed their focused disposable browser/API acceptance checks. WP30 and WP31 are implemented. WP32 evidence is captured on the current Test revision, with remaining acceptance follow-up recorded in its packet row.

## Wave 1: repair verified defects

### WP01 - Compare initialization and side failures

- Dependencies: none. Findings: UI-01, UI-10.
- Files/interfaces: `zet/web/static/zet.js` Compare activation, independent-side loaders and legacy handlers; `index.html` Compare markup.
- Work: route activation through the current independent-side implementation; remove obsolete active references to absent controls. Handle each side's rejected request and stale response locally.
- Acceptance: menu entry and direct URL render the same controls without an exception; changing universe/character/phase on one side does not corrupt the other. One unavailable image leaves the other side usable.
- Validation: J; disposable Compare entry/side-change/failure checks at desktop and landscape tablet; `git diff --check`. No dedicated existing Compare scenario is claimed.

### WP02 - Lettering confirmation and selection integrity

- Dependencies: none. Finding: UI-02.
- Files/interfaces: `narrative_scene_text_service.py`, `narrative_candidate_board.js`, `narrative.js`; existing scene-text endpoints in `narrative_router.py` if a separate select intent is needed.
- Work: separate saving/confirming a finished image from replacing the selected candidate. Validate publication/selection effects before writing finished artifacts; retain a saved draft if a later step fails. Preserve current locked bytes and selection.
- Acceptance: finish text on an unlocked draft while another candidate is locked without an unexplained late selection failure; changing the selected image remains explicit and guard-protected. Stale text tokens still fail safely.
- Validation: J, P, N; disposable second-candidate/other-lock case and saved-file/selection check. The existing finishing scenario does not assert that blocked case.

### WP03 - Safe text editor close and failure recovery

- Dependencies: WP02. Finding: UI-15.
- Files/interfaces: `scene_text.js`, `scene_text.css`; shared unsaved-change presentation in `zet.js` where suitable.
- Work: distinguish Save draft, Save finished image and Close. Close/Escape offer save/discard/continue when needed and remain usable after validation/network errors. Show which save succeeded before a later failure.
- Acceptance: no editor trap; no silent finish or lost edits on Escape; close restores review focus and scroll. A failed finish retains the draft and current image.
- Validation: J, N; disposable empty-placement, failed-save and failed-confirm interactions via both Close and Escape.

### WP04 - Importer empty and failed states

- Dependencies: none. Finding: UI-03.
- Files/interfaces: `zet.js` `loadSceneCandidates`, scene import markup/navigation labels in `index.html`; import/source services only if serialization lacks an explicit error state.
- Work: finish loading when no source is configured, distinguish unavailable source from no matching briefs, and label the destination by its import purpose. Keep current source selection valid when the source list changes.
- Acceptance: no indefinite Loading for an empty configuration; recovery guidance names the missing configuration/source; a populated source still imports idempotently.
- Validation: J; disposable no-source, stale-source and prepared populated-source checks; do not modify the external Adventure Log source.

## Wave 2: shared foundations

### WP05 - Tokens and explicit action definitions

- Dependencies: none. Finding: UI-11.
- Files/interfaces: `zet.css`, `candidate_board.css`, `image_card_ui.js`; proposed `ui_actions.js`; `UI_STYLE_GUIDE.md`.
- Work: centralize action label, glyph, semantic role and ordering. Keep compatible decoration during migration. Consolidate Draft/Final/upscale tokens, typography, spacing, feedback and touch/focus rules.
- Acceptance: the same action looks and reads the same in cards and review. Color never supplies the only state meaning. Repeated actions do not gain page-local SVG definitions or conflicting palettes.
- Validation: J, C; disposable representative action sheet at both pointer modes, measured contrast/focus and long-label inspection.

### WP06 - Operation status presentation

- Dependencies: WP05. Findings: UI-08, UI-18.
- Files/interfaces: proposed `operation_status.js`, shared styles in `zet.css`, board feedback rendering in `candidate_board_component.js`.
- Work: present submitting/queued/running/success/error/unknown/paused states with local messages, accessible announcements and scoped recovery actions. Preserve the board's existing revision/attempt fencing and feedback ownership.
- Acceptance: clicks acknowledge before waiting; failures survive subsequent polling; repeat submissions are blocked at the correct scope. An uncertain response triggers reconciliation before a retry.
- Validation: J, C; disposable slow/rejected/unknown response checks and state changes while the originating section is collapsed.

### WP07 - Candidate review layout and persistent decisions

- Dependencies: WP05-WP06. Findings: UI-05, UI-10.
- Files/interfaces: `candidate_board_component.js`, `candidate_board.css`, integration documentation.
- Work: keep navigation, zoom, Select/Lock and their status outside the advice/details scroll area. Shorten the visible heading; retain full copyable identity and automation-accessible candidate IDs. Make disabled reasons usable on touch.
- Acceptance: 1133x610 review supports candidate navigation, selection and lock without scrolling through advice. Same-candidate updates preserve zoom, comparison, scroll and focus. All supported workflow actions retain their meaning.
- Validation: J, C, N, G; disposable long-advice/coarse-pointer and mixed pending/complete gallery checks.

### WP08 - Shared image viewer and zoom interaction

- Dependencies: WP05, WP07. Finding: UI-07.
- Files/interfaces: `review_image_zoom.js`, proposed `image_viewer.js`, `zet.js` full-size viewer boundary, shared viewer CSS; Candidate Board adapter to the shared zoom controls.
- Work: supply explicit zoom/reset, image-area pan/pinch, image navigation, loading/error state, accessible close/focus return and optional caller actions. Preserve existing editor-specific gestures via a viewing-only adapter.
- Acceptance: touch and keyboard can inspect every part of a zoomed image; image changes/reset fit correctly; page scrolling works outside the image. Viewing alone does not select or publish.
- Validation: J, C; disposable thumbnail/keyboard/zoom/pan/load-failure and focus-return checks. Physical pinch behavior remains a device check if hardware is unavailable.

### WP09 - Common image acquisition and Inventory picker

- Dependencies: WP05-WP06, WP08. Finding: UI-06.
- Files/interfaces: `image_input.js`, proposed `image_inventory_picker.js`, picker boundary currently exposed by `zetQuickCharacterWizard.openLibraryPicker`, existing catalog read/import APIs.
- Work: one component for Choose image, actual async Paste image, Image Inventory, preview, label, replacement/removal and constraints. Return typed file or Inventory acquisition to caller adapters. Remove creative-workflow ownership from the shared picker boundary.
- Acceptance: all three acquisition methods can be used with touch and keyboard; denied/empty clipboard preserves the previous source; a late read cannot replace a newer source or another universe's input.
- Validation: J; disposable three-path acquisition, current-filter visibility, read cancellation and rejected-image checks using the isolated library.

### WP10 - Shared proposed-change review and small choices

- Dependencies: WP05-WP06. Findings: UI-09, UI-14.
- Files/interfaces: `interview_proposals.js`, proposed `proposal_review.js` only if needed for state/actions; `zet.css` and `narrative.css` proposal styles; shared board field renderer.
- Work: reusable before/after rows with acceptance checkboxes, Apply selected changes, optional full diff and scoped progress/conflict messages. Supply native radio rendering for small exclusive sets.
- Acceptance: unchecked proposals cannot change inputs; applying a subset reports what changed and preserves current edits on conflict. Radios, checkboxes and labels follow their native keyboard semantics.
- Validation: J; disposable subset selection, duplicate text findings, rejected apply and concurrent edit checks. Existing service exact-text/revision validation remains authoritative.

### WP11 - Expandable production workspace shell

- Dependencies: WP05-WP07. Findings: UI-04, UI-14.
- Files/interfaces: proposed `production_workspace.js` and `production_workspace.css`; `index.html` shared mount points; Candidate Board integration documentation.
- Work: arrange context, domain-owned preparation, readiness/activity summary and board. Preserve per-scope disclosure choices and local drafts; keep render actions reachable without duplicating the board/controller.
- Acceptance: empty/incomplete setup opens necessary inputs; a ready board prioritizes results. A short landscape viewport exposes render actions and candidates. Async updates never reopen/close preparation or jump scroll.
- Validation: J; disposable prepared empty/ready/pending shell inspection at all target viewports. Integrate one Character pilot in WP12 before adopting this shell elsewhere.

## Wave 3: main workspaces and wizards

### WP12 - Character workspace pilot

- Dependencies: WP09-WP11. Findings: UI-04, UI-06, UI-14.
- Files/interfaces: `character_asset_container.js`, Character container markup, `CharacterContainerPromptService`, `character_asset_container_service.py` only for missing readiness serialization.
- Work: mount the shared shell, references/input status and prompt preview around the existing board; integrate Head input acquisition and visible unsaved recipe/mode settings. Preserve automatic deterministic compilation.
- Acceptance: Body, Head, Assembly and Dressing present the same anatomy; source/phase/mode differences remain explicit. Render uses the intended saved inputs and current compiler; preview and request expose matching ordered bindings.
- Validation: J, P if changed, C; upstream/source-consumption scenarios as affected. Disposable coarse-pointer Character pilot review before WP13-WP16.

### WP13 - Minor Character board alignment

- Dependencies: WP12. Findings: UI-08, UI-14.
- Files/interfaces: `minor_characters.js`, Minor Character markup, `minor_character_service.py` prompt-basis/public state, shared proposal integration.
- Work: adopt workspace layout, shared prompt-readiness language, proposal review and local status. Retain source/template revision checks and editable saved prompt behavior.
- Acceptance: input changes visibly require prompt update; Update prompt does not render; saved current prompt renders normally. Style stays private and official views publish through their existing lock path.
- Validation: J, P, M; disposable prepared Style interview/update/render/private-lock and official-view publication checks.

### WP14 - Narrative authored-prompt freshness

- Dependencies: WP06, WP10. Finding: UI-14.
- Files/interfaces: `narrative_generation_service.py`, `narrative_scene_service.py`, `narrative_prompt_service.py`, relevant Narrative model/repository serialization; `narrative_candidate_board.js`.
- Work: record and compare the effective prompt input basis, including relevant shared direction, applied local overrides, source/placement and style changes. Expose needs-update/ready/unknown without scanning completed image lineage. Keep manually saved/adopted prompt support.
- Acceptance: relevant input changes prevent an accidental stale-prompt render with an actionable explanation. Update prompt is explicit; stale writer responses cannot overwrite newer edits; retries and finished locks retain frozen records.
- Validation: P, J, N; disposable shared/local input change, manual prompt, late response and older-record adoption cases.

### WP15 - Narrative preparation and source layout

- Dependencies: WP11-WP12, WP14. Findings: UI-04, UI-08, UI-09.
- Files/interfaces: `narrative.js`, `narrative.css`, `narrative_candidate_board.js`.
- Work: use the common workspace shell for backdrop/subscene/assembly; collapse long direction/context/interview sections while preserving direct editing and placement. Adopt shared proposal and operation status; use radios for appropriate small mode/style sets.
- Acceptance: a returning operator reaches render shortcuts and candidates immediately. Placement and pending proposals remain accessible, and scene/target changes preserve correct scope and draft guards.
- Validation: J, N; disposable three target kinds, long direction, pending interview and landscape review checks.

### WP16 - Image Generation and Reconstruction alignment

- Dependencies: WP09-WP12. Findings: UI-06, UI-08, UI-14.
- Files/interfaces: `image_generation.js`, generation/reconstruction markup, related shared styles; generation asset service only if prompt state serialization is insufficient.
- Work: adopt the shell, direct-prompt save state, common ordered reference inputs, reconstruction stages/proposals and scoped activity. Replace native prompt dialogs used for rename/create/conflict with shared forms where they affect the flow.
- Acceptance: direct prompt entry still renders with no required AI-writing step; reference order/labels survive reload; Reconstruction analysis and prompt adoption remain explicit; correction ancestry and independent Inventory publication remain intact.
- Validation: J, G; disposable upload/paste/Inventory, conflicting save, ready/failed analysis and landscape correction review checks.

### WP17 - Character Wizard alignment

- Dependencies: WP09-WP10, WP12. Findings: UI-06, UI-08, UI-09.
- Files/interfaces: `character_wizard.js`, wizard markup/styles in `index.html`/`zet.css`, existing wizard source router/service as required for Inventory acquisition.
- Work: shared reference slots, stage status, effective model, proposal checkboxes, draft-save feedback and safe close/resume. Keep template preview and explicit acceptance before production handoff.
- Acceptance: browse/paste/Inventory work on touch; sections remain editable through delayed proposals; acceptance opens the right production context without silently rendering.
- Validation: J, P if changed, W; disposable partial selection, interruption/resume and long landscape dialog checks.

### WP18 - Costume Wizard alignment

- Dependencies: WP09-WP10, WP12. Findings: UI-08, UI-11, UI-21.
- Files/interfaces: costume handlers in `zet.js`, costume wizard markup/styles, costume wizard services for effective-model/progress serialization.
- Work: same intake/proposal/status anatomy; common image inputs and private trial viewer; visible draft revision and current/earlier test labels; clear accept-to-Dressing handoff.
- Acceptance: private test never changes the ordinary Dressing board; outdated tests are labeled; accepts only by an explicit action; model/status and feedback remain visible during async work.
- Validation: J, P if changed, W; disposable earlier/current revision, failed retest and landscape proposal/viewer cases.

### WP19 - Minor Character source acquisition

- Dependencies: WP09, WP13. Finding: UI-06.
- Files/interfaces: `minor_characters.js`, `minor_character_router.py` and `minor_character_service.py` as needed; existing catalog import services.
- Work: add file/paste paths to its Inventory-source model through explicit Import and use. Keep acquisition provenance, duplicate handling and eligible source validation under current services.
- Acceptance: all three methods produce a usable source; cancel/reject keeps the old source; no silent Inventory publication or source overwrite. Private Style remains bound to the selected source.
- Validation: J, P, M; disposable import/cancel/duplicate, invalid source and cross-universe late-read checks.

### WP20 - Narrative source acquisition

- Dependencies: WP09, WP14-WP15. Finding: UI-06.
- Files/interfaces: Narrative element/reference picker in `narrative.js`, `narrative_reference_service.py`, existing catalog import services and Narrative router only where necessary.
- Work: common image acquisition and explicit import when required by the element/reference contract. Keep backdrop reuse/import, element references and placement as distinct domain actions.
- Acceptance: all input methods retain source kind, labels and ordered binding semantics; cancellation is harmless; new inputs affect next-render readiness while submitted images keep captured bytes.
- Validation: J, P, N; disposable source replacement and stale-scope checks, plus one finished-image record check.

## Wave 4: complete the site

### WP21 - Inventory list, details and organization

- Dependencies: WP08-WP09, WP16. Findings: UI-06, UI-10, UI-12 related picker presentation.
- Files/interfaces: Inventory controller sections in `zet.js`, inventory markup/shared styles; existing catalog services/router. Extract a focused Inventory presentation module if needed for bounded ownership.
- Work: visible active filters/clear-all, consistent cards and viewer, source acquisition for add/replace, grouped details, searchable organization controls, local save/description activity and full tag access.
- Acceptance: search/filter empty states are clear; image replacement is explicit and scope-safe; entity/reference/facet edits preserve image bytes and aliases; long labels remain readable on tablet.
- Validation: J, P if changed, L; disposable organization subviews and multi-source input checks. Existing Inventory scenario covers persistence, not all subview interactions.

### WP22 - Overview, Compare, Identity Keys and Turnaround images

- Dependencies: WP01, WP08-WP09, WP12. Findings: UI-07, UI-10, UI-13.
- Files/interfaces: `character_hub.js`; `zet.js` Compare/key/turnaround presentation; corresponding markup/styles. Services change only if missing readiness/action data is needed.
- Work: common image viewing and separate Open workspace actions, readable context selectors, source previews and direct missing-view links. Align save/lock/promotion labels with their verified effects.
- Acceptance: key creation/publication remains intact; full Turnaround correctly requires eight source views; allowed partial sheets remain available; Compare sides and image navigation remain independent.
- Validation: J, C plus `npm.cmd run test:e2e -- --grep "Character workflows consume published locks"`; disposable three-view missing/full-eight-view/partial-source checks. Do not claim a test selected zero tests as a pass.

### WP23 - Finishing, lettering/style and animation controls

- Dependencies: WP02-WP03, WP05-WP08, WP15. Findings: UI-09, UI-10, UI-15.
- Files/interfaces: `scene_text.js`, `scene_text.css`, Narrative crop/animation presentation in `narrative.js`/`narrative.css`.
- Work: common modal chrome, save/preview/status and glyphs, native short choices, reachable decisions and touch sizing. Offer visible non-drag placement/resize alternatives; retain editing gestures and confirmed-text semantics.
- Acceptance: crop/text/animation tools are usable in short landscape space; closing preserves or deliberately discards drafts; preview/export uses the saved pinned scene and locked lettering bytes remain unchanged.
- Validation: J, F; disposable keyboard/touch editor movement, failed save, long style panel and animation preview/export inspection.

### WP24 - Visual Zine editing and validation

- Dependencies: WP08, WP15, WP21. Finding: UI-12.
- Files/interfaces: Zine presentation in `zet.js`, Zine markup/styles; `zine_service.py` only if a readable source/requirement projection is needed.
- Work: replace raw-tag assignment as the primary interaction with thumbnail/title choosing; keep editable/source details accessible. Show required slots, partial-fill counts and field errors beside affected pages; standardize print preview/viewer.
- Acceptance: complete valid assignments create/reload/regenerate the print layout; repeated source use works where supported; a one-scene partial fill explains missing pages and never claims full readiness.
- Validation: J, P if changed, F; disposable fresh-source page/spread selection and print preview checks at desktop/tablet.

### WP25 - Responsive shell and Recent Renders

- Dependencies: WP05-WP08, WP12-WP16. Findings: UI-10, UI-19.
- Files/interfaces: shell/Recent Renders in `zet.js`, `index.html`, `zet.css`.
- Work: keep context and task navigation readable, collapse utilities before crowding, show full selected names on demand, and adopt shared thumbnail activity rows for Recent Renders. Preserve event-driven updates and context-safe direct links.
- Acceptance: all destinations remain reachable; long names and header controls do not overlap; changing viewport preserves the open board/review; Recent Renders supports distinct Review/Open board paths.
- Validation: J, C, N; disposable shell navigation, two universes, long names and event update checks at all acceptance sizes.

### WP26 - Universe and species forms

- Dependencies: WP05-WP06, WP10, WP25.
- Files/interfaces: universe/create/settings/species markup and handlers in `zet.js`, shared form CSS and scene-style dialog integration.
- Work: consistent headings, action rows, local validation/save state, appropriate short choices and clear universe scope. Keep species editing and style preview responsive.
- Acceptance: save/conflict retains inputs; switching universe cannot apply an older response; style/species controls remain usable in landscape and full labels are available.
- Validation: J, L; disposable long species, rejected save and scope-change checks.

### WP27 - Template Editor and manuals

- Dependencies: WP05-WP06, WP25. Findings: UI-20, UI-21.
- Files/interfaces: `template_editor.js`, source-editor bridge in `zet.js`, template/manual markup and styles.
- Work: in-place source chooser and clear empty/unavailable state, reachable Save/Validate feedback, consistent source/diff typography, and contextual manual selection/copy/download feedback.
- Acceptance: users can choose a template from the editor; master conflicts retain local edits; unsaved navigation is guarded; help content has readable width and usable controls.
- Validation: J, L; disposable no-source, unreadable-source, long template, local conflict and clipboard rejection checks.

### WP28 - Config grouping and process feedback

- Dependencies: WP05-WP06, WP25. Finding: UI-16.
- Files/interfaces: Config handlers/markup in `zet.js`/`index.html`, process/config service projections as needed.
- Work: audit active settings, group them by task and add section save state. Match process actions to capabilities/current state and use affected-row progress/error. Summarize technical details without obscuring recovery.
- Acceptance: users know which section is unsaved and which process action is pending; unrelated settings stay usable. No running-process action is exercised against the user's runtime for validation.
- Validation: J, P if changed, Q for shared integration; disposable prepared process states and failed setting save checks with mocked services.

### WP29 - Queue presentation and recovery

- Dependencies: WP05-WP06, WP25. Finding: UI-18.
- Files/interfaces: `ai_queue.js`, queue markup/shared styles; durable AI job projection only if compact recovery fields are missing.
- Work: readable status/target rows, expanded exception/request detail, useful ages, local action feedback and links to owning workflow. Keep durable failures and existing ownership/fencing; avoid repeatedly replacing focused controls during refresh.
- Acceptance: current activity and historic failures are clearly distinguished; filters/pagination and retained errors work; recover/delete explanations state actual effects.
- Validation: J, Q; disposable slow/failing refresh, pending row action, focus retention and storage-unavailable states.

### WP30 - Current pipeline diagnostics and legacy controls

- Dependencies: WP12-WP16, WP28. Finding: UI-17.
- Files/interfaces: `pipeline_inspection_service.py`, `pipeline_control_service.py`, their routers; pipeline tool handlers/markup in `zet.js`/`index.html`.
- Work: map callers before removal, hide unsupported legacy reset forms in current production context, and retain useful read-only diagnostics through focused services for current containers/Narrative storage. Keep compatibility entry points informative and source files untouched.
- Acceptance: active tools no longer invite a reset of nonexistent legacy pipelines or imply current data is absent because only an old root was inspected. Diagnostic file access stays confined and demand-driven.
- Validation: P, J; disposable current-container/Narrative/legacy-link/invalid-path checks. No destructive reset or migration.

### WP31 - Task capture and remaining image/viewer consumers

- Dependencies: WP08-WP10, WP21, WP25. Findings: UI-06, UI-07.
- Files/interfaces: `task_capture.js`/`.css`, `local_character_refinement.js`, `local_character_prompt_improvement.js`, `local_template_improvement.js`, and remaining mounted static-image consumers identified by source search.
- Work: finish shared acquisition/viewer/dialog adoption and local async feedback on active consumers. Remove replaced presentation handlers/styles only after their active callers are gone; leave unrelated retired code alone.
- Acceptance: every active static thumbnail uses the common viewer or a documented editor expand action; every active image input has all three acquisition methods. Task drafts/context survive edits and no external issue is submitted during validation.
- Validation: J; disposable consumer matrix, attachment acquisition, task preview and draft/failure checks. Record any unavailable consumer instead of claiming coverage from a redirect.

## Wave 5: acceptance and knowledge maintenance

### WP32 - Final acceptance and evidence handoff

- Dependencies: WP01-WP31.
- Files/interfaces: affected docs listed below; this brief/design/review/packet log; new retained before/after evidence index. Update existing capture tooling only if needed to validate actual route, dimensions and state.
- Work: review the final diff, run the complete approved suite, capture desktop/landscape states and verify route/profile/health/manifest identity. Show the main four workspaces at the same conceptual stages. Record failures and physical-device gaps explicitly.
- Acceptance: each finding maps to an implemented result or a user-approved deferral with a reason; full tablet task access works; priority board tasks require no authoring-form traversal; image acquisition/viewing, action vocabulary and status behavior are consistent. No mixed-release or mislabeled capture is counted as acceptance.
- Validation: ALL; targeted prepared checks only where remaining concerns justify them; inspect representative screenshots and error logs. Live model/render checks remain separately requested.

| WP32 | In progress; latest-release evidence captured, three workflows incomplete | Test revision `f9fc7b0e1c60c5e76800c4629fb55ed6b1137440` / boot `bb4e7d0b15344574a598b70494ada5af` is health-verified and matches its active release record; the release update log records 20/20 approved E2E scenarios passed. Every fresh Zet_Tester evidence manifest for this campaign matches that revision/boot. Character creation, Body Reference correction, Head Image Edit and Assembly views completed; Costume Wizard correction targeting blocked Costume acceptance and Dressing. Minor Character Style and all three requested views completed and survived refresh with desktop/tablet captures. Image Generation txt2img, img2img and universe-style variants completed; Reconstruction and compare/correct were not run because the case omitted the selected-candidate prerequisite. Narrative references were verified and a new story/scene shell created, but duplicate model controls prevented selecting the required authoring model, so no AI work ran. Fresh Character and Narrative runs captured the full-size viewer close overlap. The checkout now separates viewer controls and gives replacement model buttons field-specific accessible names; both local fixes remain unverified in a deployed/browser run. Inventory Details scoping and Costume Wizard action targeting remain open findings. The older 3254602 evidence is historical and superseded for current acceptance. Production observations and further Inventory-specific work remain deferred as requested. No external merge, push or deployment was performed during this evidence pass. |

### Remaining validation limits and deferred scope

- **WP04:** Complete. Import and repeat-import passed against a real Narrative repository in a temporary isolated library; no Test or Production narrative records were created.
- **WP06:** Character, Narrative and Image Generation lost-response checks passed, and the 20-scenario suite passed. Minor Character failure injection remains unexercised; its adapter uses the same refresh-and-unknown behavior.
- **WP08:** Complete. Physical tablet gestures were verified by Joe; browser zoom/reset/Escape were checked in disposable runs.
- **WP10:** Native checkboxes/radios and stale-field conflict handling passed disposable service checks; the 20-scenario approved suite passed. The guard is present in the health-verified f9fc Test release. The fresh Narrative visual run stopped before proposal handling because the authoring-model selectors could not be operated through Zet_Tester.
- **Image Inventory:** Further Inventory-specific review and implementation are explicitly deferred to a separate focused effort. The production observations are retained in the evidence review only.

## Documentation owners

Synchronize affected documentation as each interface changes, rather than leaving a documentation-only cleanup at the end:

- `Docs/UI_STYLE_GUIDE.md`: visual tokens, action labels, image input/viewer rules and feedback.
- `Docs/COMPONENTS/CANDIDATE_BOARD.md` and `CANDIDATE_BOARD_INTEGRATION.md`: review layout, actions/status and adapter changes.
- `Docs/COMPONENTS/DASHBOARD_UI.md`: responsive shell, shared modules and acceptance/device limits.
- `Docs/COMPONENTS/LOCAL_CHARACTERS.md`, `NARRATIVE.md`, relevant wizard guides: changed workflow and prompt-readiness behavior.
- `Docs/CODE_MAP.md`: new shared owners, extracted Inventory/viewer/picker boundaries and affected scenario gaps.
- `Docs/DATA_MODEL.md` and `INVARIANTS.md`: only if new prompt-basis fields or persistence contracts are introduced; preserve serialization compatibility.
- `Docs/Testing.md`: commands and actual validation results, without claiming new maintained coverage.
- Add a short ADR after checking the next available number for durable prompt-freshness ownership and shared workspace/image presentation boundaries. Do not duplicate complete schemas in it.

The plan stays in `plans/active/` through acceptance and implementation. Archive it only after the selected implementation scope is complete and actual validation is recorded. Approval of this plan does not itself deploy, publish, commit, push or authorize later unlisted refactors.
