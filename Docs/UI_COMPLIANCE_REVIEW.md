# Dashboard UI compliance review

Reviewed 2026-10-27 against [UI style guide](UI_STYLE_GUIDE.md).
Implementation plan: [UI alignment](../plans/active/ui-style-guide-compliance.md).

## Evidence and interpretation

This is a bounded alignment pass, not certification of every interaction. The isolated fast fixture captured 26 destinations at 1920×911, 1133×610, 1133×560, 1024×640 and 390×844. All captures reported zero horizontal overflow; Pipeline Controls activation failed at every size. A disposable DOM audit at four requested sizes found no visible unnamed buttons in the active dashboard sections. This check is not a complete accessible-name, contrast or keyboard audit.

The 2026-10-28 console-remediation follow-up has begun. Costume-Dressing now
renders per-view saved mode/prerequisite/reference readiness and preserves
unsaved settings through polling. The populated Valindia Loungewear batch on
release `fb1f2d38` shows completed-state copy, but the mixed-ready and unsaved
mode journeys remain open. On release `efd20ed8`, Assembly’s completed batch
still exposes stale FRONT-first tooltip text even though a direct fetch of the
static script matches the corrected local source. The page keeps referencing
the prior script URL; its query version is bumped locally to force a fresh fetch
in the next release. Full page interaction checklists remain open in the
[active plan](../plans/active/console-error-remediation.md).

Evidence is under ignored `test-results/ui-compliance-before/` (baseline capture metadata/screenshots) and `test-results/ui-compliance/` (disposable DOM audit and auxiliary captures). Captures are revision/dirty-state stamped. Baseline captures may overlap early local edits; they are not a pristine before/after comparison. The desktop contact sheet was inspected. Empty/prerequisite pages do not establish populated-state acceptance. Earlier responsive-plan evidence remains historical.

Guide references below: §2 foundations; §3 controls; §4 local feedback; §5 cards; §6 dialogs; §7 forms/navigation. **Verified with exceptions** means the stated checks passed, with the listed limits; it does not mean the whole page complies. A blank finding is not permission for speculative cleanup.

## Active page inventory

Main dashboard page identifiers resolve through `zet.js:canonicalDashboardPage` and `activatePage`. Shared markup is in `zet/web/templates/index.html`; shared presentation in `zet/web/static/zet.css`. All rows below received source/navigation inspection and initial-layout browser inspection unless marked otherwise.

