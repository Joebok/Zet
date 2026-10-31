# Draft and Final rendering across Zet
Status: complete

## Goal
Implement the user-approved draft/final rendering plan: configurable 1,048,576 and
4,194,304 pixel targets, aspect-ratio sizing, independent mode selections and
locks, dependent references, bulk cleanup, clear UI indicators, and selective
backup across every active image workflow. Existing images are drafts and existing
Inventory entries remain intact. No permanent tests or live model calls.

## Implementation packets
1. ConfigService, PipelineControlService, Config UI and shared sizing policy.
2. Shared preparation and AI_Proxy dispatch; freeze submitted settings and retry.
3. Character mode-separated candidate and slot storage; compatibility reads.
4. LocalAssetStore mode locks, reference resolution and final publication.
5. Body and both Head pipelines; mode-separated rendering and selection.
6. Assembly, Dressing and Overview mode propagation and prerequisites.
7. Character refinement and private post-render trials.
8. Narrative generation, composition, reference, selections and lettering.
9. Minor and Quick Character boards, references and publication.
10. Image Generator, reconstruction, true-up and guided generation.
11. Mode-aware controls, dimension previews, cards and reviews.
12. Confirmed mode-scoped bulk cleanup and active-work fencing.
13. Metadata-based backup enumeration, immutable mode names and PowerShell.
14. Architecture, data model, invariants, component docs, code map, ADR and validation.

All implementation packets are complete. Draft cleanup and selective backup use
Joe's confirmed boundaries recorded below. Joe chose logical cancellation for
already-running AI_Proxy work: queued asks are removed and late results from
running asks are fenced. No changes to the separate AI_Proxy project are needed.

