# Dashboard UI compliance review

Reviewed 2026-10-27 against [UI style guide](UI_STYLE_GUIDE.md).
Implementation plan: [UI alignment](../plans/active/ui-style-guide-compliance.md).

## Evidence and interpretation

This is a bounded alignment pass, not certification of every interaction. The isolated fast fixture captured 26 destinations at 1920×911, 1133×610, 1133×560, 1024×640 and 390×844. All captures reported zero horizontal overflow; Pipeline Controls activation failed at every size. A disposable DOM audit at four requested sizes found no visible unnamed buttons in the active dashboard sections. This check is not a complete accessible-name, contrast or keyboard audit.

Evidence is under ignored `test-results/ui-compliance-before/` (baseline capture metadata/screenshots) and `test-results/ui-compliance/` (disposable DOM audit and auxiliary captures). Captures are revision/dirty-state stamped. Baseline captures may overlap early local edits; they are not a pristine before/after comparison. The desktop contact sheet was inspected. Empty/prerequisite pages do not establish populated-state acceptance. Earlier responsive-plan evidence remains historical.

Guide references below: §2 foundations; §3 controls; §4 local feedback; §5 cards; §6 dialogs; §7 forms/navigation. **Verified with exceptions** means the stated checks passed, with the listed limits; it does not mean the whole page complies. A blank finding is not permission for speculative cleanup.

## Active page inventory

Main dashboard page identifiers resolve through `zet.js:canonicalDashboardPage` and `activatePage`. Shared markup is in `zet/web/templates/index.html`; shared presentation in `zet/web/static/zet.css`. All rows below received source/navigation inspection and initial-layout browser inspection unless marked otherwise.

