# Standard render slots
Status: complete
Related specification: approved conversation plan, 2026-10-12

## Goal and desired behavior
Body-Reference, Head-Image, Character-Assembly, Costume-Dressing and Image Generation use eight fixed slots, automatic updates during review, and consistent Generate / Select / Unselect / Clear / Regenerate / render Retry actions. Character creation retains FRONT and other-view counts (1–8, defaults 8/4). Supplemental generation fills empty slots only. Preserve pipeline-specific review, ordered inputs, immutable locks, universe isolation and user changes.

## Current behavior and impact
Local character adapters merge spec/state candidates; the shared browser polls but stages updates behind Refresh and pauses in review. Image Generation stores jobs server-side but slot assignments in browser storage. Narrative already updates live and remains independent.
Owners: local image policy/workflow, Body/Head/Assembly adapters, local router, evaluation/recovery consumers, ad hoc generation service/router, dashboard JS/template/styles. Affected knowledge: architecture, local characters, queues, data model, invariants, code map; durable design ADR.

## Luna sized work packets
Each packet is sequential, single-agent, preserves existing edits, and runs git diff --check. The maintained baseline is unchanged; Joe separately approved the four disposable follow-up checks recorded below. Live services remain unrequested.

| Packet | Responsibility / files and interfaces | Dependencies | Acceptance / validation | Status |
| --- | --- | --- | --- | --- |
| WP1 | render_slot_service; local_image_pipeline_policy: durable slot maps, merged added candidates, legacy compatibility | none | Eight stable positions; no historical loss; inspect atomic persistence | implemented |
| WP2 | local_body_reference_service: limits, active candidate merge, targeted render inputs | WP1 | Supplemental Body renders preserve anchor requirements; inspect creation/resume | implemented; source inspection |
| WP3 | local_head_image_service: same contract, frozen Head inputs | WP1–2 | Preserve FRONT source and review retry; inspect packaging | implemented; source inspection |
| WP4 | local_character_asset_pipeline_service: Assembly/Dressing integration | WP1–3 | Preserve sources, costume qualifier, selections; approved S2 | implemented; source inspection |
| WP5 | local_image_workflow_service/router, evaluation/recovery summaries | WP2–4 | Atomic slot actions, persisted target IDs, late-result fencing, full-view ranking; approved S2 | implemented; source inspection |
| WP6 | local_asset_pipeline.js, template/styles, shared slot presentation | WP5 | Fixed grid and review actions; JS syntax | implemented; source inspection |
| WP7 | local_asset_pipeline.js polling | WP6 | Automatic updates preserve focus and dirty review/observations; JS syntax/source inspection | implemented; source inspection |
| WP8 | ad_hoc_image_generation_service/router | WP1/5 | Universe-owned workspace, child states, recovery/browser import; inspect persistence | implemented; source inspection |
| WP9 | zet.js Image Generation, template/styles | WP6/8 | Count control and common actions; JS syntax and fast suite | implemented; source inspection |
| WP10 | affected docs/ADR and this plan | all | Approved npm.cmd run test:e2e, final diff review, record gaps | complete; approved baseline and disposable checks passed |

## Invariants and defaults
Keep unique candidate identities independent of slot number. Clear detaches rather than deleting history. Older >8-candidate views keep labeled legacy gallery until capacity fits. Selected/locked images require existing explicit protection transitions. Generate/Regen use the current view prompt with fresh seeds; the Recompile checkbox rebuilds it from current templates before these actions. Retry reuses failed inputs. Separate slots remain usable during rendering; advisory work is fenced/superseded. Ranking never changes slot positions. Empty slots are not automation work.

## Validation boundaries
S2 covers Assembly/Dressing publication and S3 protects Narrative display/retry; Body/Head supplemental renders, dialog updates and ad hoc recovery remain source/manual acceptance gaps. New tests/material expansion require Joe's separate approval. Use isolated approved fixtures only; no live rendering or normal-library validation. Verify Python 3 before commands.

## Progress and decisions
- Planning inspections completed; existing working-tree changes predate this task and must remain intact.