## Historical progress and validation
Packet 1 complete: Config reads and persists both settings, Config UI exposes
them, and image_sizing_service implements aspect-ratio sizing. Temporary fixture
load/save/reload and sizing checks passed. The approved E2E suite passed all four
scenarios (42.5s); JavaScript syntax and git diff --check passed. The Config
controls passed a disposable Chromium save-and-reload check using a private fixture.
Packet 2 is in progress. Image Generator's backend accepts an explicit render_mode
and aspect_ratio, saves resolved settings and reuses them for workspace Retry.
Legacy payloads retain their original dimensions. Disposable prepared-submission
checks passed new sizing, configuration changes, frozen retry and legacy inputs.
The approved fast E2E suite passed again (four scenarios, 41.8s).
Config now rejects noninteger or out-of-range targets on load and through the
settings endpoint. A temporary Chromium fixture verified both values survive
save and reload. Image Generator frozen-sizing metadata survived a private
save/read check and invalid render modes were rejected. A further full E2E run
passed (four scenarios, 42.9s) after stopping the owned fixture server that held
port 8765 from the browser check.
Other producers do not yet supply a mode. Packets 3–14 remain pending.
Image Generator cards and review display Draft/Final with requested dimensions;
legacy requests are labeled Draft. Image Generator's frozen sizing is included
in the AI_Proxy ask and prepared render metadata. A disposable manifest roundtrip
confirmed the proxy manifest retains both the sizing metadata and dimensions.
The shared AI_Proxy boundary validates frozen sizing, supplies its dimensions as
overrides, and rejects conflicts. Preparation ignores legacy preset aspect ratios
when sizing is frozen. Disposable checks passed conflict rejection and compiled
a private Qwen workflow with a frozen 2368 × 1760 canvas. Character producers
have not yet been connected to this contract.
The approved E2E baseline passed four scenarios (45.0s); the preset-aspect
handling was additionally checked in the disposable workflow compilation.
Body, both Head pipelines, Assembly and Dressing dispatch now forward an existing
frozen sizing record; preset width/height do not overwrite that record. Shared
character `frozen_input` accepts and validates an optional sizing record while
preserving ordered reference snapshots. A disposable check covered that capture
and invalid-input rejection. The approved fast baseline passed (four scenarios,
45.0s) after the dispatch edits; the optional input helper was checked separately.
No current character producer creates mode-specific sizing records yet, and
character slot, selection and lock actions remain single-mode.
Character input preparation now accepts an optional explicit mode and ratio,
freezing the configured target with the prompt and references. Head defaults to
1:1 and other character pipelines to 2:3. Progression forwards a candidate's
explicit mode/ratio while retaining previously frozen inputs on retry. Disposable
checks passed explicit progression forwarding, retry preservation and costume
input preparation. A disposable Body check also preserved its prompt while
capturing Final sizing. The approved fast E2E baseline passed (four scenarios,
43.4s). Character UI and slot creation do not yet set those fields.
Packet 3 in progress: character detail projects separate `slots_by_mode` and
`selected_views_by_mode` maps. Legacy candidates default to Draft; Body reads
the optional Final maps from its state. Existing actions still operate on Draft;
Final candidate creation, selection and locks are not implemented. Disposable
checks passed legacy/default separation and distinct projected maps.
Character slot creation has mode-specific storage and frozen sizing groundwork;
Draft ranking inputs exclude Final candidates. A private state check verified
Final slot and sizing isolation before adding an availability guard. Final
character slot actions remain disabled: existing batch rerun/selection actions
still operate across candidate modes and could alter another mode's work. Remove
the guard only after those actions and mode-specific selection/locking are fenced
and verified. This temporary integration guard is not a Draft prerequisite.
Body, Head, Assembly and Dressing rerun paths previously derived candidate work
across modes. Other batch and selection actions still need the same audit and
mode scoping, including queued-ask withdrawal and preservation of snapshots.
Draft rerun/view/failed paths now filter candidate work in Body, Head, Assembly
and Dressing; Body and Head ask withdrawal is scoped to Draft candidate IDs.
Private service checks verified Body batch/view, Head batch/view and Dressing
batch/view preserve Final candidate state, Final selection and other-mode asks.
Final selection, lock, other batch operations and mode-aware controls remain
unfinished; the Final integration guard remains in place.
Packet 4 groundwork: LocalAssetStore has distinct mode keys and selection
records, immutable private Draft lock snapshots, and requested-mode locked-source
fallback. Legacy locks resolve as Draft and are not republished. Temporary-library
checks covered separate selections, no Inventory publication, source-change and
foreign-library rejection, legacy locks, fallback, and independent lock snapshots.
These methods are not yet wired into character actions; Final publication still
needs integration with those actions.
`lock_final` now publishes the mode-specific selection through the existing
catalog transaction and recovery journal; mode-specific unlock and clearing
leave the other mode untouched. Disposable temporary-catalog checks passed
Final publication, lock idempotence, selection/source fencing, fallback and
rollback after an injected post-workspace-write failure. These operations are
not yet wired into the character workflow, and Final slots remain guarded.
Mode-specific clearing and unlock preserve the opposite mode and reject clearing
a locked selection. Final publication rollback was rechecked under the enclosing
workspace lock. The approved E2E baseline passed four scenarios (41.5s).
Mode-specific individual character select/lock/unlock actions now delegate to
`LocalModeSelectionService` when an explicit `render_mode` is supplied. A private
fixture verified independent run selections, private Draft locking, Final catalog
publication and scoped unlock; a separate check verified action routing. Legacy
requests retain their existing path. The dashboard, bulk actions, downstream
reference wiring and Final slot creation are not yet enabled.
Assembly/Dressing source resolution now accepts a requested mode, falls back to
the other lock/selection within the chosen source, and preserves source mode in
reference bindings and labels. Existing callers use Draft preference. Private
fixtures verified Final preference, Draft fallback, explicit source-batch choice,
and ordered mixed-mode reference snapshots. Assembly input preparation now passes
an explicit requested mode to that resolver and substitutes its two base source
bindings into the saved prompt manifest without modifying the shared manifest,
batch source snapshots or prompt. Body and Head preparation now project available
same-batch selections with mode preference/fallback and rebind saved references
without changing the shared prompt or reference order. Private checks covered
mixed modes, missing bindings, Final anchors and Draft fallback. Dressing now
resolves its Assembly source per request and reuses a saved prompt and bindings
when available; a private check preserved the prompt, supplemental reference and
shared manifest. Additional checks exercised actual Dressing readiness and
rejected a missing binding manifest without altering the prompt. Final character
slots remain guarded. The approved fast E2E baseline passed (four scenarios,
42.0s) after Dressing integration.
The approved E2E baseline passed four scenarios (42.3s) after these changes.
The approved E2E baseline passed all four scenarios (42.7s); JavaScript syntax
and `git diff --check` passed. No live render was performed.
The approved fast E2E baseline passed all four scenarios (42.8s). A subsequent
private check verified costume-mode selection uses the adapter's normalized
qualifier and remains discoverable. No live model/render checks were run.
Mode-specific bulk lock preview/lock/unlock now operates on the open batch and
selected mode, fences lock against changed selections, and reports per-view errors.
The completion helper can check Draft and Final independently. A disposable
fixture verified coexistence, a stale-preview refusal and scoped bulk unlock.
Dashboard controls, Final slot availability and mode-aware Overview remain open.
The approved fast E2E baseline passed four scenarios (43.0s). Later adjustments
to private-lock snapshot names and relative paths were verified by disposable
temporary-library checks; no live rendering was run.
The approved E2E baseline passed all four scenarios (42.9s) after these changes;
Python syntax and `git diff --check` passed. No live rendering was performed.
The integration guard was checked against a private state file and preserved it;
all four approved E2E scenarios passed (41.9s) after the guard and ranking edits.
The approved E2E baseline passed four scenarios (43.0s); the later selection
projection was additionally checked in isolation. No live rendering was run.
`GET /api/image-generation/sizing` exposes the shared calculation to future
controls; disposable endpoint checks passed square Draft/Final and invalid-ratio
responses. Image Generator options include both configured pixel targets. The
latest fast E2E run passed four scenarios (41.7s), although it started before the
subsequent proxy metadata and sizing-preview edits, so those edits were checked
with disposable manifest/endpoint checks rather than that run.
Packet 10 groundwork: Image Generator now stores a separate Final board inside
its existing workspace document; old boards remain Draft. The workspace API can
read and operate on either mode, with independent slots and selections. Private
checks passed mode-scoped generation, selection, clearing, persistence, and
legacy default behavior. Image Generator now has mode/aspect controls, separate
board switching, and mode-scoped reconstruction reservations with frozen sizes.
Private browser checks passed mode switching and square/4:3 previews; private API
checks passed Draft/Final submissions and distinct persisted boards. A disposable
workspace check passed reconstruction reservation and frozen submission. The
other pipelines and bulk deletion are not complete; live rendering was not run.
Additional checks passed selected-result lookup across modes and scoped staging
reset. The full approved E2E baseline passed after the integration (four
scenarios, 42.9s). No live image-quality check was run.
The approved E2E baseline passed (four scenarios, 40.3s). The isolated server
logged transient storage-maintenance lock contention while the suite ran.
The approved fast E2E baseline passed four scenarios (43.0s) after the mode-aware
bulk lock and Dressing changes. Draft Body and Head anchor resets now restrict
artifact deletion and queue withdrawal to Draft candidates; Draft Body and
Head and Assembly/Dressing remaining-work calculations likewise exclude Final candidates.
Disposable checks confirmed Final selections, candidates, and queued work are
preserved. Character detail now reports slot numbers from each candidate's own
mode. The approved fast E2E baseline passed all four scenarios (40.6s); the
subsequent Head remaining-work filter was verified separately with a disposable
mixed-mode fixture. The Final slot guard remains necessary until the remaining selection,
batch and dashboard paths are integrated and verified.
Character slot prerequisites now use the requested mode's same-batch selections
and Dressing source resolution, including fallback, without mutating shared
sources. Explicit-mode slot candidates persist their captured aspect ratio,
pixel target and dimensions alongside the frozen request. Draft review
collection excludes Final candidates. Newly prepared AI Proxy requests with
frozen sizing use unique `draft_` or `final_` output filenames; legacy and
already submitted jobs retain their names. Disposable checks covered mode
fallback, source isolation, sizing persistence and filename generation. Backup
enumeration still must use lock metadata rather than these filename markers.
Character slot Retry now uses its frozen prompt, references, seed and dimensions
without requiring current upstream selections. A disposable fixture checked this
after changing the requested aspect ratio. A slot request can explicitly reuse a
same-view candidate's seed from the other mode while freezing the current prompt;
the dashboard action remains to be connected. The approved fast E2E baseline
passed all four scenarios (43.5s) after filename and prerequisite changes; the
subsequent retry and seed-reuse changes were checked with disposable fixtures.
Character cards, selected-view summaries and review panels now label their
candidate's mode and show actual image dimensions after the image loads. The
dashboard still needs mode switching, scoped actions and dimension controls.
The approved fast E2E baseline passed four scenarios (40.4s) after the UI and
retry changes. A disposable JavaScript check verified the mode label and its
actual-dimension update; desktop/narrow visual validation remains outstanding.
Explicit-mode selection now rejects human-rejected candidates and invalidates
Draft Assembly's downstream ranking advice when its FRONT selection changes.
A disposable isolated service check verified that behavior and preservation of
the Final selection. The approved fast E2E suite passed all four scenarios
(42.5s), and `git diff --check` passed. Final slot creation remains guarded;
the remaining mode integration and the other packets are still pending.
Legacy whole-batch deletion now refuses batches containing Final candidates,
slots, selections or batch-owned Final asset records until mode-scoped cleanup
is implemented. Legacy character selection rejects Final candidates. A
disposable mixed-mode check exercised all three adapter deletion boundaries,
the guard's independent evidence, and progression selection. These temporary
fences do not replace the planned mode-scoped cleanup or Final integration.
Legacy per-candidate retry also rejects Final candidates before touching files
or Draft review state; disposable checks covered all character adapters. The
four approved E2E scenarios passed (43.4s) after the deletion/selection fences;
the subsequent retry fence was checked separately. `git diff --check` passed.
Character-to-Image-Generator staging now resolves character selections and
Assembly sources with the requested Draft/Final preference, retains reference
mode metadata, and stages the corresponding configured dimensions and pipeline
aspect ratio. This applies to Costume Dressing's normal, no-reference and
rotation handoffs as well. Disposable checks exercised Head and Dressing Final
handoffs, invalid mode rejection, frozen dimensions and source-mode propagation;
no live render was run. Full dashboard mode controls remain pending.
Reference mode metadata now survives Image Generator submission, is validated,
and is cleared when a user replaces or removes the image. A disposable prepared
submission checked persistence and invalid-mode rejection. The approved E2E
baseline passed four scenarios (42.7s) after the staging changes; subsequent
metadata edits were checked separately, along with JavaScript syntax and
`git diff --check`.
Joe confirmed that this code will not be deployed or used until the plan is
complete. The temporary Final slot, whole-batch deletion, and legacy retry
integration blocks described above have therefore been removed. Their removal
does not complete mode-scoped batch actions or cleanup; those remain required
before the plan is finished. Character detail now projects per-mode slot
readiness, including Final's mode-preferred prerequisites, alongside the
unchanged legacy Draft controls.
Disposable checks verified separate readiness and Final slot creation without
changing the Draft slot. The approved fast E2E suite passed all four scenarios
(41.6s), and `git diff --check` passed.
Both explicit-mode readiness projections now use the same mode-preferred
prerequisites as their corresponding submissions, retaining legacy Draft
controls for existing callers. Mode-specific selection and locking share a
candidate eligibility check: the candidate must belong to the requested mode,
view, slot and batch, remain available, and not be human-rejected. Disposable
checks covered mode readiness, rejection, and cross-batch image paths. Dashboard
mode selection and action integration remain pending.
Assembly readiness also resolves the requested mode's source inputs before
reporting a view ready. A disposable check covered missing Draft and Final
sources. The approved fast E2E suite passed four scenarios (42.2s); the last
Assembly readiness change was additionally checked in isolation.
The character dashboard now switches separate Draft/Final slot boards and
selections, submits mode-specific individual and bulk locks, requests configured
dimension previews, and can reuse a seed from the other mode for Generate or
Regenerate. Image Generator staging follows the chosen character mode. Private
Chromium checks covered board switching, dimension previews, submitted Final
mode/ratio/seed, and Final selection without changing Draft selection. The
existing view/batch rerun, review, refinement, cleanup and Overview paths still
need their planned full mode integration; this packet is not complete.
Source-batch summaries now include Final selections, allowing Assembly and
Dressing to offer Final-only batches. Explicit source resolution prefers the
requested mode and falls back within the chosen batch when that image is absent
or rejected, while still rejecting changed-byte evidence. A disposable check
covered Final-only discovery, Final preference, Draft fallback and rejection.
Slot Clear/Regenerate now waits for that slot's submitted render to finish,
preserving queue ownership as part of the planned active-work fencing.
Per-view and batch regeneration now operate on occupied slots of the requested
mode; failed render retry retains its frozen input. Each protected or failed
slot is reported while other eligible slots can proceed. The existing legacy
API remains available for callers without a mode. New character batches mark
their initial candidates Draft with their pipeline's default ratio so configured
Draft sizing is captured on submission; older candidates keep legacy behavior.
Final Assembly dispatch now resolves the Final-preferred FRONT selection before
its progression guard. Disposable checks covered mode isolation, partial error
reporting, retries and a Final-only FRONT; no live render was run.
Narrative targets now have independent Final slots and selections alongside
legacy Draft fields. Explicit-mode generation freezes sizing into parent and
image jobs and proxy manifests; candidate retry reuses its original prompt,
references, seed and sizing. Per-mode locks, clearing, source discovery,
mode-preferred source choice, backdrop reuse/crop, scene-text confirmation and
the target board are connected. Existing pinned assembly layers remain pinned.
Disposable checks covered board isolation, frozen proxy sizing, locks and clear;
broader Narrative composition, downstream discovery, backup and cleanup still
require audit before the packet is complete.
Narrative source and assembly pickers now label modes and prefer the requested
selection, with fallback; reused/cropped backdrop images and confirmed lettering
stay in their own mode. Final selections are represented in scene summaries.
A private Chromium fixture checked independent selected/locked images and mode
switching at desktop and narrow widths. Minor Character new Draft renders now
freeze configured sizing, and failed-slot Retry reuses its saved prompt,
references, seed and sizing; disposable checks covered both. Minor Character
Final boards, mode-specific publication and reference fallback are still pending.
Minor Character work now has separate Final board, selection and lock maps;
working-candidate projection includes both modes. New Final renders prefer the
Final style selection with Draft fallback. Draft locks and Style locks copy to
private immutable snapshots; Final view locks publish through the existing
Inventory transaction. Mode controls, board actions and sizing are being wired
and verified; the packet remains in progress.
Minor Character board actions, selection, locks, source-style fallback and
dashboard mode/size controls now use the requested mode. Failed Retry retains
its original payload, seed and frozen sizing. A private library fixture checked
coexisting Draft/Final selections, private Draft locking, Final Inventory
publication and the Final board in Chromium. Locked or active slots remain
protected during replacement. Cleanup, source variations, and remaining
Quick Character and backup paths still need audit.
Minor Character reference bytes are now frozen at candidate creation, with
locked style snapshots preferred and hashes checked before reuse. Opposite-mode
seed selection is available for Narrative and Minor Character renders; retry
retains its original seed instead. Overview prefers a Final locked Costume
FRONT and falls back to Draft while identifying available modes.
Character refinement sessions and private post-render trials now retain their
mode, resolve mode-preferred references, freeze configured sizing, and isolate
Final adoption from Draft slots and selections. Disposable checks covered
snapshot integrity, Final refinement sizing/adoption and trial dispatch. The
remaining trial and cross-workflow paths still require integration validation.