| Page / entry | Presentation owner | Guide / result | Findings, changes and remaining exceptions |
| --- | --- | --- | --- |
| Overview `onboarding`; shared shell navigation and production summary | `zet.js` | §2–4,7; verified with exceptions | Initial fixture summary fits. Same-context failure retains timestamped counts, exposes retry and shows retry-pending feedback; a disposable browser check also confirms counts clear on context change and an older failed request does not replace the new context. Phone References still targets legacy `assets` (Batches); expression metric remains despite retired expression destination. Full upload/error lifecycle not exercised here. |
| Body-Reference `local-body-reference`; Assets menu | `local_asset_pipeline.js`, `local_template_improvement.js` | §2–7; partial populated inspection | Shared controls receive pressed acknowledgement; publication/rerun/master-update confirmations use the application dialog. Populated Valindia batch `20261028_062917_803930` inspected at 1920×911 and 390×844; all eight selected views were locked and no horizontal overflow appeared. Prompt acceptance/skip, both FRONT entry points, remaining widths, dialogs and the interaction checklist remain open; screenshots were viewed but not saved as files. |
| Head-Image `local-head-image`; Assets menu | same shared pipeline owners | §2–7; partial populated inspection | Valindia batch `20261028_064432_920373` inspected at 1133×610 (document 1118×2176); all eight candidates selected and locked, and the lower view-action rows were inspected. No horizontal overflow. Prompt acceptance paths, selector freshness, review errors, other widths and full interaction checklist remain open. |
| Head-Image Edit `local-head-image-edit`; Assets menu | same shared pipeline owners | §2–7; partial populated inspection | Completed Valindia survey batch `20261028_154319_195916` inspected at 1133×610 (document 1118×13484); all eight selected views are locked, derived views show the selected FRONT reference, and per-view prompt links are present. Frozen context was confirmed for the bounded Refine analysis. Full-page/other-width captures, analysis failure recovery and full interaction checklist remain open. Default capture inventory still omits it. |
| Character-Assembly `local-character-assembly`; Assets menu | same shared pipeline owners | §2–7; partial populated inspection | Valindia batch `671d96a45d6b4476b5e8dca9b92e5b80` inspected at 1133×610 previously and at 1905×855 on release `efd20ed8` (document 1905×1743, no horizontal overflow). The completed control still gives stale FRONT-first tooltip advice. Direct static fetch matches corrected local source; browser caching is a working explanation, not confirmed. The script query version is bumped locally; deploy and live recheck are pending. Review dialog, other widths and full checklist remain open. |
| Costume-Dressing `local-costume-dressing`; Assets menu | same shared pipeline owners | §2–7; partial populated inspection | Full-page populated Valindia Loungewear batch inspected at 1920×911, 1133×610, 1024×640, and 390×844, plus a scrolled 1133×560 viewport; no horizontal overflow. Latest release `fb1f2d38` shows completed-state copy beside “No unrendered views ready” and directs the user to review saved per-view mode/reference settings. Mixed readiness, unsaved mode/save states, dialogs, coarse pointer, keyboard, contrast, zoom/reflow and reduced-motion checks remain open. |
| Minor Characters `minor-characters`; character navigation/Tools | `minor_characters.js` | §2–7; partial populated inspection | Populated four-card list and Galen editor inspected at 1133×610 and 390×844. Galen Slot 1 remains selected/locked with its existing suggestion; the authorized Slot 2 remains ready/unselected, with its review kept separate. Full viewport/checklist and other populated journeys remain open. |
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
| Batches `local-batch-status`; toolbar | `local_batch_status.js` | §2–4,7; partial populated inspection | Summary reads carry running views without loading full details. Prepared populated refresh and injected failure retained same-universe rows, showed pending/stale feedback, and kept retry available. Live 1133×610 page showed 13 rows in two groups (document 1118×1272); normal refresh retained rows while pending and then settled. Failure/retry, long-status/keyboard and context-switch browser checks remain open. |
| Config `local-image-config`; Tools | `zet.js` | §2–4,7; partial populated inspection | Live 1133×610 page showed populated project automation, 25+ managed roles and ComfyUI settings (document 1118×5103). Process table showed Zet Web Dashboard and Auto Harvester, two PIDs each and duplicate count 0; read-only PID inspection found parent-child pairs, but the common launcher identity was unavailable. No process action or setting edit was made. Other widths, raw-PID detail accessibility, coarse-pointer sizing, contrast and full checklist remain open. |
| Pipeline Inspection `pipeline-inspection`; Tools | `zet.js` | §2–4,7; verified with exceptions | Empty inspection panel fits; populated diagnostics not exercised. |
| Pipeline Controls `pipeline-controls`; Tools | `zet.js` | §2–4,7; blocked | Fixture lacks Traveler/Adult/Pipelines.json. Partial screenshot must not count as successful activation. Do not invent a compatibility pipeline to make this page pass. |
| Manuals `help`; Help menu | `zet.js` | §2–4,7; verified with exceptions | Initial manual content fits. Every download/content variant not exercised. |
| Local Character Overview `/local-character-overview`; Tools button | `local_character_overview.html` | §2–5,7; verified with exceptions | Replaced private dark palette with shared light tokens, wrapping actions and responsive cards. Added per-slot pending/outcome text, per-slot repeat-action guard, stable unchanged polling and focus restoration. Disposable checks passed pending/error retention, single submission, unchanged-poll focus and four viewport bounds. Narrow screenshot inspected. Actual generation/stop completion not exercised. |
| Refinement `/local-character-refinement`; pipeline action | `local_character_refinement.html/js` | §2–7; partial populated inspection | Added action-local pending/error/accepted statuses beside analysis, generation and adoption/retry controls. Prepared contextual browser check passed local analysis pending/error retention through polling. Live Valindia FRONT_LEFT_3_4 Refine route at 1133×610 (document 1118×2244) showed the selected image, seven checked comparisons and the completed M2 advisory beside correction/render controls; no draft or new action was submitted. Actual failure/retry, draft preservation, generation/adoption, other widths and full modal/keyboard acceptance remain unverified. |
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