## Observed validation and remaining work
- Verified fallback Python 3 at C:/Python314/python.exe; default Windows python3 alias cannot execute. An ignored test-results/runtime/python3.cmd shim points the approved harness to that interpreter.
- Approved S2 passed (1 test, 8.3 seconds).
- Full approved npm.cmd run test:e2e passed (3 tests, 23.4 seconds), after core integration.
- Python compilation, JavaScript syntax checks and git diff --check passed so far.
- Restricted-network browser setup failed; sandbox escalation allowed the approved pinned setup/suite. No dependencies added, no live rendering, no normal-library validation.
- Initially, additional acceptance checks were unapproved and unrun. Joe subsequently approved the four follow-up checks below; no permanent tests/scenarios or live checks were added.
- Final Python compilation, JS syntax checks (local_asset_pipeline.js, zet.js, render_slots.js), and git diff --check passed. Final full approved suite passed again: 3 tests, 24.8 seconds. A later presentation-only patch for source/advice refresh passed JS syntax/diff checks; it does not affect baseline API/Narrative assertions.
- Source/diff review completed for changed services, routes and presentation. Existing user changes were preserved; no tests, dependencies or live-service calls added.
- Discovered dependencies: added definitions must survive mutable rerun resets; recovered gate collectors must finish their evaluation and capture each view's callback arguments; Body ranking requires finished gate eligibility. These fixes are limited to supplemental/recovered review behavior.
- Image Generation saves planned child seeds before dispatch and persists each published ask. Interrupted/unsubmitted children fail visibly and retain replay inputs. Results remain bound by child index; workspace selection/mapping survive restart.
- Joe’s follow-up approval covers the four reported issue checks. They are complete; no approval is pending for this task. Full Body/Head generation and general restart recovery remain documented coverage limits, not unfinished implementation.

## Final results
Implementation complete, including Joe’s follow-up corrections. The full approved fast suite passed (3 tests, 23.0 seconds). Four separately approved disposable checks passed for batch URLs, layout, prompt/Recompile behavior, and overlapping slot actions. Image Generation containment passed at 1365/850/640 pixels. Source parsing, JS syntax and final diff checks passed. No live model/render calls, normal-library validation, dependency additions or maintained test additions. Full Body/Head generation/general recovery remain outside maintained coverage. See ADR 0007.


## Reported issues and follow-up packets (2026-10-12)
Joe reported overflowing buttons, lengthy labels, costume batch URLs showing no gallery, whole-batch slot lockout, and ambiguous prompt/Recompile behavior. Joe approved four disposable checks for these issues: deep-link loading, containment, prompt behavior, and overlapping actions. No live rendering or maintained test files are authorized.

- WP11 — local_asset_pipeline.js / zet.css: restore costume before capturing context, wrap controls, use Regen; dependencies none; acceptance deep-link opens requested batch and buttons stay inside cards; validation approved disposable browser checks and node --check.
- WP12 — render_slot_service.py / local workflow/router: independent per-slot submission/collection, clear fences running candidates; dependencies WP11; acceptance other slots remain usable and late answers cannot replace current membership; validation approved isolated prepared-response checks.
- WP13 — adapter view prompt inputs and browser Recompile controls: Generate/Regen use current view prompt, optional recompilation affects these actions, Retry replays saved inputs; dependencies WP12; validation approved prompt checks.
- WP14 — recovery/docs/approved baseline: persist pending slot work, preserve legacy run execution and locks; dependencies WP12/13; validation npm.cmd run test:e2e, syntax/diff review, record exact results and remaining earlier coverage gaps.

### Follow-up results
WP11–WP14 complete. Costume restoration now updates the context key before loading batch results. Both card types constrain images and wrap controls; Regen matches Narrative’s label. Independent character slot collectors persist work, publish new asks while other slots run, and fence cleared candidates. Image Generation also accepts independent slot actions and Regen uses current inputs. Generate/Regen use the current view prompt, optionally recompiled; Retry preserves the failed inputs. Already submitted asks are immutable.

Observed commands: `node test-results/slot-acceptance.mjs` (all four approved check groups passed, with prepared render/rank responses), `npm.cmd run test:e2e` (3 passed, 23.0 seconds), `node --check` for changed browser files, verified Python 3 compilation, `git diff --check`. Disposable scripts/screenshots/logs stay under ignored `test-results`; the maintained S1–S3 suite is unchanged. Initial disposable-script failures came from waiting for visibility of a deliberately collapsed gallery and checking a character locator after navigating away; both harness errors were corrected, and the final run passed.