Image Generator reconstruction and true-up now retain the selected source board
independently of the destination board; correction deduplication includes frozen
sizing. A disposable workspace check verified cross-mode allocation and rejects
a changed source selection. Refinement and private trial documentation now notes
mode isolation and frozen inputs. Cleanup and backup boundaries remain unresolved.

The approved fast E2E baseline passed all four scenarios (43.4s); Python and
JavaScript syntax checks and `git diff --check` passed. A later isolated check
verified Narrative print/discovery prefers a finished Final assembly and falls
back to Draft when the Final image is missing. No live model calls were made.

## Confirmed cleanup and backup boundaries (2026-10-31)

Selected Drafts remain usable as downstream references. Delete all Draft images
for a batch or view, after one confirmation, includes selected and locked Drafts,
clears their selections and locks, cancels matching work, and removes owned
outputs. Completed downstream results and independently saved Inventory copies
remain.

Backup includes all Inventory images regardless of origin, locked Final character,
Minor Character and Narrative outputs (Narrative confirmed lettered output when
present), and the script's existing Markdown/text scope. It excludes Drafts and
unlocked generated images unless independently saved in Inventory, as well as
Image Generator working results, reference snapshots, masks, composites and
previews. Image eligibility derives from metadata and lock state, not filenames.

Selective backup now enumerates Inventory and locked Final workflow outputs
from metadata, including confirmed Narrative lettering and private Minor STYLE
locks; the PowerShell script retains Markdown/text copying. Disposable fixtures
verified included and excluded files, empty image manifests and actual PowerShell
copying. Bulk deletion and its active-work cancellation are not yet implemented.