| Page / entry | Presentation owner | Guide / result | Findings, changes and remaining exceptions |
| --- | --- | --- | --- |
| Overview `onboarding`; character navigation | `zet.js` | §2–4,7; verified with exceptions | Initial fixture summary fits. Phone References still targets legacy `assets` (Batches); expression metric remains despite retired expression destination. Record for follow-up, preserve routing. Full upload/error lifecycle not exercised here. |
| Body-Reference `local-body-reference`; Assets menu | `local_asset_pipeline.js`, `local_template_improvement.js` | §2–7; verified with exceptions | Shared controls receive pressed acknowledgement. Initial/prerequisite layout checked; populated review/polling is not established by this capture. |
| Head-Image `local-head-image`; Assets menu | same shared pipeline owners | §2–7; verified with exceptions | Initial layout checked; populated selection, comparisons and errors remain outside this capture. |
| Head-Image Edit `local-head-image-edit`; Assets menu | same shared pipeline owners | §2–7; verified with exceptions | Explicitly added to capture invocation; initial layout fits. Default capture inventory still omits it. |
| Character-Assembly `local-character-assembly`; Assets menu | same shared pipeline owners | §2–7; verified with exceptions | Initial layout checked; approved S2 covers representative prepared selection/publication rather than all review behavior. |
| Costume-Dressing `local-costume-dressing`; Assets menu | same shared pipeline owners | §2–7; verified with exceptions | Initial layout checked; existing checklist-local feedback retained. All modes/trial states not exercised. |
| Minor Characters `minor-characters`; character navigation/Tools | `minor_characters.js` | §2–7; verified with exceptions | Empty list fits. Native deletion/restart confirmations remain; populated comparison/true-up states need further evidence. |
| Identity Keys `identity-keys`; character navigation | `zet.js` | §2,3,5,7; verified with exceptions | Empty preview wells had a separate dark background; shared viewer now uses subtle-surface/muted-text tokens. Mutations not exercised. |
| Turnarounds `turnarounds`; character navigation | `zet.js` | §2,3,5,7; verified with exceptions | Preview-well theme aligned; initial list/preview fits. Creation and publication not exercised. |
| Costumes `costumes`; character navigation | `zet.js` | §2–4,7; verified with exceptions | Existing form fits; source editor routes retained. Wizard populated/error states not exercised. |
| Phase Comparison `phase-comparison`; character navigation | `zet.js` | §2,5,7; verified with exceptions | Seeded paired images inspected; shared viewer palette aligned. All long-name/view combinations not exercised. |
| Image Inventory `auxiliary-resources`; Tools | `zet.js` | §2–7; verified with exceptions | Seeded image cards fit. Import/replacement/organizer dialogs and destructive lifecycle not exercised by capture. |
| Image Generation `image-generation`; Tools | `zet.js` | §2–7; verified with exceptions | Empty slots/settings fit. Live generation excluded. Existing `_preset` backend defect recorded below. |
| Stories `narrative`; story navigation | `narrative.html`, `narrative.js/css` | §2–7; verified with exceptions | Story list fits; control corners aligned to 8px and disabled cursor no longer implies all disabled actions are running. Native image deletion confirmation remains. |
| Candidates `scene-candidates`; story navigation | `zet.js` | §2–4,7; verified with exceptions | Empty source/list layout fits. Imported Adventure Log records and source-change review not exercised. |
| Zines `zine`; story navigation | `zet.js` | §2–4,7; verified with exceptions | Empty list/editor fits. Populated page preview/export not exercised. |
| Universes `universes`; Tools | `zet.js` | §2–4,7; verified with exceptions | List fits; selection/deletion not exercised. |
| New Universe `universe-create`; New/list action | `zet.js` | §2–4,7; verified with exceptions | Form fits; filesystem creation excluded from visual capture. |
| Universe Settings `universe-settings`; universe list | `zet.js` | §2–4,7; verified with exceptions | Existing settings form fits; persistence/errors not exercised. |
| Template Editor `template-editor`; Tools/contextual master-edit actions | `template_editor.js` | §2–4,7; verified with exceptions | Empty editor fits. Existing draft/stale-response guards retained; populated diff and save-conflict behavior not revalidated in this pass. |
| AI Queue `ai-controls`; Tools | `ai_queue.js`, `ai_model_picker.js` | §2–4,7; verified with exceptions | Empty queue/table fits. Native delete confirmation remains. S4 supplies representative queue/model behavior. |
| Batches `local-batch-status`; toolbar | `local_batch_status.js` | §2–4,7; verified with exceptions | Empty batch list fits; populated long-status rows not exercised. |
| Config `local-image-config`; Tools | `zet.js` | §2–4,7; verified with exceptions | Forms and role groups fit. Compatibility/retired role section explicitly says settings do not enable retired workflows; retain it. |
| Pipeline Inspection `pipeline-inspection`; Tools | `zet.js` | §2–4,7; verified with exceptions | Empty inspection panel fits; populated diagnostics not exercised. |
| Pipeline Controls `pipeline-controls`; Tools | `zet.js` | §2–4,7; blocked | Fixture lacks Traveler/Adult/Pipelines.json. Partial screenshot must not count as successful activation. Do not invent a compatibility pipeline to make this page pass. |
| Manuals `help`; Help menu | `zet.js` | §2–4,7; verified with exceptions | Initial manual content fits. Every download/content variant not exercised. |
| Local Character Overview `/local-character-overview`; Tools button | `local_character_overview.html` | §2–5,7; verified with exceptions | Replaced private dark palette with shared light tokens, wrapping actions and responsive cards. Added per-slot pending/outcome text, per-slot repeat-action guard, stable unchanged polling and focus restoration. Disposable checks passed pending/error retention, single submission, unchanged-poll focus and four viewport bounds. Narrow screenshot inspected. Actual generation/stop completion not exercised. |
| Refinement `/local-character-refinement`; pipeline action | `local_character_refinement.html/js` | §2–7; verified with exceptions | Added action-local pending/error/accepted statuses beside analysis, generation and adoption/retry controls. Prepared contextual browser check passed local analysis pending/error retention through polling. Actual generation/adoption and full modal/keyboard acceptance remain unverified. |
| Post Render Adjustments `/local-character-prompt-improvement`; pipeline action | `local_character_prompt_improvement.html/js` | §2–7; not exercised (populated) | Source reviewed: criteria/suggestion statuses already local; general errors/outcomes still use page message. Direct entry lacks required context. Retain existing draft/revision fences. |
| Task capture/attention; shell and auxiliary controls | `task_capture.html`, task controllers/CSS, `auxiliary_task_context.js` | §2–4,6,7; not exercised (submission) | Shared controls receive pressed response. External submission excluded; native screenshot permissions and all attention states not established. |

