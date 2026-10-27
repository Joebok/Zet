# Character and costume template editor

Status: complete — implemented and validated on 2026-10-26
Date: 2026-10-26
Related issue/specification: Joe's template-editor request in this chat; no tracker issue.

## Goal

Update the existing dashboard Template Editor to edit complete character and costume Markdown templates, with view applicability highlighting, case-insensitive search highlighting, a current-master diff, and compiler-compatible validation before saving.

Joe authorized implementation of this plan on 2026-10-26. Use one agent. This does not authorize external writes, live inference, production-library changes, new dependencies, or permanent tests. Work packets are sizing boundaries, not delegation instructions.

## Current behavior and evidence

- [index.html](../../zet/web/templates/index.html), `#template-editor-page`, presents a Source Editor with one textarea and Save Source. [zet.js](../../zet/web/static/zet.js), `renderSourceEditor`, `openSourceEditorForSource`, and `saveSourceEditor`, loads/saves through `/api/edit-source/load` and `/api/edit-source/save`. Existing dirty-navigation handling sets `autosave: false`.
- [SourceEditorService](../../zet/services/source_editor_service.py) supports Markdown files, marked sections, and JSON fields. Whole-file saves directly write text without template validation or an expected-master revision. Path resolution currently accepts the configured library or project; the specialized editor must resolve the selected universe's canonical target rather than trusting a client path or type label.
- The Costumes table's Open button already calls `openSourceEditorForSource(costume.source)`. Character/governing-source controls and Prompt Inspection also call it. Appearance/expression controls still contain calls. Config's `renderLlmRoleSettings` actively exposes instruction-file editing through the same function. Do not assume these callers are all dead merely because general-purpose editing is no longer the product goal.
- [Compile_Character_Template.py](../../Scripts/Compile_Character_Template.py), `load_template_sections_with_sources`, validates recognized section pairing/duplicates and provides source ranges. Its regex can overlook malformed marker-like text, so successful extraction alone is insufficient validation.
- [view_conditioning_service.py](../../zet/services/view_conditioning_service.py) owns `VIEW_ORDER`, tags/groups/exclusions, inferred/explicit head/body domains, inherited defaults, canonical-only content, spatial visibility, and retained source-line numbers. `validate_view_controls` currently conditions with an empty `ViewContext`; some spatial contradictions require a concrete view to detect. Malformed directive-like text can also escape the recognized-directive regex.
- [CharacterOnboardingService.validate_template](../../zet/services/character_onboarding_service.py) and [CostumeService.validate_template_file](../../zet/services/costume_service.py) validate canonical sections and required content against shared templates/section metadata. Character validation permits compatible/optional sections, including legacy files without the newer optional `HEAD_EDIT_*` sections. Preserve those rules.
- [costume_mode_conditioning_service.py](../../zet/services/costume_mode_conditioning_service.py) composes rendering-mode annotations with view rules. A view selector must not silently select a costume rendering mode.
- [template_source_service.py](../../zet/services/template_source_service.py), `template_sources`, can supply unsaved text at its canonical path without changing the master. [local_template_revision_service.py](../../zet/services/local_template_revision_service.py), `template_diff_rows`, supplies aligned contextual diff rows. Its private `_validate_text` enforces proposal-specific token preservation and is not a complete validator for this editor.
- [local_template_improvement.js](../../zet/web/static/local_template_improvement.js) has a separate popup editor for batch proposals and source diffs. It can edit task/config templates and saves proposals, not disk masters. Leave that workflow and its acceptance/promotion boundaries unchanged.
- [Testing.md](../../Docs/Testing.md#approved-fast-scenarios) and [fast.spec.mjs](../../tests/e2e/fast.spec.mjs) define four current maintained scenarios. S1 covers character upload/costume naming; S2 covers front Assembly/Dressing compilation/publication. None directly covers this editor. Older three-scenario wording in AGENTS/planning docs is stale; do not edit unrelated documentation to reconcile it here.

## Desired behavior

### Opening and editing

- Reuse the existing Template Editor destination and costume Open action. Support the selected character phase's `Character.md` and selected `Costume_*.md`, opening the complete file even when the incoming character/costume source identifies one section. Scroll to that section when available.
- Show template identity/path, Full file/Diff, View, Search, validation feedback, and Save. Use character/costume wording rather than the obsolete Prompt Inspection instructions for these targets.
- Keep the existing character entry points and add a direct Edit character template action beside the existing character setup/template controls if they otherwise require a historical asset. Resolve its target through existing phase/path services; no new file browser or template creation workflow.
- Keep one authoritative plain-text draft. All characters, including markers, tags, and grayed text, remain editable. Decoration, searching, analysis and diffing must never rewrite the draft or reset native undo history. Preserve selection/caret/scroll on control changes.

### View highlighting

- Default to **Off**. Off shows the entire raw file with no view-based dimming. Search marks may still appear.
- Offer all eight views in compiler `VIEW_ORDER`, using readable labels. For this single orientation selector, apply the selected view to both head and body domains; independent head/body selectors are out of scope.
- In a selected view, applicable prose has normal foreground emphasis; inapplicable prose is gray. Never hide, delete, disable, or make any line read-only. Keep sufficient contrast to read/edit dimmed text.
- Derive applicability from the shared parser/conditioning decisions, including default scopes, explicit domains, exclusion groups, canonical-only and spatial omissions. Plain unscoped prose applies to all views. Keep file metadata, delimiters, and compiler-control lines readable as structural context; headings remain present, with headings belonging only to inactive prose dimmed. Canonical-only prose is dimmed for selected render views.
- This is authored view applicability, not a preview of one pipeline's selected prompt sections. Do not gray a whole section merely because one pipeline omits it. Do not translate anatomical wording or strip tags in the editor.
- Evaluate costume mode annotations across their valid modes: a line applicable to the chosen view in any supported mode stays applicable. Validate mode syntax without adding a mode control.
- Recalculate as the draft changes, with debounced backend analysis. Apply responses only when target and draft revision match. While syntax is incomplete, keep affected lines neutral with diagnostics rather than presenting guessed or stale applicability as authoritative; valid sections can retain their results.

### Search

- Literal, case-insensitive substring search, covering the complete draft, including dimmed text and tags. No regex interpretation, replacement, or line filtering. Empty search clears its marks.
- Highlight every occurrence and show a match count. Search background marks take visual precedence over dimming without changing applicability. Use text nodes/escaped text so template HTML-like text is displayed literally.
- Preserve the query when toggling Full file/Diff. In Diff, highlight matches in both displayed columns; label its count as displayed diff matches. Full file counts always cover the complete draft.

### Diff and disk master

- Full file is the editable mode. Diff is a read-only contextual side-by-side review of **Master on disk → Current edits**, with original/new line numbers and an explicit no-changes state. Return to Full file to edit any text.
- Compare the whole raw draft, independently of selected view/search. Never compare against Git HEAD, a shared blank template, a compiled prompt, or a batch overlay. Do not omit changes on dimmed lines.
- Fetch the current master on entering Diff and provide Refresh diff for changes made elsewhere while Diff is open. Label the master revision used. Draft changes made after returning to Full file appear on the next Diff entry. Do not add background disk polling.
- Keep the original load/save revision separate from a refreshed diff revision. If the master has changed since loading, show a conflict notice and preserve the draft; merely viewing a newer master must not authorize overwriting it.

### Validation and saving

- Save validates the exact submitted draft on the server, even if client analysis reports success. Validation errors prevent any master write and retain the draft, search/view settings and dirty state. Allow opening an already-invalid template so it can be repaired.
- Report actionable error codes/messages with section and source line/range where available. Selecting an error returns to Full file and focuses that location. Provide a general message when a line cannot be determined; do not invent locations.
- Check balanced/matching/unique section markers; missing/unsupported canonical sections and required content according to the current character/costume contract; recognized control-block balance; malformed reserved marker/directive syntax; valid view groups, domains, defaults and exclusions; spatial rules in each of the eight concrete orientations; and costume rendering-mode annotations. Include valid placeholder/resource and variant syntax where the source format supports them, using existing compiler helpers rather than freezing all existing token text.
- Reuse existing schema/content validators through an unsaved-text interface; do not require new optional character sections in old files, introduce a new template schema, or silently repair/reformat text. Legitimate tag and supplemental-reference edits remain allowed.
- Establish structural/view compiler acceptance without requiring generated prerequisite images, a batch, AI calls, or render jobs. Do not claim that this guarantees reference availability, every pipeline-specific input, or artistic quality. Resolve new parser/helper gaps as part of the validator, not by running live compilation against the normal library.
- Under the applicable existing write fence/lock, recheck canonical target ownership and the expected disk digest, validate, then atomically replace only the target. Coordinate with existing template promotion locks and `usage_mutation`; preserve edit logging. A conflicting/deleted/inaccessible master fails without replacing it. Do not add a new lock protocol or delete lock files.
- Return a server-confirmed saved revision and submitted text baseline. If typing continues during Save, only the submitted text becomes saved; newer draft text remains dirty. Successful save resets subsequent diff to the new disk master without losing newer edits.
- Preserve source text, Unicode, whitespace and newline conventions as far as the existing format allows; add no automatic formatting. Save changes the canonical file only. Accepted batch revisions, frozen asks/retries, image locks and Inventory publications retain their existing behavior.

## Impact analysis and boundaries

| Area | Planned ownership |
| --- | --- |
| Shared text validation | New focused `zet/services/template_validation_service.py`; small adaptations in `character_onboarding_service.py`, `costume_service.py`, compiler/view helpers only where needed to share authoritative rules and accept unsaved text |
| Load/analyze/diff/save | `zet/services/source_editor_service.py`; thin existing routes in `zet/web/app.py`; server-resolved character/costume targets and revision checks |
| Raw editor/search/decorations | New `zet/web/static/template_editor.js`; scoped `zet.css` rules; `index.html` controls/script inclusion |
| Dashboard integration | Narrow `zet.js` entry-point, dirty-state and save adapters; preserve the existing costume handoff; character setup action if needed |
| Knowledge owners | `Docs/COMPONENTS/PROMPTS.md` for syntax/validation; `Docs/COMPONENTS/DASHBOARD_UI.md` for editor controls; `Docs/CODE_MAP.md` for new entry points. Update `Docs/COMPONENTS/LOCAL_CHARACTERS.md` only for affected authoring handoffs; `Docs/Testing.md` only to record actual validation. No stored schema or broad architecture-document rewrite is planned. |

No new production dependency is planned. Use a native textarea with a synchronized noninteractive escaped-text decoration layer, matching font/wrap/padding/scroll metrics; make that layer hidden from accessibility tools and keep the textarea as the actual accessible editable control. Validate this approach with wrapping and input-method checks before proceeding. If reliable alignment requires an editor dependency, stop at that concrete limitation and seek approval rather than installing one.

Specialize by a server-recognized template target. Keep a minimal existing plain-source compatibility path for the active Config instruction-file editor and any confirmed remaining non-template callers. New view/validation features apply only to character/costume masters. Do not delete the general backend or redirect task-template/proposal edits into a character validator. Replacing or redesigning those other workflows requires separate scope.

## Implementation steps — Luna sized work packets

### WP1 — Authoritative validation and line applicability

- Dependencies: none.
- Files/interfaces: `template_validation_service.py` (new), `view_conditioning_service.py`, narrow compiler section-loading helpers in `Scripts/Compile_Character_Template.py`, and existing character/costume validator entry points.
- Work: expose validation of unsaved text at its canonical identity using `template_sources` or a shared text parser; retain current schema/optional-section rules. Expose source-line applicability from the same conditioning decisions used for compilation, including partial diagnostics for invalid drafts. Avoid a second parser in JavaScript. Check all eight orientations and costume mode combinations deterministically. Keep compiler output/source mapping unchanged for valid inputs.
- Acceptance: valid seeded character/costume text passes; broken markers/tags/directives and concrete-view spatial errors fail with useful locations; optional legacy sections remain optional; returned line coordinates address the raw draft. Off requires no analysis to display the file.
- Validation: disposable temporary-directory checks against actual seed/shared templates and mutated copies, including parser/output equivalence for representative valid tagged sections; Python 3 syntax/AST checks of touched files. Do not modify the seed or add maintained tests.
- Status: complete — shared unsaved parser, concrete-view applicability, schema/content reuse and located diagnostics implemented; disposable service checks passed.

### WP2 — Revision-aware editor service and routes

- Dependencies: WP1.
- Files/interfaces: `source_editor_service.py`, existing edit-source routes in `web/app.py`; existing `PathService`, atomic writer, usage and template-lock interfaces consumed without unrelated redesign.
- Work: extend load with recognized template identity/full text/load digest; add focused analyze/diff actions under the existing edit-source route family; require target, draft text and draft revision for analysis, and expected-master digest for specialized saves. Return line states/diagnostics and current-master diff rows. Reuse `template_diff_rows` without involving AI/batch services beyond that pure helper. Validate/save under existing applicable locks and atomic write rules.
- Acceptance: cross-universe or forged target/type requests are rejected; section sources load the whole correct template; analysis/diff never write; invalid saves and stale-disk saves leave bytes unchanged; valid save returns its new baseline. Existing non-template Config load/save still works.
- Validation: disposable service/HTTP probes with private temporary library/configuration, unchanged-file digest assertions, stale-master/save interleaving and failure cases; Python syntax check. No normal-library writes or live app startup with production configuration.
- Status: complete — recognized targets, analysis/diff, revision conflict checks and fenced atomic saves implemented; disposable service/browser checks passed.

### WP3 — Full-file editor with view and search decoration

- Dependencies: WP1/WP2 response contracts.
- Files/interfaces: new `template_editor.js`, editor section/script in `index.html`, scoped `zet.css`.
- Work: implement one textarea draft plus synchronized decoration layer, Off/eight-view selector, debounced analysis revision fencing, literal search marks/count and validation-location focus. Expose a small controller API for get draft, set loaded target, submitted-save baseline and dirty changes.
- Acceptance: dimmed text, markers and tags remain editable; Off restores normal full text; repeated/mixed-case/special-character searches work; stale analysis cannot recolor a later draft/other target. Selection, undo, multiline paste, Tab/native keyboard behavior, composition input, Unicode, wrapping and scroll remain reliable with a large real template. No duplicate accessible text or HTML execution.
- Validation: `node --check zet/web/static/template_editor.js`; disposable isolated Chromium checks at desktop and narrow widths, including wrapped long lines and caret/decoration alignment. Use the approved fixture, not the normal library; store only disposable evidence.
- Status: complete — native editor, search/view decoration and diagnostics implemented; desktop/narrow wrapping/scroll/caret/undo checks and screenshot review passed.

### WP4 — Dashboard handoffs, diff and validated save

- Dependencies: WP2/WP3.
- Files/interfaces: focused `zet.js` adapters, `template_editor.js`, `index.html`, scoped CSS; service responses from WP2.
- Work: wire existing costume/character source entry points to the specialized controller, adding the bounded character setup action if required. Integrate Full file/Diff, Refresh diff, master revision/conflict feedback, search in diff columns, validation errors and save lifecycle. Preserve `autosave: false`, navigation protection and the small active generic compatibility path. Protect a dirty current draft before opening a different source, including asynchronous load failures/races.
- Acceptance: open character/costume, edit a dimmed line, find it, review its full-file diff, return without lost text/undo, save and reopen. Disk edits made elsewhere cause a visible conflict and cannot be overwritten by refreshing Diff. Invalid Save retains all edits and navigational protection; typing during a save remains dirty afterward. Config instruction editing and batch-proposal behavior remain intact.
- Validation: `node --check zet/web/static/zet.js`; `node --check zet/web/static/template_editor.js`; disposable isolated browser/API journey covering these checkpoints, with screenshots for readability. No permanent scenario expansion.
- Status: complete — character/costume handoffs, diff, validated save, reload, dirty-navigation and stale-response handling implemented; disposable Chromium journey passed.

### WP5 — Regression validation and affected documentation

- Dependencies: WP1–WP4.
- Files/interfaces: only affected documentation listed above, this plan; existing approved test runner/scenarios unchanged except repairs required to preserve their approved purposes.
- Work: run the approved fast suite once after focused checks pass; inspect final diff for accidental compiler behavior changes, unrelated cleanup or broadened editable paths. Document controls, single-selector head/body meaning, current-disk diff, validation limits and unchanged batch-overlay semantics. Record actual commands/results and move this plan to `plans/completed/` only after implementation and validation finish.
- Acceptance: four approved fast scenarios pass; focused disposable checks establish the editor-specific gaps; changed-file syntax checks and `git diff --check` pass; documentation matches observed behavior and names any unresolved limits.
- Validation: verify available Python 3 interpreter as required by AGENTS, then `npm.cmd run test:e2e` in the isolated fixture; changed Python AST checks; both changed JavaScript syntax checks; `git diff --check` and manual final diff review. Do not run the separately invoked live Narrative check.
- Status: complete — four approved E2E scenarios, changed-file syntax checks and final diff review passed; affected knowledge updated.

## Validation coverage and limits

- S1 remains regression coverage for character template upload and costume metadata authoring, not view-highlight/search/diff/save coverage.
- S2 remains regression coverage for front Assembly/Dressing compilation, references, selection and publication, not all eight view orientations or Body/Head generation.
- S3/S4 remain Narrative/shared-queue regressions because `zet.js` and the shared dashboard shell are touched.
- Disposable service/browser checks cover the new editor contracts above without adding permanent tests. If maintained coverage is desired later, request approval for the named user task and explain these gaps before changing scenarios.
- The initial planning turn required document review and `git diff --check` only. Implementation verification is recorded below and in Testing.

## Risks and alternatives

- **Source-line drift:** conditioned output can drop lines or transform spatial wording. Address the original parser ranges and decisions, never match rendered text back to the file by value; repeated lines must remain distinguishable.
- **Compiler/validator divergence:** reuse authoritative helpers and check representative output equivalence. Existing validators alone do not cover malformed reserved syntax or concrete-view spatial failures. Do not indiscriminately apply the proposal validator's token-preservation restrictions to free-form template editing.
- **Decoration alignment:** a textarea overlay must remain aligned on soft wraps, tabs, Unicode and composition. WP3 is the acceptance checkpoint for the no-dependency approach; do not ship visibly misaligned highlighting.
- **Disk concurrency:** refreshed diff and loaded baseline are different revisions. Preserve both; a newer diff never silently rebases edits. Conflict handling offers continued editing/copying and an explicit reload through existing discard protection, without adding automatic merging.
- **Scope pressure:** Config and the separate proposal popup still exist. Retain small compatibility behavior instead of redesigning or retiring unrelated workflows. Shared blank-template authoring, task/config template specialization, AI rewriting, new compiler syntax, batch migration and rendered previews are outside this plan.

## Progress and decisions

- Final verification: `npm.cmd run test:e2e` passed all four approved scenarios in 38.6s. Changed Python AST and both JavaScript syntax checks passed. Disposable service and Chromium checks passed against private fixtures, including delayed Save/analysis responses, invalid/conflicting save preservation, final-newline diffs, CRLF and desktop/narrow layout. Screenshot review caught a global `pre` height cap clipping the decoration layer; the scoped override and explicit height-alignment check passed on rerun.
- Actual changes: character onboarding validation was reused through its existing source overlay rather than refactored. Costume validation now consumes the shared pure parser instead of a temporary file. Shared compiler behavior for valid files remains unchanged; structural exceptions additionally expose line/section coordinates. A distinct final-newline diff indicator supplements the existing contextual diff helper, which intentionally compares split lines.
- Documentation: prompt contracts, dashboard UI, local character handoffs, code map and Testing updated. No stored schema, dependency, permanent scenario, production-library data or batch-proposal workflow changed. No additional ADR was warranted for these localized changes.

- Implementation: added a pure unsaved-section parser used by both file compilation and costume validation; the editor validator uses existing canonical schema checks and concrete-view source maps. Specialized load/analyze/diff/save now resolve canonical selected-universe templates, validate drafts, preserve disk newline convention and fence digest-checked atomic saves. Initial isolated service checks passed character/costume applicability, invalid-save preservation, stale-master rejection, generic compatibility and foreign-template rejection. The UI/controller and dashboard handoffs are wired; browser checks are next.
- Clarification: `ViewContext` with no rendering mode already retains the union of valid mode scopes while validating their syntax, so highlighting requires no separate mode-loop or selector.

- 2026-10-26: inspected the knowledge index/code map, architecture/data/invariants, current prompt contracts, approved testing policy, existing editor/callers, source overlays/diffs and validation helpers. Planning is complete; all implementation packets remain pending.
- Decision: extend the existing dashboard editor and retain its current destination/costume handoff. Keep canonical template editing separate from batch-proposal acceptance/promotion.
- Decision: one view selector sets matching head/body orientations; mode annotations do not introduce another selector. Off always displays the raw draft without view dimming.
- Decision: Diff is read-only review against current disk text; Full file provides editing everywhere. Disk revision conflicts block overwriting rather than losing outside edits.
- No ADR is needed for this planning artifact. During implementation, add one only if a significant durable boundary/contract choice emerges beyond these localized editor changes.

## Final results

Implemented all five work packets. The existing editor now supports whole character/costume files, editable view dimming, literal case-insensitive search, current-disk diffs, validation diagnostics and conflict-checked atomic saves. Character setup adds a direct entry point; costume Open is retained. Config plain-source compatibility and batch-proposal boundaries remain.

All four approved E2E scenarios passed (38.6s); focused disposable service/Chromium checks, changed-file syntax checks, final diff review and `git diff --check` passed. Live inference/render checks were not requested or run. Resource existence and pipeline-specific runtime inputs remain compiler concerns; validation here establishes source structure/view compatibility. No implementation packet remains pending.
