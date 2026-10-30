# Local testing

## Story animation opening (2026-10-30)

All four approved fast scenarios passed (`npm.cmd run test:e2e`, 38.4s).
A disposable Chromium check under ignored `test-results/animation-open/` passed
animation creation, ID-bearing list/read/save responses, reopening without a
duplicate, export-link identity, and opening-error display/retry (6.7s including
startup). No undefined-ID requests or uncaught page errors occurred. JavaScript
syntax and `git diff --check` passed. No permanent tests, live AI calls or normal
library writes were added; the hosted site was not deployed or exercised.

## Character pipeline bulk locks (2026-10-27)

`npm.cmd run test:e2e` passed all four approved scenarios (40.1s). Disposable
checks under ignored `test-results/bulk-locks/` exercised all five real adapters
against temporary catalogs: selected-only publication, already-locked no-op,
other-batch/out-of-view unlock, phase/pipeline/costume isolation, retained
Inventory files, changed-selection rejection and partial-failure reporting.

Two disposable Chromium journeys passed (23.7s), using prepared Assembly/Dressing
responses and imported Body/Head/Head-Image Edit overrides. All five pages passed
single-dialog lock/unlock/relock, cancellation without writes, disabled completed
actions and retained publication checks; the three reference pipelines exercised
two selected views per action. No page errors occurred. Initial disposable runs
needed fixture/import/assertion corrections; the final focused run passed.
Python/JavaScript syntax and `git diff --check` passed. No maintained tests,
dependencies, live AI calls or production-library writes were added.

## UI compliance pass (2026-10-27)

`npm.cmd run test:e2e` passed four approved scenarios (43.2s). Disposable
Overview checks passed local pending/error retention, duplicate submission fencing,
unchanged-poll focus and four viewport bounds; prepared Refinement checks passed
analysis pending/error retention through polling. Syntax and final diff checks
passed. No permanent tests or dependencies were added. The 26-destination capture
reported no overflow at five sizes, but Pipeline Controls failed activation because
the isolated fixture lacks Pipelines.json. See [review register](UI_COMPLIANCE_REVIEW.md)
for page-specific evidence, legacy references and remaining acceptance gaps.

## Minor Character view true-ups (2026-10-27)

`npm.cmd run test:e2e` passed all four approved scenarios (44.1s). Disposable
checks under ignored `test-results/minor-true-ups/` used a private fixture with
prepared render completion. Service checks passed all five view transitions,
explicit preview versus existing selection, revision/current-slot/view/rendered
eligibility, preserved feedback and suggestions, custom-only failed-review
refinement, selected fallback, immutable input bytes and retained Inventory locks.

Chromium reproduced the former disabled controls on an unselected Front image,
then exercised the real service/router with the updated controller for all five
views: Continue enabled from the preview, retained edits, Try these changes,
single-canvas render payloads, carried selection, reload and unchanged direct
Style refinement. No page errors occurred. The 390px guidance screenshot was
inspected; this focused fixture does not establish full shell/device acceptance.
Python AST, JavaScript syntax and `git diff --check` passed. No maintained tests,
dependencies, live AI calls, production-library writes or deployment were added.

## Character pipeline template edit routing (2026-10-27)

`npm.cmd run test:e2e` passed all four approved scenarios (44.5s). A disposable
Chromium check with prepared responses passed five master-edit actions across
Body Reference, Head Image, Head Image Edit and Costume Dressing: each called the
shared Template Editor entry with the current canonical source path rather than
the saved proposal path, without popups or page errors. JavaScript syntax checks
for both changed controllers and `git diff --check` passed. No permanent tests,
dependencies, live AI calls or production-library writes were added.

## Minor Characters status recovery (2026-10-27)

`npm.cmd run test:e2e` passed all four approved scenarios after the final controller
changes (43.0s). A disposable Chromium check under ignored `test-results/` passed
failed-poll retry/error clearing, rejected-mutation refresh without repeating the
write, and delayed-poll fencing against newer mutations. The controller also
passed these checks with local/session storage and IndexedDB access denied; no
uncaught page errors occurred. JavaScript syntax and `git diff --check` passed.

Production inspection found a workspace-lock timeout during autosave and an
interrupted submission. The reported browser storage error was not reproduced
or attributed. Prepared-response checks establish browser recovery behavior,
not resolution of the underlying lock contention or live rendering. No permanent
tests, dependencies, live AI requests or deployment were added.

## Minor Characters console errors (2026-10-27)

`npm.cmd run test:e2e` passed all four approved scenarios (37.4s). A disposable
Chromium check under ignored `test-results/minor-character-console/` reproduced
the reported line-428 null listener with the previous controller's removed
`mc-side` binding. The current controller passed list/create/rename/reload and
six-tab checks against the private fixture without `Assets.json`, legacy asset
requests or page errors. Both controller syntax checks and `git diff --check`
passed. No maintained tests, live AI calls, production-library writes or deployment
were added.

## Character and costume template editor (2026-10-26)

`npm.cmd run test:e2e` passed all four approved scenarios (38.6s). Python AST checks for the changed compiler/service/routes and `node --check` for `zet.js` and `template_editor.js` passed. Disposable checks under ignored `test-results/template-editor/` used private copies of the approved fixture and no live AI calls.

Service checks passed canonical full-file loading, repeated-line view addressing, inherited defaults, canonical-only/exclusion/head-domain/spatial rules, rendering-mode union and validation, valid/malformed image-reference syntax, located diagnostics, invalid-save byte preservation, stale-master rejection, current-disk/final-newline diff, CRLF preservation, foreign-template rejection and plain-source compatibility. Chromium checks passed the actual character/costume entry points, dimmed-line edits, case-insensitive search, literal HTML-like content, native caret/undo across controls, read-only diff/full-file switching, invalid/conflicting saves, reload protection, edits made while Save is pending, stale analysis response fencing, and desktop/narrow textarea/decoration width/height/wrapping/scroll alignment without page errors. Screenshots were inspected; an inherited global `pre` height cap was found and corrected before the final browser pass.

These checks establish editor/software behavior. They do not validate live render quality, referenced-image availability, every pipeline-specific input or production deployment. No maintained tests/scenarios, dependencies, seed files or production-library data were changed.

## Costume suggestion source binding (2026-10-26)