## Cleanup work packets (completed)

1. Character Draft cleanup: `render_slot_service.py`, local asset store and
   character workflow/router. Fence matching queued/running asks and both legacy
   and slot workers, detach affected candidates, remove batch-owned output
   bytes and private Draft lock snapshots, and clear only this batch's Draft
   selections/locks. Preserve Final and downstream/Inventory copies. Validate
   batch/view scope and races with disposable isolated fixtures.
2. Minor Character and Narrative Draft cleanup: each workflow owns its boards,
   jobs, private snapshots and output paths. Add equivalent scope and
   cancellation using their existing locks and job fences; retain other-mode and
   downstream state. Validate queued and completed candidate cases in fixtures.
3. Dashboard confirmation and integration: expose batch/view operations with one
   explicit confirmation, report failures, and verify both layouts with isolated
   browser fixtures. Re-run approved E2E, review diff, update affected docs and
   complete the plan only after all remaining cross-workflow gaps are resolved.

Narrative target Draft deletion now confirms once, cancels matching parent and
image jobs, clears selected/locked Drafts and removes owned images and lettering.
Minor Character adds workspace/view Draft cleanup, cancellation of owned shared
image requests, private-lock removal and a fence for pending analysis-to-render
handoffs. Disposable isolated fixtures verified mode isolation, queue fencing,
owned output deletion and preservation of Inventory copies. Character pipeline
cleanup remains outstanding. The approved E2E suite passed four scenarios
(43.6s) after the Narrative cleanup, before the later Minor Character changes.