## Legacy and reachability register

| Reference | Source/caller evidence and classification | Impact / follow-up |
| --- | --- | --- |
| `assets`, `manifest`, `expressions`, `scene-appearances`, `local-image-review` | `canonicalDashboardPage` redirects to Batches; old sections/listeners remain in index/zet.js. Compatibility destinations, not active standalone workspaces. | Do not restyle retained unreachable sections as active pages. Consumer audit required before removal. |
| `scene-builder`, `scene-batches`, `stories`, `scenes`, `render-console`, `render-review` | `canonicalDashboardPage` redirects to Narrative. Retained Render Console API/controller names are not evidence of an active UI. | Preserve compatibility links. Scene workflows belong to Narrative; no revival or backend cleanup in this pass. |
| `local-overview`, local Identity/Turnaround/Costume/Comparison aliases | Canonicalize to Overview or corresponding active character destination. | Intentional aliases; not obsolete solely because they lack separate markup. |
| Prompt Review `prompt-review` | Remains in `PRODUCTION_PAGES`, activation and `zet.js` task action near the end of the controller. Production menu selectors have no matching current index markup. | Contextual/direct-link compatibility UI, absent from primary navigation. Content and downstream Render Console links need a dedicated workflow ownership decision. Not certified or removed. |
| Phone Overview “References” | `renderCharacterPhoneViewer` targets `assets`, which canonicalizes to Batches. | Potentially misleading destination. Record only under the agreed legacy-reference boundary. |
| Overview Expressions count | `renderCharacter...` summary still displays `expression_count`; expression page redirects to Batches. | Historical data metric may be valid, but editing destination is retired. Clarify intended product meaning separately. |
| Local stub/Coming Soon markup | `local-stub-page`, `placeholder-page` remain in index; active local aliases mostly canonicalize before display. | No demonstrated normal navigation entry. Trace consumers before deletion. |
| Prompt Generator Pilot | Current component/code-map documentation records retirement; no active Pilot template or entry found in web template/controller search. | Historical references do not authorize restoration. No active experiment was inferred from historical notes. |
| Local Character Overview | Explicit Tools button and handler navigate to its standalone route. | Active and reachable; distinct from the `local-overview` alias. |
| Refinement/Post Render Adjustments | `local_asset_pipeline.js` constructs their contextual URLs with run/view information. | Active contextual pages, not orphaned merely because absent from Tools. |
| Image Generation `_preset` | Current `AdHocImageGenerationService` stores `self.zet_app`, while `_preset` references `self.app.config`. | Source confirms the previously reported attribute mismatch remains. Backend repair is outside this presentation pass; do not claim render submission acceptance. |
| `new_pallet.css` | No web source reference found in targeted search. | Candidate unused experiment/style asset; usage outside web sources unresolved. Preserve pending separate cleanup authority. |

## Follow-up acceptance gaps

Populated auxiliary workflows, imported Candidates/Zines, full action lifecycles, contrast measurements, comprehensive keyboard/modal checks, native task capture and physical iPad/Safari remain unverified. Browser confirmations cannot keep failed actions open with custom local errors as prescribed by §6; replacing each safely requires its own bounded workflow repair. No new modal framework or broad controller rewrite was introduced.

Do not archive the implementation plan as fully compliant while required checks remain pending. No routes, API schemas, storage formats, dependencies, service eligibility or creative records were changed.

## Observed validation

- `npm.cmd run test:e2e`: four approved scenarios passed (43.2s). An earlier invocation refused an occupied fixture port; the owned inspection fixture was stopped before the successful run.
- Disposable Overview browser check: local pending/error retention, one submission, unchanged-poll focus and four viewport bounds passed after final controller changes. Prepared responses only, no creative writes.
- Disposable Refinement contextual browser check: local pending/error retention across polling passed, no page errors. Prepared responses only.
- JavaScript and Overview inline-script syntax checks passed. An intermediate encoding/syntax error in the edited standalone template was corrected before the successful browser checks; the approved E2E suite alone does not cover that template.
- Capture evidence is initial-state evidence, not complete workflow acceptance. Pipeline Controls remains fixture-blocked. Physical-device behavior remains unverified.