`npm.cmd run test:e2e` passed all four approved scenarios (41.9s). Disposable
prepared-response checks under ignored `test-results/suggestion-binding/` passed
section/line/digest addressing, repeated lines within/across sections, protected
head/resource/scene content, stale IDs, prose-only and spatial validation,
24 view/mode scope cells, asymmetric mirror defaults, one repair attempt,
partial success/provider failure, empty findings, cancellation/supersession before
repair, legacy findings and shared Character.md validation.

The existing disposable costume lifecycle check was adapted to return catalog IDs
and passed all-view mode preparation, two four-seed private rounds, render and
assessment retry, diff/revision approval, costume-only save and replay. An isolated
Chromium check passed source section/line labels, scope controls, desktop/narrow
containment and existing trial/checklist/mode/staging controls without page errors.
Changed Python AST, JavaScript syntax and `git diff --check` passed. No permanent
tests, dependencies, live inference or production-library writes were added.
These checks establish software contracts, not live model/image quality or
production deployment. See [ADR 0035](DECISIONS/0035-costume-suggestion-source-binding.md).

## Costume-Dressing modes and source adjustments (2026-10-26)

`npm.cmd run test:e2e` passed all four approved scenarios after integration (37.8s and 39.6s). A final focused invocation of the approved character-to-costume scenario passed (13.0s) after the staging provenance and pre-normalization mode-filter fixes. Changed Python AST checks, three JavaScript syntax checks and `git diff --check` passed. No permanent test, scenario or dependency was added.

## Post-render criteria and suggestion feedback (2026-10-26)

Trial-viewer follow-up: all four approved fast scenarios passed (41.1s). Disposable
prepared-response Chromium checks passed image expansion, button/keyboard navigation,
end boundaries, per-trial frozen prompt display, Escape/Close, thumbnail focus restoration,
and 390px layout containment. The narrow screenshot was inspected. Python AST,
JavaScript syntax and `git diff --check` passed; no permanent tests or live AI calls were added.

`npm.cmd run test:e2e` passed all four approved fast scenarios (38.2s). Disposable service checks verified two-item persistence/reload, row-specific validation and atomic rejection. A prepared-response Chromium check verified blank-new-row omission, retained input and invalid-row marking after a server error, unsaved-criteria guidance, suggestion progress/empty/error states, and a delayed poll not overwriting a newer criteria save. Changed JavaScript syntax and `git diff --check` passed. No permanent test or dependency was added. No live inference or production-library write occurred.

Ignored disposable checks under `test-results/costume-adjustments/` verified all supported view/mode compiles and ordered inputs; independent readiness; explicit-source blocking; view/mode line partitioning and production compiler annotation filtering/source maps; shared criteria/revisions; two four-seed rounds with stable seeds; render and assessment failure/selective retry; exact diff approval; costume-only master save/replay; retained earlier trial images; unchanged gallery counts; existing Assembly Character.md analysis; costume rename; staging alternatives and failed-stage workspace preservation; frozen slot/runner retries; circular lineage rejection; cancelled sessions; and retired continuation dispatch fencing.

Isolated Chromium exercised real mode saving/reload, the staging menu, criteria saving and the review/diff/four-image controls with prepared responses. Desktop and 390px screenshots were inspected; there were no uncaught page errors or page-width overflow. The fixture server used port 8767 and was stopped afterward. These checks establish software contracts, not live model quality, production deployment or physical-device acceptance. No live inference or normal-library writes occurred. See [the implementation plan](../plans/completed/costume-post-render-adjustments.md) and [ADR 0033](DECISIONS/0033-costume-post-render-adjustments.md).

## Prompt Generator rotation modes (2026-10-25)

`npm.cmd run test:e2e` passed all four approved scenarios twice (39.1s, final
39.6s). Changed Python AST checks, both changed JavaScript syntax checks and
`git diff --check` passed. Existing disposable guided-cycle checks also passed
five rounds for Doll-dressing and Head-Image Edit, including reassessment,
selective retries, stale revisions and late-result fencing.

Disposable isolated checks passed all eight existing Stage Rotation handoffs and
source/overlay guards, then compared a Rotate Pilot baseline with the staged prompt
and ordered image hashes. Pilot checks covered compiler facts, reference roles,
separate mode sessions, legacy file/hash preservation, invalid modes, frozen resume
after recipe changes, failed/successful restart, concurrent opens, prepared baseline
and trial cycles for both modes, replay, adoption provenance and corrupt-byte rejection.
An actual rotation template declaration survived source-map extraction and froze
analysis-only bytes without changing renderer bindings. Isolated catalog publication
retained Rotate mode, edit-base/orientation roles and source-view identity.
No live AI/render execution or normal-library writes were used.

Isolated Chromium exercised the actual batch mode dialog with an unrendered target,
Doll-dressing default, cancellation, source label, mode-specific resume, reload,
history and Rotate restart. Screenshots were inspected at desktop and narrow widths;
dialog containment passed and there were no uncaught page errors. Disposable evidence
is under ignored `test-results/pilot-rotation/`. No permanent scenario was added.

## Guided Prompt Generator Pilot (2026-10-24)

`npm.cmd run test:e2e` passed all four approved fast scenarios (39.6s) after the guided-cycle integration, using a verified Python 3 interpreter via `ZET_TEST_PYTHON`. The approved scenarios remain regression coverage rather than pilot-quality coverage. No permanent tests or scenarios were added. Changed Python compilation, both changed JavaScript syntax checks and `git diff --check` passed.

Disposable prepared-response checks exercised both pilot pipelines through five rounds, criteria reassessment without replacement rendering, separate saved human corrections, direction/draft/image/evaluation failures and selective retries, exact prompt history, stale revision rejection, archive/restart, adoption without selection/locking, and a deliberately blocked evaluator returning after archive. A read-only copy of the real Tsaeytte legacy session retained all four images/reviews/notes and its failed-draft diagnostic; the source file remained unchanged.

Isolated Chromium exercised setup through baseline/evaluation/review, autosave and reload, immediate busy feedback, read-only prompt popup, criteria reassessment/history, next-round direction approval, draft rejection/regeneration/approval, the next image round and archive/restart. Screenshots were inspected at 1440×900, 1920×1080 and 390×844; image-left/review-right proportions and page-width containment were asserted. The new browser page had no uncaught JavaScript errors. Evidence is disposable under ignored `test-results/guided-pilot/`.