Character pipeline batch/view Draft cleanup now fences owned asks under the
run-state lock, clears Draft selections, locks, slots and ranking evidence, and
removes owned output images and private lock snapshots. Queue staging and image
harvest use the same lock so late work cannot recreate a deleted candidate. A
disposable fixture verified an active selected and locked Draft, queue fence,
Final preservation and an independently saved copy. Remaining work includes
cleanup race/integration audit, full regression and final documentation.

Image Generator workspace Draft cleanup now clears the selected Draft and its
board, cancels owned image jobs and removes output bytes, preserves the Final
board, and invalidates unfinished reconstruction reservations. A disposable
workspace fixture verified the board and Final isolation.

A disposable continuation check verified that analysis started before Minor
Character cleanup cannot start the deleted Draft render. The image-generator
request cancellation check also verified owner validation, a superseded queue
marker, removal of generated bytes and terminal cancellation. ADR 0039 records
mode ownership and the confirmed cleanup/backup contract.

Overview autogeneration now prefers Final selections and locks with Draft
fallback, and uses the mode-aware lock boundary so Drafts stay private. An
isolated check verified Final selection, missing-Final fallback and Draft lock
routing. Image Generator's Draft cleanup confirmation was checked in Chromium.
The approved fast E2E suite passed all four scenarios (43.5s) before these
Overview changes; no live AI calls were made.