These checks use temporary library records and prepared responses, not live AI/render execution. They do not establish artistic success or production deployment. See [Local Characters](COMPONENTS/LOCAL_CHARACTERS.md#prompt-generator-pilot-2026-10-24) and [ADR 0032](DECISIONS/0032-guided-prompt-generator.md).

## Tsaeytte costume rear-view improvement (2026-10-24)

`npm.cmd run test:e2e -- --grep character-to-costume` ran and passed all four
approved fast scenarios in 38.8 seconds. A private text-only compile passed for
all eight Tsaeytte Costume-Dressing views with the updated library source,
template, orientation text, and compiler guidance. Its audit found no conditional
visibility clauses in the emitted image prompts. Python syntax, JSON parsing,
and `git diff --check` passed. The private evidence packet verified 44 frozen
controls before source edits and all 41 unchanged controls afterward. Diagnostic
AI_Proxy renders and Joe's visual review are recorded in the
[active plan](../plans/active/tsaeytte-costume-fix.md); these checks do not
constitute a selected or locked production image.
The completed diagnostic screen used all 36 authorized renders (30 AI_Proxy,
six imagegen). Two direct BACK renders of the updated compiled prompt still
ended above the boot cuffs. The final BACK source clarification requiring full
cuff coverage passed text compilation but has no live render check under this cap.

## Independent Head-Image Edit (2026-10-22)

`npm.cmd run test:e2e` passed all four approved scenarios; the final run took
39.3s. S2 remains legacy Assembly/Dressing regression coverage. No maintained
scenario, dependency, live inference or deployment was added.

Disposable checks passed 16 new all-view generation/analysis compiles and eight
byte-identical legacy prompts before/after separate authoring. Isolated services
verified independent runs/locks, FRONT-based progression, accepted operation
source maps, slot/staging bindings, both locked and selected-batch Assembly source
choices and refresh, guided finishing/adoption/ancestry, text-only follow-up and
stale-guide refusal. Isolated AI_Proxy preparation covered text FRONT and two-image
BACK; no worker executed these requests. Actual Chromium checks verified both
pages, Assembly selectors, guided finishing click/reload, 1280px/390px containment
and no page errors. Screenshots were inspected. Changed Python/JSON/JavaScript
syntax and `git diff --check` passed.

Adult Tsaeytte's appended block preserves the original bytes and all 26 legacy
sections. These checks establish implementation contracts, not live image quality.
See [the completed plan](../plans/completed/head-image-edit.md) for observations,
resolved disposable-check issues and limits, and
[Local Characters](COMPONENTS/LOCAL_CHARACTERS.md#independent-head-image-edit-2026-10-22)
for operator behavior.

## Repo-managed Qwen guidance and LLM roles (2026-10-22)

`npm.cmd run test:e2e` passed all four approved scenarios initially (44.4s) and after final integration changes (40.8s). The final run emitted the existing nonfatal Windows usage-maintenance file-sharing warning. An intervening invocation correctly refused the disposable browser fixture's occupied port; the owned fixture was stopped before the successful final run. No maintained scenario was added; the queue fixture now supplies an explicit skill-free role.

Disposable checks passed 371 request cases across role/provider/operation/publication variants, imported-source hashes, original request/schema/options/image preservation, appropriate modules despite analysis-only attachments, missing-file/invalid-role/operation failures, updated versus frozen instructions, role-model inheritance, Config TOML save/clear, complete cards and AST caller inventory. Actual isolated Chromium controls verified all 25 cards, Qwen indicators, popup selection, override save/reload/clear, Template Editor loading, no browser errors and containment at 1280px and 390px. Screenshots were inspected under ignored `test-results/qwen-ui/`. Changed Python AST, JavaScript syntax and `git diff --check` passed.

These checks establish prepared-request integration and UI behavior, not live model adherence, image quality, production deployment or physical-device behavior. No live inference, normal-library writes, dependencies or permanent tests were added. See [LLM roles](COMPONENTS/LLM_ROLES.md) and the [completed plan](../plans/completed/qwen-llm-roles.md).

## Costume rotation staging (2026-10-21)

`npm.cmd run test:e2e` passed all four approved scenarios (41.5s). Disposable
isolated checks passed all eight Dressing rotation handoffs, ordered labels and
bytes, single edit-base contract, accepted template overlays, source-batch file
immutability, no inference, invalid/missing/rejected/foreign/self sources,
unsupported pipelines, universe isolation and unchanged generator board on failure.
Chromium clicked the actual BACK_LEFT Stage Rotation button and verified prompt,
45-degree source note, reference labels, img2img mode, 832x1216 dimensions, empty
board and persistence after reload. Python AST, both changed JavaScript syntax
checks and `git diff --check` passed. No maintained tests or dependencies changed.

Read-only preparation of Joe's Tsaeytte example resolved the selected LEFT_PROFILE,
matching BACK_LEFT Assembly, embroidery and rear jewelry in order. The source
image's shorter rear hem differs from the authored ankle-length specification;
the new prompt gives authored construction precedence. These checks establish
staging/compilation behavior, not live rendered fidelity. No production restart,
deployment, live inference or modification of the existing generator session was
performed. See the [completed plan](../plans/completed/costume-rotation-staging.md).

## Costume Dressing no-reference staging (2026-10-25)

`npm.cmd run test:e2e -- --grep "character-to-costume"` passed all four approved
fast scenarios (38.7s). Disposable compiler checks exercised all eight view prompts
with a prepared active template revision, confirming the matching Assembly image
was attached and no previous costume view was added. A disposable BACK staging
service check verified Image Generator reference packaging and rejection of
conflicting modes before workspace replacement. The new browser click path and
missing-snapshot failure path were not exercised in Chromium. Python AST, both
changed JavaScript syntax checks, and `git diff --check` passed. No permanent tests,
live AI calls, or normal-library writes were used. See [Local Characters](COMPONENTS/LOCAL_CHARACTERS.md) and the
[completed plan](../plans/completed/stage-no-costume-ref.md).

## Character review latency checks (2026-10-20)

The approved four-scenario suite passed in 42.5s after the shared path-conversion
and character projection changes. Disposable checks verified complete before/after
response equality for the reported 64-candidate Assembly batch, review save/reload
in a temporary copy, portable-path guards and per-walk freshness, Body BACK recipe
defaults, and asset-filter behavior with denied browser storage. Python/JavaScript
syntax and diff checks passed. A symlink retargeting check was unavailable because
Windows denied symlink creation. No maintained scenarios were added. See the
[completed plan](../plans/completed/character-review-latency.md) for measured service
timings and limits; production browser click timing and the exact reported console
error remain unverified.

## Template-edit publication and deployment recovery (2026-10-20)

`npm.cmd run test:e2e` passed all four approved scenarios twice (51.2s and
47.9s). The final run emitted a nonfatal Windows fixture usage-maintenance
file-sharing warning. No maintained scenario or dependency changed.

Disposable repositories and mocked GitHub delivery verified snapshot/stale-preview
fences, staged/unstaged and unrelated blockers, CRLF handling, three-way upstream
preservation/conflicts, uncertain PR responses with one retained branch/PR,
validation checkpoint reuse, normal/squash merges, local/target changes, later
release receipts, final pre-stop rejection, and startup rollback preserving old
template bytes. Route-wiring checks verified request/error codes; a copied
controller loaded outside the repository and a second process could not acquire
the promotion fence. These checks do not publish to GitHub or stop real processes.

Prepared-response Chromium checks exercised diffs, selection, publication progress,
close/reopen, PR links, merge refresh, unrelated blockers and ready actions at
1280/800/390px. Mounted dashboard checks at 1280/390px used the actual controls and
prepared deployment responses; actual isolated development APIs rejected every
publication endpoint. Screenshots were inspected under ignored
`test-results/template-publication/`. A pre-checkout clone check, mobile dialog
overflow and CRLF diff-check handling were corrected during disposable validation.
Python/JavaScript syntax and `git diff --check` passed. Live host credentials,
actual GitHub delivery, physical iPad use and production promotion remain
unverified; the first-install handoff is documented, not performed. See
[the recovery workflow](GitHub_Task_Workflow.md#accepted-template-edits-and-update-recovery).

## Character Image Generator staging (2026-10-20)

`npm.cmd run test:e2e` passed all four approved scenarios (45.9 seconds).
Disposable isolated checks compared all 32 Body/Head/Assembly/Dressing view inputs
and eight FRONT/BACK matched-seed workflow graphs, including prompt text, ordered
reference bytes and render settings. They also checked uploaded Head FRONT,
unchanged run spec/state, selected/pending result detachment, reference-limit/missing
image failures, cross-universe rejection, no inference on staging and Retry retaining
the saved configuration/seed. Chromium checks passed on all four source pages for
both modes, replacement of old content, reload persistence, return-to-source button
availability, navigation cancellation and delayed-upload fencing. An initial browser
check exposed the return-to-source disabled button; it was fixed and the check
passed. Two JavaScript syntax checks, six Python AST checks and `git diff --check`
passed. No maintained tests, dependencies or live inference were added. These checks
establish prepared-job equivalence, not live rendered image quality.

## Compact image cards and review (2026-10-20)

`npm.cmd run test:e2e` passed all four approved scenarios in 42.6 seconds after the
presentation changes. Six changed JavaScript files passed `node --check`;
`git diff --check` passed. No maintained scenario, dependency or backend contract
was added. An initial passing run emitted a nonfatal Windows fixture
usage-maintenance sharing warning; the final run did not.

Disposable Chromium checks used isolated fixture storage/prepared responses and
browser projections: actual three-candidate Assembly review/polling and Narrative
render/select/reload; all four character pipeline card states, image-less details,
long/missing/stale/failed Luna advice, prompt defaults and focus; Inventory
copy/fullscreen, Generation controls, Minor Character comparison and standalone
refinement. Desktop, 1133x560 and 390x844 checks included coarse-pointer sizing,
control/overflow bounds and inspected screenshots. A representative desktop card
shrank from 583.7px to 491.9px against identical data. Physical iPad acceptance and
separate populated journeys through every shared fullscreen consumer remain
unverified. See the [completed plan](../plans/completed/site-wide-image-cards.md)
for actual checks, corrected disposable-check setup errors and scope limits.
No live inference, production data writes or deployment occurred.

## Governing-template review UI (2026-10-20)

`npm.cmd run test:e2e -- --grep character-to-costume` passed the approved S2
scenario (20.4 seconds including startup). Disposable service/API/Chromium checks
verified eight-view master skips for Body, Head and Assembly without model calls;
separate-window proposal saving and refreshed diffs; unchanged active inputs and
master bytes until explicit use/promotion; current-master restart without the old
overlay; checkbox-column layout, selected acceptance and bottom FRONT continuation.
Stale editor/version saves and stale active-version skip requests were rejected.
Polling preserved editor text; desktop, 800px and 390px bounds passed and screenshots
were inspected. A follow-up changed button rows to wrap at their natural widths.
Python AST, both changed JavaScript syntax checks and `git diff --check` passed.

These checks used the private fixture library/queue and prepared text responses.
Only the fixture character master was promoted; project templates and normal
library data were unchanged. No maintained scenarios, dependencies, live inference
or production deployment were added. Early disposable-check failures exposed
fixture limitations (FRONT-only prerequisite locks, newline normalization, retained
source/job state) and a transient-message assertion; the corrected check passed.
See the [completed plan](../plans/completed/governing-template-review-ui.md).

## Responsive dashboard and image input (2026-10-19)

The local implementation and acceptance limits are tracked in the
[active UI plan](../plans/active/ipad-responsive-ui-and-style-consistency.md);
[Dashboard UI](COMPONENTS/DASHBOARD_UI.md) owns the conventions and capture command.
The existing four fast scenarios passed in 41.1 seconds after repairing S1's
navigation to use the visible compact selector or desktop tabs. Scenario count and
authoring purpose are unchanged. The initial S1 timeout on the now-hidden desktop
Overview button was retained in ignored `test-results/ui-responsive`; S2–S4 passed
in that initial run. A later passing run emitted a nonfatal Windows file-sharing
warning for fixture usage-maintenance state; no warning suppression or backend
change was made.

Disposable Chromium checks used only isolated fixtures and prepared responses:

- Twenty-five destinations at five viewport sizes had no horizontal overflow in
  the final capture reports. Pipeline Controls had an activation error because
  the fixture lacks legacy `Pipelines.json`; its captures establish only partial
  layout. Several other pages had empty/prerequisite data, not populated journeys.
- Three actual local candidates exercised review at 1133×610, 1133×560, 390×844,
  and 1440×900: viewport bounds, gallery return, candidate navigation, and polling
  with unsaved decisions and expanded details preserved.
- Prepared Narrative synthesis/render/selection, reloaded image-first viewing,
  direction disclosures, and review bounds passed. Image Generation viewer
  layout/protection messaging used browser-only prepared board responses at three
  sizes; standalone refinement checks inspected HTML/CSS, not adoption/model work.
- Mocked clipboard image/empty/denied reads passed through actual Head source and
  generation-reference handlers. Browser helper checks covered nested file inputs,
  disabled controls, and discarding reads after context changes. Shell/menu bounds
  passed at 1100/1101/1133/1360/1361/1440 pixels with long labels and visible utilities.

Native iPad clipboard permission/Photos behavior and physical-device viewport
acceptance remain unverified. A prepared Image Generation backend submission hit
an existing `AdHocImageGenerationService._preset` AttributeError (`self.app`);
that backend file is unchanged, and no render success is claimed for that check.
No new maintained scenarios, dependencies, live inference, production-library
writes, external submissions, or deployment were added.

## Character prompt review and image refinement (2026-10-18)

Ordering follow-up: disposable checks verified that all four character preview lists follow the actual progression stages and every declared same-batch reference precedes its target. Review guidance contains the authoritative stage schedule. All 33 preview/render comparisons and reference-validation checks still passed; the approved character-to-costume S2 scenario passed in 15.8 seconds including startup. Python AST and `git diff --check` passed. The runtime scheduler was already correct; no live AI execution or maintained test additions were needed.

Conditioning follow-up: disposable isolated checks passed exact preview/render prompt comparisons for all 32 Body/Head/Assembly/Dressing pipeline/view combinations, uploaded Head FRONT, alternative rear-right BACK inputs in all four pipelines, future inputs before batch images exist, and an accepted costume edit with a separate snapshot path. New body proposals upgraded an inherited obsolete input clause while preserving another edit and the original parent bytes. Production compilers rejected missing/declared references; traditional Body compilation rejected images; the frozen-input guard rejected preview references. `npm.cmd run test:e2e -- --grep "character-to-costume"` passed S2 (18.6 seconds). Python AST and `git diff --check` passed. No maintained tests, live inference or production data changed. See the [conditioning fix plan](../plans/completed/body-reference-preview-conditioning.md).

`npm.cmd run test:e2e` passed all four maintained scenarios in 48.9 seconds. S2 now supplies a prepared text-only prompt report, accepts the batch version and explicitly opens FRONT before its existing Assembly/Dressing render/select/lock task. Front-only runs use one seed per actual candidate. No maintained scenario or dependency was added.

Disposable isolated prepared-response checks passed all 32 pipeline/view text previews; five-stage generation and exact same-side references for all four pipelines; no-change/selective acceptance, rejected/overlapping corrections, stale master refusal and unchanged masters; image-only comparison choices, custom-only edits after failed advice, one-base correction payloads, frozen render replay/retry, occupied-slot adoption, unchanged published bytes, retained attempt history and warning-only downstream choices. AI Queue refinement navigation was checked separately. Desktop and 800px Chromium journeys passed prompt-checkbox persistence/reload, feedback preservation, acceptance/Continue readiness, and FRONT/front-left/front-right refinement, chosen comparisons, adoption and reload. Screenshots were inspected; narrow layout had no horizontal overflow. Python AST, changed JavaScript syntax and `git diff --check` passed.

These checks used disposable libraries, queues, indexes, prepared images and model answers. They did not run live inference, render real artwork, deploy production code or establish image quality. Broader real-model fidelity remains an operator trial.


AI job repair validation (2026-10-16): the four maintained fast scenarios passed
in 33.4 seconds. The shared prepared-envelope helper now uses protocol terminal
status `SUCCEEDED`; its scenario purpose is unchanged. Disposable isolated checks
passed for read-only inspection, disk discovery by an existing collector, two OS
processes collecting one answer, interrupted image/receipt commits, transport vs.
worker failure, image/cancellation admission, deterministic follow-up identity,
reconstruction replay, a render waiting beyond its caller deadline, and mixed
Image Generation/Assembly/Minor Character work. An intentionally failing legacy
collector did not block a registered handler. No live inference or production
deployment was performed, and no permanent scenario was added.

Zet maintains exactly **four fast Playwright task scenarios** and **one separately invoked live Narrative check**. This is the validation owner for the agent knowledge base. The recovered commits `b3d695a`, `3f6acbe`, and `257fdeb` retired the former Python/browser suites and GitHub Actions gates in favor of representative local tasks. See [AGENTS.md](../AGENTS.md) and the [delivery workflow](../.github/CODEX_WORKFLOW.md). Old test paths in tickets refer agents to this baseline; they are not instructions to recreate deleted tests.

Fast fixtures keep operational storage in a process-unique temporary root outside
the Git checkout, as the production TaskWorkflow guard requires. The E2E server
removes only that exact temp directory at shutdown; it never uses normal Zet
AppData, queue or index roots.

Minor Characters (2026-10-15) were verified with disposable prepared-response service/browser journeys, including selected versus locked views, nonblocking advisory review, source/candidate comparison and Inventory handoffs. Those checks are not maintained scenarios. All three approved scenarios passed (26.7s); see the [completed plan](../plans/completed/minor-characters-workspace.md) for evidence and scope limits.

Scene and story coverage uses `/narrative`, `/api/narrative`, and `NarrativeStories`. Scene Builder and local scene-batch execution are retired; their offline archive has no maintained scenario. Passing the baseline is not evidence of every subsystem contract or live rendering quality.

## Minor Character alignment validation (2026-10-15)

The current style alignment -> selected style -> independent view alignment -> selected view -> true-up workflow passed disposable prepared-response service/API and Chromium journeys. Checks cover one-reference short prompts, selection/lock gates, same-slot repeated carry, recipe-only undo and alternate corrections, regeneration after undo, reload, review failure, immutable publication, stale revisions/late results, excluded retired records, comparison looping, main navigation and feedback edits during an in-flight autosave. Desktop and 800px screenshots were inspected. These scripts/artifacts remain ignored under `test-results`; no maintained scenarios were added.

`npm.cmd run test:e2e` passed all three existing scenarios in 27.7 seconds. Python AST checks, `node --check` for the changed dashboard scripts, and `git diff --check` passed. This establishes isolated software behavior, not live image quality; no live model/render calls or production deployment were performed. See [ADR 0015](DECISIONS/0015-minor-character-alignment.md) and the [completed plan](../plans/completed/minor-character-alignment.md).

## Approved fast scenarios

All four are implemented in [fast.spec.mjs](../tests/e2e/fast.spec.mjs). The S1–S4 names below are navigation labels for those existing scenarios, not extra tests.

| Label / exact test title | User task and assertions | Scope limit |
| --- | --- | --- |
| S1 — `library and narrative authoring save and reload through the dashboard` | Upload/restore the Traveler character template; edit/restore costume name; save story title, scene setting, and element appearance; reload and display the reference image; inspect persisted source files | Uses seeded library images/records. Does not cover every catalog operation, merge, migration or universe lifecycle |
| S2 — `character-to-costume workflow previews prerequisites and creates a real run` | API preview/create/start a front-only Character-Assembly run; deliver a prepared image response; wait for ranking; select/lock; repeat for Costume-Dressing using the assembly prerequisite and verify costume availability | Seeds Body/Head locks and uses one front candidate. Does not generate Body/Head batches or test all views, ranking comparisons, cancellation or recovery |
| S3 — `narrative interview, prompt, render, retry, and final assembly persist` | Dashboard interview proposals, review/Apply and synthesis; render backdrop/subscene; fail and retry a subscene render; select/lock sources; add assembly layers, synthesize/render/select/lock final assembly; reload and verify story summary/image availability | Prepared text/image answers exercise persisted job/application flow, not actual LLM synthesis, image quality, or every provenance/protection case |

S4 — `unified AI queue collects all universes in the background and shares model selection`
was explicitly approved on 2026-10-16. It submits prepared Codex/Ollama work across
Test/TestOther universes, verifies automatic queue loading and filtering, leaves
source pages while collection runs, checks durable history after reload, and verifies
popup mutual exclusion/vision filtering plus server-side capability rejection.
No real AI execution occurs. Fixture envelopes preserve original request bytes and
include terminal output inventories.

The suite mixes browser actions, API calls, and filesystem assertions. In particular S2 is primarily API-driven; do not describe it as a complete browser journey through every character control. [CODE_MAP.md](CODE_MAP.md) maps capabilities to these scenarios and their gaps.

## Commands and prerequisites

Run the default suite with:

```powershell
npm run test:e2e
```

On Windows, `npm.cmd run test:e2e` avoids PowerShell script-policy restrictions. Its pretest setup uses `npm ci` when the locked Playwright packages are missing and installs Chromium only when the matching browser executable is absent. Browser downloads use Playwright's shared user cache, while npm packages are installed into the current checkout or worktree. [package.json](../package.json) calls [run-e2e.mjs](../Scripts/run-e2e.mjs) and [playwright.config.mjs](../playwright.config.mjs), which run only `fast.spec.mjs` on Chromium with one worker, a 90-second scenario timeout, 8-second default assertion timeout, and port **8765**. Each run writes to a unique folder under the system temp directory's `Zet-test-results/<checkout-name>/`; `ZET_TEST_RESULTS_ROOT` overrides that parent path. Successful runs delete their folder; failed runs retain it for diagnosis. The local-front helper has a bounded 70-second poll. Reuse of an existing server is disabled; keep suites serial across worktrees and resolve port conflicts before rerunning.

The bootstrap removes only the lifecycle-exported `npm_config_allow_scripts`
override (including case and hyphen variants) from its nested `npm ci`
environment, allowing npm to read script policy directly from `.npmrc` or
`package.json`. It preserves the remaining environment, including `userconfig`,
cache, registry, and other script controls. npm 11.16 rejects that environment
override for project installs even when the original setting came from `.npmrc`;
see [npm's lifecycle export bug](https://github.com/npm/cli/issues/9912).
Do not work around this failure by enabling all scripts, editing allowlists, or
changing locked dependencies.

On 2026-10-13, disposable clean projects running npm 11.16.0 reproduced the old
helper's `EALLOWSCRIPTS` failure. The repaired helper passed cold and warm lifecycle
bootstraps with user `.npmrc`, project `.npmrc`, and `package.json` policies, plus
an uppercase/hyphen environment override. Package manifests, lockfiles, and
configuration files stayed unchanged. The approved `npm.cmd run test:e2e`
baseline then passed all three scenarios in 28.2 seconds using verified Python
3.14.6 through `ZET_TEST_PYTHON`. These bootstrap checks are disposable, not new
maintained scenarios. Issue #46's worker validation receipt at `1c21be2` remains
failed until the repair is integrated into that worktree and its helper validation
is rerun; the passing checkout baseline does not replace that receipt.

On 2026-10-13, directly bootstrapping the failed staged release `8917920` also
passed; its approved `npm.cmd run test:e2e` baseline then passed all three scenarios
(26.3 seconds). This validated staging only; production promotion was not retried.

Use an existing verified Python 3.11+ runtime, project packages, Node, Playwright and Chromium. The configs call `python3 -B tests/e2e/server.py`; verify that interpreter before running. The pretest setup restores only dependencies pinned by `package-lock.json` and the required Chromium browser; it does not change dependency declarations. There is no routine pytest, coverage, lint/type-check, or GitHub Actions test command in the current baseline.

## Fixture and response boundaries

[server.py](../tests/e2e/server.py) copies [tests/library](../tests/library/README.md) into the selected results root's `narrative-e2e/<mode>/` at process startup. The seed owns `Test/universe.json`, `seed.json`, Traveler character/costume sources, reference images, and prepared response images. It is never written back from a run. App construction seeds Narrative records through real services and creates valid Body/Head batch specs and locks; fixture-only `/__test/*` routes are added by this server, not production routes.

Before each fast scenario, `/__test/reset` replaces the Narrative story and resets the Traveler local lock/batch state and File Proxy folders, then reseeds prerequisites. The app, Test universe, and entity catalog persist within the run; this is **not a full database rebuild per scenario**. S1 restores the source template/costume edits it makes. Library/queue paths are disposable; the derived index uses a separate temporary directory outside Git with exit cleanup. Producer-local queue routes/receipts are keyed by the disposable queue path, distinct from the normal queue.

The server suppresses Ollama catalog refresh and supplies prepared local-prompt observations. Fast helper functions deliver prepared envelopes and images into the private File Proxy folders. Narrative envelopes include proxy-result inventory and an external-consumer harvest marker; local-pipeline answers use their own reconciliation path. This exercises packaging, persistence and supported result application without running the external dispatcher, Ollama, Codex, or ComfyUI. It does not independently prove all readiness, ownership or stale-result rejection branches.

Failure traces are retained under the failed run's `playwright` folder. `/__test/retain-failure` copies the Test library, queue, and fixture config to its `narrative-e2e/failures/scenario-<number>-<title>/`. Inspect these plus terminal output before rerunning; another run uses a separate folder.

To inspect the seed in a separate dashboard process and port, run:

```powershell
npm run test:library
```

This opens `http://127.0.0.1:8766/narrative` against an inspection copy. Stop the server with `Ctrl+C`.

Inspection uses the selected results root's `narrative-e2e/inspection`, not the normal library. It shares port 8766 with the live check; do not run both at once.

## Optional live Narrative check

The live check is separate and is never part of the fast suite:

```powershell
$env:ZET_LIVE_TEST_ENABLED = "1"
$env:ZET_LIVE_TEST_NARRATIVE_MODEL = "your-installed-ollama-model"
$env:ZET_LIVE_TEST_CHECKPOINT = "your-installed-comfyui-checkpoint"
# Optional when ComfyUI is not at its default address:
$env:ZET_LIVE_TEST_COMFYUI_URL = "http://127.0.0.1:8188"
npm run test:e2e:live
```

It preflights the Zet and AI Proxy Python runtimes, the configured Ollama model, and the ComfyUI service/checkpoint. It starts AI Proxy with a run-local registry, runtime configuration, and private queue; normal AI Proxy configuration and queues are not changed. Prepared backdrop and subscene inputs keep the live portion focused on real final-assembly prompt synthesis and rendering. Its overall timeout defaults to 20 minutes and can be changed with `ZET_LIVE_TEST_TIMEOUT_MS`. Missing prerequisites block the live check; Joe reviews artistic quality.

[playwright.live.config.mjs](../playwright.live.config.mjs) selects only [live.spec.mjs](../tests/e2e/live.spec.mjs), port **8766**, one worker, 30-second assertions, and the selected results root's `playwright-live`. The server expects sibling `AI_Proxy` with its existing `.venv` runtime; it starts a private File Proxy process with external ComfyUI and records `narrative-e2e/live/ai-proxy.log` under that root. The check verifies final synthesis/render completion, selection/lock, reload and displayed/published image. It skips when the explicit enable flag or preflight requirements are absent; **skipped means unverified, not passed**. Run only when Joe requests this live check, and follow the existing ComfyUI operating instructions.

## Coverage policy

Joe explicitly approves each new test, scenario, or material coverage expansion. The approval must identify the user task and why the existing scenarios are insufficient. Existing tests can be repaired to preserve their approved purpose. Do not add exhaustive cases, snapshots, coverage targets, test frameworks, or dependencies without that approval.

Shared reconstruction/true-up (2026-10-15) has no maintained scenario. Ignored disposable prepared-response checks exercise intent-aware reports, original-source render exclusion, corrections/retry, three-view wizard publication, front replacement, selected-result ancestry and stale selection. A disposable browser check exercises both new controls and resume/dirty-field behavior. These checks use isolated storage/prepared models and images; Freydis's actual identity/style quality requires separate visual acceptance. Maintained S1–S3 remain unchanged.

For a change, locate the relevant S1–S4 assertions, run the approved baseline, and inspect uncovered contracts in authoritative code. Do not add tests for retiring Scene Builder/local scene-batch workflows. Plan/test references must distinguish scenario coverage from source-only verification. [DEVELOPMENT.md](DEVELOPMENT.md) records actual command outcomes; [ADR 0004](DECISIONS/0004-local-task-testing-baseline.md) records the policy change.

The existing `/narrative` test links redirect into the mounted dashboard editor. The approved S1–S3 scenarios retain their purpose. The 2026-10-12 retirement used separate disposable/manual migration and Candidates checks; these are not additional maintained tests. No live rendering was performed.

## Narrative interview review checks (2026-10-13)

S3 now verifies that a prepared interview leaves the narrative unchanged until Apply, then
continues its existing prompt/render/assembly journey. The maintained scenario count and
purpose are unchanged. Disposable backend checks used a copy of Group Photo JSON records,
checking review validation, old-reply normalization and exact replay schema, selected apply/
reject/override/Shared behavior, repeat application and first-mention reference bindings.
Original source record hashes remained unchanged. Prompt prose checks used prepared text;
they do not establish live LLM fidelity or rendered height/pose accuracy.

Disposable Chromium checks covered row defaults, explicit choices versus all three bulk actions,
pending-review reload/polling/close/reopen, Shared override clearing, override Save inputs and
collapsed indicators. Prompt comparison checks included unsaved edits, reversion, generated
replacement, reload, an open image review, missing prompts, local crop/reuse and line endings.
Desktop/narrow screenshots were inspected; comparison text contrast was checked after correcting
an inherited code-block color. These scripts/screenshots are ignored `test-results` artifacts,
not additional maintained scenarios. No live model or render services were used.

## Approved disposable slot-fix checks (2026-10-12)
Joe approved four one-time check groups for reported issues: costume batch-link restoration, card containment, current-prompt/Recompile behavior, and overlapping slot actions. The disposable fixture used a separate Test library/private queue, prepared images and rankings, and no live models. All groups passed, including Image Generation containment at 1365/850/640 pixels and preserving an unsaved review choice while images arrived. Scripts/results are ignored `test-results` artifacts, not new maintained scenarios. The approved S1–S3 suite remains unchanged and passed afterward (3 tests, 23.0 seconds). See the [completed plan](../plans/completed/standard-render-slots.md) for limits and exact observations.

## GitHub workflow validation (2026-10-13)

The maintained S1–S3 purpose and count are unchanged. Fixture configuration explicitly
uses Runtime.Role=development. ZET_TEST_PYTHON optionally selects a verified staged
release interpreter for the same baseline. Disposable checks cover capture/retries,
claims/trusted replies/quota, browser attention and two-instance deployment recovery;
these do not create a permanent suite. Worker validation and deployment staging share
a fixed-port check lock outside Git. No live check was run. See the active workflow
plan for exact observed results and remaining real pilot/promotion gates.

Worker validation streams directly to its ignored log. Its timeout stops only the
owned command process tree, avoiding a descendant-held output pipe blocking recovery.
A disposable parent/child timeout check verified retained output and a failed
revision checkpoint. Windows sandbox cleanup may require the saved automatic review
for this exact isolated check; three printed scenario successes without successful
runner completion are insufficient to mark a PR ready.

The real sandbox pilot exposed physical queue-state and compiler-config leaks in
the old fixture. build_app now sets the active fixture config and a fixture-only
queue-state root. Compiler script helpers honor that active config; normal queue
state paths remain unchanged without the test override. Worker validation keeps
locked npm/browser caches inside ignored test-results and selects its own verified
Python environment. These repair the approved scenarios without adding coverage.

## Recovery fixture state (2026-10-17)
Fast/live fixture configurations set Runtime.Root to the disposable fixture's
Runtime directory. Storage-health identities, recovery leases and continuation
metadata therefore do not share normal application recovery state. The existing
local-response helper copies the original ask's attempt ID; scenario purposes and
counts are unchanged. Disposable outage checks are recorded in
[Development](DEVELOPMENT.md#storage-recovery-verification-2026-10-17).

## Simplified Assembly validation (2026-10-20)

`npm.cmd run test:e2e -- --grep "character-to-costume"` passed S2 (11.6 seconds including setup); `npm.cmd run test:e2e` passed all four maintained scenarios (37.8 seconds; final rerun after compiler/error-message adjustments: 38.2 seconds). Python AST, changed JavaScript syntax and `git diff --check` passed. The existing S2 helper bypasses governing-template review for Assembly and still exercises that review for Dressing. No maintained scenarios or dependencies were added.

Disposable isolated checks passed all eight Assembly compile/preview/prepare contracts, replacement of legacy three-image manifests and accepted overlays, preservation of current prompt edits and frozen Retry inputs, suppression of supplemental tags, two-image Image Generator staging, all five Continue stages without acceptance/recipes, and BACK publication with only body/head dependencies while FRONT is unselected. Captured multi-candidate Luna requests verified ranking-only FRONT numbering/guidance and portable provenance, plus absent/rejected/missing FRONT cases. Chromium checks verified enabled Assembly Continue, hidden governing/anchor/recipe/BACK controls, rejected template-write API, retained Body review UI and no browser errors. These prepared checks establish software behavior, not live artistic quality; no live model/render calls or production data were used.

## Assembly Run all views validation (2026-10-20)

Focused S2 passed (`npm.cmd run test:e2e -- --grep "character-to-costume"`, 13.3 seconds); all four approved fast scenarios passed (`npm.cmd run test:e2e`, 41.1 seconds). Disposable checks used the real Assembly runner with prepared render completion and evaluation dispatch: all eight views ran without selections, an old FRONT-only stage queued seven missing views, interrupted resume skipped the existing FRONT image, explicit single-view execution stayed bounded, whole-batch rerun targeted all requested views, and stop/other-pipeline review fences remained. Chromium verified that Run all views dispatches all eight targets in one action and Assembly's batch picker contains no stage/prompt-review labels, with no browser errors. Python/JavaScript syntax, final diff review and `git diff --check` passed. No permanent tests, dependencies, production data or live AI calls were added.

## Assembly front ranking validation (2026-10-20)

This supersedes the earlier same-day Run all views behavior. Focused S2 passed
(`npm.cmd run test:e2e -- --grep character-to-costume`, 13.7s); all four approved
fast scenarios passed (`npm.cmd run test:e2e`, 40.2s), using verified Python 3.14.6.
Changed Python AST, JavaScript syntax and `git diff --check` passed.

Disposable isolated checks exercised the real Assembly runner with prepared render
completion: FRONT-only dispatch, the required human selection pause, then seven
remaining views with exactly the matching body/head render inputs. Captured Luna
requests verified comparison numbering after reference deduplication, proportionality
priority and FRONT provenance. Invalid/missing/rejected/outside-run FRONT images
were refused; selection changes retained downstream choices while staling advice;
late results could not commit against a changed FRONT. Legacy recovery, advice
without comparison provenance and FRONT-only whole-batch restart were checked.
Mounted Chromium verified Run front, disabled Run remaining before selection,
polling after API selection and seven-view dispatch with no page errors.

No maintained tests, dependencies, production library writes or live AI calls were
added. These checks verify software behavior; improved artistic proportionality
ranking remains subject to live human review. See the
[completed plan](../plans/completed/assembly-front-ranking.md).

## Code review remediation (2026-10-22)

All four approved fast scenarios passed after the remediation (`npm.cmd run
test:e2e`, 38.7 seconds). Changed Python files compiled, `node --check
zet/web/static/zet.js` passed, and `git diff --check` passed. Disposable checks
covered valid/malformed universe selection plus failed-write preservation; allowed,
traversal, absolute-outside and foreign-universe path resolution; descriptive
Head-Image Edit lock labels; one-row inventory paging; bounded two-query entity and
variant descriptor projections; pre-commit catalog rollback; committed and
uncommitted publication recovery; and duplicate continuation enqueue suppression.
These checks used temporary directories/catalogs and prepared data. They did not
exercise live model/render services or add permanent scenarios.

## Narrative scene text (2026-10-29)

The four approved fast scenarios passed (43.8s) after correcting an initially invalid browser event handler. Disposable Python checks under ignored `test-results/scene-text/` passed persistence/reload, stale save/confirmation rejection, formatting/shapes/overflow and original-byte preservation. A disposable Chromium journey passed manual candidate dragging, saved placement, keyboard resize, fullscreen entry/exit, tablet/narrow image bounds, confirmation, finished-image retrieval, lock and universe-style preview/save (9.5s including startup). Screenshot inspection covered the candidate editor and formatted bubble. No maintained tests, dependencies, live models or normal-library writes were added. Physical touch/pen input, fullscreen denial and exhaustive failure injection remain unverified.

Final scene-text integration rerun: all four approved scenarios passed (42.2s); final disposable Chromium journey passed (7.8s including startup). Changed Python/JavaScript syntax and diff checks passed. See plans/completed/narrative-scene-text.md for earlier corrected failures and verification limits.

## Finished scene-text editing and universe settings (2026-10-29)
All four approved fast scenarios passed (38.8s). Disposable service checks passed persistence, stale confirmation, original-byte preservation, locked mutation rejection and all available four-face fonts. Disposable Chromium passed draft/final saving, lock/unlock/re-edit, overflow recovery, clean view and combined universe-settings save/reload with Comic Sans MS (9.5s). Python AST, JavaScript syntax and diff checks passed. No permanent tests, live AI calls or production data writes were added. See plans/completed/scene-text-finish-settings.md for limitations.