The compatibility audit replaced legacy no-mode lock publication with private
Draft locking. Shared local-source discovery now prefers Final per view while
retaining exact Draft-key lookup for pinned references; Head Image Edit phase
sources and workspace summaries include Final. A disposable source fixture
verified Final preference and pinned Draft lookup.

Draft deletion now cancels matching Minor Character and Image Generator
reconstruction continuations and fences their attributed structured AI requests.
Workflow cancellation markers also prevent later resumption or submission. A
disposable check verified that an unrelated continuation and its queued ask
remain untouched. Older in-flight structured asks that predate workflow-ID
attribution cannot be identified individually; their continuation is fenced.

A disposable structured-AI check verified workflow-ID attribution and rejection
of submission after cancellation. The approved fast E2E baseline passed all
four scenarios (48.3s) after continuation cancellation was added. A later
character cleanup adjustment additionally fences attributed view-evaluation
asks; it remains covered by targeted checks rather than that baseline.

The file-queue cancellation contract removes queued asks and supersedes running
asks so their late results cannot be applied. AI_Proxy's file queue has no
per-job stop for a provider already executing; such a provider may continue to
run. Physical interruption would require work in the separate AI_Proxy project.

The approved fast E2E baseline passed four scenarios (46.5s) after the cleanup
and continuation changes. JavaScript/Python syntax and `git diff --check`
passed. The plan remains active pending Joe's choice about physical cancellation
in the separate AI_Proxy project; existing Zet cancellation removes queued asks
and fences already-running asks, whose provider process may still finish.

## Final results

Joe confirmed logical cancellation on 2026-10-31. Already-running provider
processes may finish, but their superseded results cannot be applied; older
in-flight structured asks without workflow attribution cannot be individually
identified, while their continuation is fenced.

The completed work includes configured mode sizing, independent Draft/Final
boards, selections and locks, mode-aware reference fallback and UI, frozen
retry inputs, scoped Draft cleanup, and metadata-selected backup. See
[ADR 0039](../../Docs/DECISIONS/0039-draft-final-images.md) and the affected
component documentation for ownership.

Validation: `npm run test:e2e` passed all four approved fast scenarios (46.5s);
`git diff --check`, Python and JavaScript syntax checks passed. Disposable
fixtures exercised mode isolation, backup and cleanup, cancellation, source
fallback and pending continuation fencing; an isolated Chromium check covered
the Image Generator cleanup confirmation. No permanent tests or live model calls
were added. Live rendering and visual quality were not evaluated, as requested.
