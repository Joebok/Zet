# Dashboard presentation and image input

Compare presents independent universe, character, phase and pipeline/costume
selectors. Paired locked images share local view navigation; image bytes remain
cached in memory only while the page is open.

The [Candidate Board specification](CANDIDATE_BOARD.md) defines the shared UI
standard for Render Controls, candidate cards, and review. This page records
implementation details.

## Expandable production workspace shell (2026-11-24)

`production_workspace.js` supplies a context row, per-scope Preparation
disclosure, operation summary, and results area. The Character Asset Container
is the first integration. A selected Candidate Board opens with preparation
collapsed by default; the overview opens with preparation available. Explicit
disclosure choices persist in session storage by pipeline and costume, and
viewport changes do not rebuild the board. The operation summary remains
outside the disclosure so messages stay visible when preparation is closed.

The Character pilot passed the Character-to-costume and candidate-board safety
scenarios. A disposable Playwright inspection passed at 1920x1080 and
1133x610. Minor Character, Narrative target boards, and Image Generation now use the shell too.
Narrative keeps shared scene direction, local target preparation, the operation
message and the board in one route. Its disposable landscape-tablet inspection
passed at 1133x610. These checks use CSS viewports, not physical tablet input or
device-browser behavior. Image Generation keeps direct prompt rendering and its
reconstruction flow in the same shell, with ordered Browse, Paste and Inventory
reference inputs and named asset forms. Character Wizard reference slots now
use the same Browse, Paste and Image Inventory controls. Costume Wizard private
test renders also open through the shared full-size zoom viewer. The isolated
input/viewer checks and approved Image Generation, Character Wizard, and Costume
Wizard scenarios passed.

## Current Character image production workflow (2026-11-06)

The Assets menu opens Body Reference, Head Image Construct, Head Image Edit,
Character Assembly or a selected Costume Dressing container. Its overview has
shared settings and one selected or locked output card per view, each linking
to a mixed-quality eight-slot Candidate Board. Header changes reload the same
pipeline and valid view for the committed character and phase. Operators prepare
and run images from that board. The Batches page, Run All Remaining, Activity
staging, and legacy character batch endpoints are retired. Old pipeline page
links redirect to the matching container when their pipeline can be identified.
Character Overview remains a separate read-only page.
Legacy batches are neither resumed on startup nor included in current-output
source listings. While the visible board has active renders, the page polls only
compact progress and refreshes full detail after the work settles. Idle views
refresh on entry, tab return, relevant actions or explicit refresh. Finished
candidates can open the optional template-proposal action; accepting a reviewed
proposal updates the governing Character.md for future requests. See the
[completed migration plan](../../plans/completed/character-image-production-workflow.md).

## Pipeline diagnostics and controls

Pipeline Inspection is read-only. It lists current Character Asset Container
records and Narrative story folders from the selected library, alongside any
files found under the legacy pipeline root. Current workflow files are resolved
only within their owning storage roots; file lists and previews load after a
diagnostic is selected. Legacy pipeline configuration remains visible for
reference, but the batch reset control is not offered for current container work.
Use the owning workspace board to queue or manage current candidates.

Character and Narrative use the same responsive Candidate Board grid, action
glyphs, and desktop review layout with controls on the right. Character review
places comparison images on the left and the candidate under review on the right,
using its existing slot and publication guards for select, lock, retry, regen,
and clear.
The character board's View selector opens any view in the current container.
Conditional render settings sit above the action bar with their save controls
and feedback. Aspect ratio and Prompt precede the Character generation buttons.
Both board types group the delete actions at the right edge of the action bar,
which wraps on narrow screens.
Completed candidate cards show the elapsed render time in whole seconds after
their status. Timing begins when Zet submits the render and ends when the image
is collected and placed; older completed candidates without saved timing retain
their existing status display.

## Retired batch-era presentation notes

The following notes describe the former character batch UI and are retained as
historical behavior only.

The dashboard shell initially shows a blank page with the requested route's
heading while context loads. A Final route applies the Final canvas color
immediately. The retired legacy Assets section is never the initial page, and
startup no longer reads legacy assets before activating the requested route.

Identity Key source choices identify Draft or Final source locks in the option text, alongside pipeline, view and costume, so the available mode is clear before previewing a crop. Saved rows continue to use `source_render_mode` for their mode color.

Character Overview view titles link directly to the matching Asset Container workspace, while thumbnails open the shared full-screen viewer. Turnaround missing views link to the corresponding local source workspace for eligible Local rows. A full turnaround remains unavailable until all eight source views are locked; partial sheets remain available from a ready full row.

Character Run available, slot generation/retry, view regeneration, Re-evaluate,
batch Start/Resume and candidate-review retry show immediate submission feedback.
The shared Activity menu lists in-progress preparation and undismissed actions
needing attention, including blocked and partial outcomes. Entries name the action
and view; active work and recent attention appear first. Attention items can be
dismissed without changing their operation checkpoint. Activity refreshes on
navigation, menu open, tab return, submission or explicit request, with no timer.
An unconfirmed browser request retains its operation ID. Activity tracks preparation
and handoff, not render completion. See the [completed plan](../../plans/completed/character-pipeline-operations.md)
for validation limits.

The Assets menu lists Head-Image (Edit) after Body-Reference and before Head-Image (Construct). Pipeline identifiers and source defaults remain unchanged.

Character pipeline batch creation uses a modal with an optional name. An existing
batch opens on a summary page with one selected or locked card per requested view;
its view links open mode-scoped galleries, ranking, review, references and render
tools. Draft/Final, batch, universe and costume remain in the page URL. Batch
and view pages keep the Costume-Dressing selector visible; changing costume opens
that costume's batch summary. Summary and view polling use separate projections;
card images use bounded thumbnails,
while the review viewer requests originals. Master preparation and comparison
reports run only on explicit clicks. Create and Re-evaluate report authoritative
validation after an attempt instead of disabling the controls from a preview.
Batch card view names remain readable links, and selected/locked images open the
review pane with previous/next and Left/Right navigation across available views.
View review offers selected FRONT, the selected opposite side, and the matching
locked Draft as side-by-side comparisons when available.
Each view places its Luna ranking pill below the gallery, followed by separate
Render tools, override image, and Observations disclosures with dividers.
Stage opens an overlaid menu, and successful action acknowledgements quiet after
five seconds. The [completed plan](../../plans/completed/character-pipeline-ui.md)
records restart behavior and validation.

Local character batches show Draft and Final progress separately. The shared
pipeline page offers Run front and Run available, and the Batches page labels
and links each actionable render mode. Pause batch pauses slot collection;
already submitted renders can finish at the proxy and are collected after Resume.
Batches cards reuse the pipeline canvas colors for Draft and Final, with outlined
Mode pills alongside the pipeline pills. Cards have no individual Create task button.

The summary carries compact progress for both modes. A view request contains one
mode and one view; navigation and request generations prevent older responses from
replacing the current page. Missing Final prerequisites are reported when a render
action is attempted. The batch's Draft images and empty Final cards remain visible
in their respective modes.

Final mode uses the shared `--canvas-final` muted green background and a teal
**Final** pill before each character view heading. Minor Characters, Image
Generation and Narrative Scenes reuse the treatment for their image workspace
and slot headings, including empty slots. Controllers expose their current mode
through `data-render-mode`; shared CSS limits the canvas cue to the active page,
so switching to Draft or navigating elsewhere restores the usual background.
Disposable Chromium presentation checks verified scrolled visibility and mode/
navigation resets; physical-device appearance was not checked.

The [UI style guide](../UI_STYLE_GUIDE.md) owns the target visual and interaction
standards, including button/glyph roles, card anatomy, review dialogs, immediate
action acknowledgement, and feedback beside its initiating action. Adoption is
partial; this component document records implemented behavior and verification limits.

## Recent Renders

Recent Renders lists one row per board with a saved thumbnail, image count,
**Review latest**, and **Open board** actions. The local implementation keeps
the visible review label short and includes the board label in its accessible
name so repeated actions can be identified independently. Release verification
of this accessible-name change is pending. Rows with no saved thumbnail disable
review and explain why.

## Optional legacy context (2026-10-28)

`zet.js:loadAssets` uses onboarding's `assets_exists` flag to skip an absent
legacy Assets.json and clear stale selection. Local character readiness does not
require that file; explicit asset API reads still report missing/invalid storage.
`PipelineControlService.snapshot` exposes global settings when Pipelines.json is
absent, with empty legacy stage rows and an unavailable message. Invalid pipeline
configuration still raises an error. `PhaseComparisonService` orders local rows
by stable source key when legacy asset IDs are absent, retaining numeric legacy
ordering and canonical view ordering.

The shared shell's production summary clears counts and timestamps when its
workspace query changes. A same-context refresh failure retains the last
successful counts with a local timestamp and retry action; retry activation is
shown in that notice, and an older request failure cannot replace the new
context's status. A disposable browser check covered success, failure, pending
retry feedback, recovery and a context change during an older in-flight failure.

The approved S1 authoring scenario reopens setup after successful template upload
before restoring its fixture. All four fast scenarios passed (41.6s); disposable
service/browser checks covered missing/invalid files, null IDs and direct loads.
These checks used isolated storage and no live AI calls.

## Dashboard Overview (2026-10-27)

## Character Overview Hub

Character cards use a title link for the owning Asset Container and open locked
images in the shared fullscreen viewer. Character template editing is available
beside the Base Images summary. Character and phase rename/archive actions live in
the overview; phase deletion is no longer in the global header. See the
[Local Characters component](LOCAL_CHARACTERS.md#character-overview-hub) and
[ADR 0055](../DECISIONS/0055-character-overview-management.md).

Rename shows local progress while files and saved references are updated, then
refreshes the character/phase selectors and selects the server-returned scope
without reloading the page. The shell also updates the URL and stored selection.
Rename/delete actions and the universe/character/phase selectors are disabled
until the request and refresh settle. A persistent success message confirms
completion and survives ordinary overview refreshes. If the rename succeeds but
the dashboard refresh fails, the message reports that distinction and asks for a
page refresh. Page navigation does not cancel the rename request.

Character Overview is the selected character/phase hub. Setup retains draft,
upload and validation controls until Character.md is valid, then exposes the
character template editor. Base Images and each costume show eight view cards for
current published locks in front, front left/right 3/4, left/right profile, back
left/right 3/4, back order; cards link directly to their Asset Container view and
show an empty state when no lock exists. Thumbnails are bounded cached JPEGs.
Base Images starts collapsed and remembers its open or closed state per universe,
character and phase, like the other disclosures. Data refreshes
on entry/context change without recurring or tab visibility polling. The former
`local-overview` page and `/local-character-overview` URL map to this hub.

Dynamic proposal controls have unique accessible names that include their action,
row position, and affected field or correction. Nested image review scope choices
identify their parent correction, and replacement actions identify their section.
The dashboard uses the existing palette in [zet.css](../../zet/web/static/zet.css).
The [2026-10-27 compliance register](../UI_COMPLIANCE_REVIEW.md) records current
page reachability, bounded alignment changes and unverified states. Local Character
Overview uses the shared light tokens and current-output cards. Refinement shows
request acknowledgement and errors beside each action group.
Shared preview wells use subtle-surface tokens. These changes do not establish
complete style-guide or physical-device compliance.
Primary teal identifies the main action and selected images. Selection also has a
text label and stable inset border; it does not mean that an image is locked.
Published images retain a separate Locked label. Success, warning, and danger
tokens describe completion, attention, and errors. Clear slot uses an outlined
danger action. Backend services still own every protection and state transition.

## Character and costume template editor (2026-10-26)

Character Asset Container overviews show Container Settings and Template
Improvement as separate disclosures. The latter offers current-prompt analysis
or a finished-candidate picker, optional direction/model, editable governing
source choices, per-finding selection, diffs and compiled prompt previews.
Candidate cards link to this panel with their evidence selected. Dressing also
shows an Edit governing Costume template action beside Character.md.

Character and costume template edit actions, including the pipelines' **Edit master template**, character setup's **Edit character template**, Costumes table's **Open**, and asset template buttons, open the current canonical master in the Template Editor. Pipeline edits do not open proposal popups; saved batch versions retain their frozen sources. Use **Restart from current masters** to review edited masters for a batch. [template_editor.js](../../zet/web/static/template_editor.js) keeps one native textarea draft with an inert, escaped decoration layer. **View: Off** shows raw text normally; the eight orientation choices dim inapplicable prose without disabling editing. One selector sets matching head/body orientations. Applicability follows compiler view rules, independently of pipeline section selection; costume mode annotations retain their union without another selector.

The Template Editor also lists the current character's `Character.md` and
costume templates in place, with an explicit empty/loading/error state. It uses
the selected header character and phase. The editor remains disabled until a
source is loaded; a failed switch keeps the previous draft visible. Template
manual selection updates the local page status, and copy/download feedback stays
beside the manual controls.

Literal case-insensitive Search highlights all occurrences, including dimmed text. **Full file** is editable; **Diff** is a read-only contextual master-on-disk/current-edits comparison with line numbers. Its search count covers displayed diff rows. Switching controls preserves the draft, selection and undo history. Refresh diff checks the latest disk master; Reload master uses existing unsaved-change protection. Save rejects validation errors or changed masters, retaining edits. New typing while a save is pending remains dirty after the submitted version succeeds. Invalid syntax temporarily leaves affected sections neutral until analysis succeeds. Config's existing plain-source editor remains available without template-specific controls. See [prompt contracts](PROMPTS.md#character-and-costume-source-editing-2026-10-26) for backend validation and batch-overlay limits.

## Responsive shell and viewing

[index.html](../../zet/web/templates/index.html) owns the shared shell.
[zet.js](../../zet/web/static/zet.js), `syncResponsiveChrome`, moves infrequent
utilities into Tools at 1360 CSS pixels and below, restoring their original
locations above that boundary. Task attention stays visible. The section selector
includes all four character pipelines. Header selectors retain current context;
native selectors expose full choices when labels are long. Coarse pointers receive
touch sizing even above the compact breakpoint.

Character batch settings and Image Generation settings use disclosures. Existing
batches collapse new-batch settings on compact screens; pages without a batch
open those settings. Toggling disclosures preserves form controls and drafts.
Overview exposes its existing image viewer on compact screens when a preview is
available. Narrative targets use the production shell at every viewport, with
shared scene and target preparation in a per-target disclosure. The board takes
priority when a target already has images; empty targets open preparation.
Disclosure choices persist by target and the operation message stays visible.

Review dialogs use fixed viewport positioning and dynamic height with a `vh`
fallback. Local candidate review preserves originating gallery position/focus,
offers reference/candidate comparison, and removes the empty reference column
when no comparison exists. Decisions, selection, close, and navigation stay outside
scrolling details. Polling preserves the current candidate, unsaved decision,
comparison choice, details expansion/scroll, and focus.
The shared [review zoom helper](../../zet/web/static/review_image_zoom.js)
provides cursor-centered wheel zoom from fit to 4×. Character Asset Containers
register both candidate and comparison images. Narrative and Image Generation
register the candidate image. Minor Characters attaches the helper without
synchronizing its rendered images, so wheel zoom is unavailable there. The
Candidate Board specification defines the common comparison and zoom behavior.

The shared full-screen image viewer also uses this helper for mouse-wheel zoom
from fit to 4x. Zoom resets when the image changes or the viewer closes.
Character Overview supplies the available locked images in each base-image or
costume group, preserving view order. Left/right buttons and arrow keys move
within that group and stop at the first and last available views.

Task-capture evidence and Pipeline Inspection previews use the dashboard viewer.
The Character refinement and post-render adjustment pages use the helper's
standalone viewer with the same zoom, pan, reset, and close controls. Gallery and
comparison images have keyboard-accessible full-screen actions. Cross-phase
Character FRONT references use the shared Browse, Paste, and Image Inventory
controls; task attachments remain evidence files rather than workflow inputs.
The shared zoom/viewer and phase-source selection were checked in disposable
browser fixtures; the Character-to-costume and candidate-board safety journeys
passed. Physical tablet touch behavior remains unverified.

Shared candidate review disables candidate/view navigation while saving a review
decision and gives the pending action local status. Short-height, narrow review
dialogs reserve a minimum image area while keeping decision controls reachable.
These source changes still require populated-state browser inspection at the
captured compact viewport.

The Batches summary uses candidate view/status data already available in adapter
summaries to show running views; it does not load each full run detail. Refresh
shows pending feedback while retaining populated rows. A failed refresh keeps rows
from the same universe and labels them as the last successful results; a universe
change clears old rows before loading. Three-second polling and its in-flight guard
are unchanged. An isolated prepared browser check covered populated refresh and
failure retention; populated keyboard and long-label behavior remain unverified.

Minor Characters groups six horizontally arranged image cards under each
collection, following the Character Overview card layout. Cards show locked
Draft or Final previews and link to the asset's Candidate Board even when the
image is unavailable. The Style board is labeled “Style”; other cards use their
view name. The same cards appear beneath Container Settings and Template
Improvement on the collection page. A character-only link opens the collection.
Adding `view` opens the named board, which owns image generation and asset
authoring.

On a Minor Character asset page, the title identifies the character, an Asset
selector switches among its boards, and Back to Asset Container returns to its
collection. Asset inputs and Interview are separate collapsed sections above
the Candidate Board.

Direct Minor Characters links skip the shell's legacy `/api/assets` startup load;
these universe-local workspaces do not require a selected phase's `Assets.json`.
The overview reads collection summaries without polling individual boards.

Post-render trial thumbnails open a viewing-only dialog with Previous/Next buttons,
left/right arrow keys, and Close/Escape. Navigation includes ready images in the
current round and preserves the displayed trial while polling. Each trial card and
the viewer offer a read-only generation prompt dialog, sourced from the frozen
trial input exposed by `LocalPostRenderPromptService.detail`, rather than the
current proposed template. Closing the image viewer restores thumbnail focus.

## Compact image cards and review (2026-10-20)

Candidate Board aspect ratio remains visible above render shortcuts for every
subscriber. Narrative backdrops and assemblies show their inherited scene canvas
ratio as read-only. Image Generation owns generation mode, universe style, and
reference management in page setup; reconstruction is an asset-scoped subview.

Character view action rows retain the text button **Stage in Image Generator**,
including on completed views. `local_asset_pipeline.js` supplies the batch, view,
costume and Recompile context; `zet.js` initializes Image Generation, applies the
validated handoff and navigates there. It replaces prompts, reference slots,
result/selection bindings, inventory-update associations, reconstruction and true-up
drafts, including universe-scoped browser persistence. Inputs remain editable;
render count is retained and Generate is explicit. Reference bytes/metadata and
the staged render settings survive reload. Mode changes and other generator entry
workflows clear the pipeline render settings. Context checks prevent stale responses
from applying after navigation, universe changes or a newer content replacement.

[image_card_ui.js](../../zet/web/static/image_card_ui.js) owns the scoped SVG
action decorator (`ZetImageCardUI.decorate/scan`). It preserves existing controls,
handlers, IDs, links and workflow eligibility while supplying accessible action
names, hover/focus labels and stable action keys for polling focus restoration.
It observes rendered image controls and dynamic labels; it does not dispatch work.
Shared styles use 32px desktop controls and at least 44px coarse-pointer targets.
Image action rows wrap naturally; page-level navigation/forms retain text.

Character, Narrative and Minor Character cards show render status once. Character
and Narrative Prompt and source disclosures live in review, collapsed on opening
or changing candidates and preserved by same-candidate polling. Occupied pending
and failed slots can open details without images; image-dependent decisions remain
unavailable. Narrative review retains prompt copy, source provenance, assembly
layer labels and raw-composite links. Image Generation follows the same disclosure
default and groups navigation, close and render controls into compact toolbars.

Character review displays the existing distinct Luna advisory panel below the
title/context and above Human decision. Available findings remain expanded;
stale/failed advice is labeled, and absent advice has no empty placeholder. Long
advice scrolls independently while decisions/actions stay reachable. Prompt/source
details include recorded inputs, ordered source labels and generation metadata.
The former Image details and render actions wrapper is removed.

Character Asset Container and Narrative candidate boards expose on-demand Luna
Review beside Draft/Final generation actions. Review criteria opens beside the
action, successful ranks appear in card metadata without moving slots, and the
full assessment appears in image review. The disclosure shows the saved prompt
after a run.

Inventory copy feedback, shared fullscreen viewers (including Overview, identity,
turnaround, costume, phase comparison and Zine images), Minor Character comparison
controls and standalone refinement image actions use the same decorator. Workflow
forms and retired generation/Render Console code retain their existing ownership.

See the [completed plan](../../plans/completed/site-wide-image-cards.md) for isolated
validation and device limits. No API, storage, queue or publication contract changed.

## Image input

[image_input.js](../../zet/web/static/image_input.js), `ZetImageInput.attach`, adds
Paste image and Choose image beside an existing paste target and file input. It
reads image clipboard data directly from a tap and passes the File to the existing
file-input change handler. It does not upload independently, parse clipboard HTML,
fetch copied URLs, or change save timing. Keyboard paste/drop handlers remain in
their original modules. Choose image does not force camera capture.

Adapters cover Head source input, Image Generation references/reconstruction,
Inventory import/add/replacement, Minor Character references, costume references,
and task screenshots. Both dashboard templates hosting task capture load the
helper before consumers. Page/universe/character/phase changes during a pending
read discard its result. Disabled inputs/targets disable both buttons. Unsupported,
denied, or non-image reads offer a file-picker alternative. Existing server
type/size validation remains authoritative.

Reads require a secure context and can show native Paste approval UI. Actual
behavior depends on the browser and copied representation; see
[WebKit clipboard documentation](https://webkit.org/blog/10855/async-clipboard-api/)
and [Zet HTTPS setup](../LAN_HTTPS.md). Chromium adapter checks do not establish
iPadOS permission behavior. Physical-iPad acceptance is tracked in the
[implementation plan](../../plans/active/ipad-responsive-ui-and-style-consistency.md).

## Inspection and validation

The [capture script](../../Scripts/capture-dashboard-ui.mjs) is a UI inspection
aid. It requires an explicit dashboard URL, visits active destinations, and writes
screenshots/JSON without deleting older captures. Default output is timestamped
under ignored `test-results/ui`. Metadata includes revision, route, dimensions,
browser, activation errors, and horizontal overflow. Run the structural sweep
against a selected dashboard; it does not submit workflow actions:

```powershell
# Set these from the verified Test active-release record and /api/health.
$env:ZET_DASHBOARD_URL = "http://127.0.0.1:8082/"
$env:ZET_EVIDENCE_COLLECTOR = "C:/Users/Joe/Projects/Zet_Tester/evidence.mjs"
$env:ZET_TEST_RELEASE_REVISION = "<release revision>"
$env:ZET_TEST_BOOT_ID = "<boot id>"
$env:ZET_UI_OUTPUT = "C:/Users/Joe/Projects/Zet_Tester/runs/<campaign>/direct-page-sweep"
npm.cmd run capture:ui
```

`ZET_UI_PAGES` optionally selects comma-separated destinations. Profiles are
1920 × 911 desktop, 1133 × 610 tablet landscape, and 810 × 1080 tablet portrait.
Each profile has a manifest; a run manifest and coverage ledger join them.
Activation errors remain explicit coverage blockers.

Cross-repository UI review evidence uses the opt-in Zet_Tester `--evidence` mode
and its named `capture` browser command. It records a viewport PNG, compact
accessibility snapshot, visible node geometry, selected styles, viewport details
and bounded browser errors beneath the run's `evidence/` folder. Each manifest
must identify the actual Test release revision and boot ID. Reuse the same fresh
workflow's outputs across desktop and tablet captures; do not combine bundles
from different release revisions. This does not replace the broader page sweep
above or establish physical iPad behavior. See the
[Zet_Tester instructions](../../../Zet_Tester/README.md).

The release-pinned, visible-navigation journeys are defined in
[Zet_Tester/ui-review/direct-journeys.json](../../../Zet_Tester/ui-review/direct-journeys.json)
and implemented by its `direct-journeys.mjs`. They cover Character Overview,
Minor Characters, Identity Keys, Turnarounds, Costumes, Compare, and Recent
Renders. They record the current visible state and navigation action; their
captures do not certify that displayed library outputs were generated in that
campaign. Tablet captures resize the already open page after desktop navigation,
because the narrow layout presents navigation in a select control.

## Managed LLM Roles (2026-10-22)

Config now renders the shared role registry, with active and compatibility/retired groups, separate model defaults, per-role inherited/overridden model choices, provider/capability requirements, Qwen applicability indicators and collapsible Template Editor links. [LLM roles](LLM_ROLES.md) owns the inventory and semantics. Disposable fixture checks cover actual override/save/reload/clear and source opening at 1280px/390px; physical-device and live-model behavior remain unverified.

Config groups related settings by image sizing, background work, scene
automation, render service, model purpose and output dimensions. Section status
shows which groups differ from the last loaded/saved values; the page-level Save
Project Settings action saves the single supported settings form. Process rows
show Running/Stopped, additional process count and collapsed process details.
Start/stop/restart follow the reported capability and current state, with
pending/error feedback on the affected row. Process actions were checked only
with mocked requests; physical production process behavior was not exercised.

## Costume-Dressing controls (2026-10-26)

`local_asset_pipeline.js` presents saved per-view render mode/reference choices and one three-action Stage menu. FRONT only offers its supported mode. Independent mode readiness supplies disabled reasons and Run ready views. Dressing's progression summary reports completion, names ready views, or directs the operator to a blocked view's prerequisite when saved settings make no view ready. Completed runs also receive completed-state control guidance, so Assembly no longer says to render FRONT after every view is already selected. These copy changes are implemented locally; populated mode/save-state and Assembly journey acceptance remain open. The existing post-render page/controller presents persistent accomplished/in-progress criteria, suggestion view/mode checkboxes, a cumulative source diff, four private target-view images, advisory assessments and earlier rounds. Criteria errors and save progress appear beside the checklist; suggestion blocking reasons, progress, empty results and failures appear beside Suggest. Unsaved checklist changes block analysis/trial/save actions. Other character pipelines retain their Character.md workflow. Prompt Generator Pilot entry points and pages are retired. Domain behavior belongs to [Local Characters](LOCAL_CHARACTERS.md#costume-dressing-modes-and-adjustments-2026-10-26).

## Universe Species settings

Open Universe Settings and use Species to add or edit a definition. Species IDs
are set when entries are added. For a save conflict, Reload Species refreshes
the catalog and keeps the form's unsaved text for review. The Character Wizard
and Manual Setup use the universe's saved choices. Loading and saving report
their current state in the page status area. A failed save highlights the
affected field while preserving the draft; a failed catalog reload keeps the
existing choices and leaves available actions usable. Universe changes fence
older settings responses from updating the current form.

## Universe creative settings
The header Universe Settings action is available in both workspaces. Creation
and settings use matching art-style headings and action rows. Settings save
canonical art style and all lettering defaults, with a preview,
unsaved-navigation protection, loading/saving feedback and read-only
identity/storage/layout details. Story lettering overrides take precedence;
changes do not rewrite previously finished images. Settings requests are
fenced by universe so an older response cannot replace a newer selection.

## Backdrop source controls (2026-10-29)

Narrative places source linking before authoring. Linking mode selectively exposes local unchanged reuse, Reference crop/adaptation, or Regenerate seeding. Crop supports exact numeric coordinates, pointer movement and lower-right resizing, independent of output size. Existing image cards remain accessible in all modes.


## Environmental universe style (2026-10-30)

Universe settings and creation expose Environmental style. Image Generation persists a canonical/environmental choice with its form; Add Universe art style uses that choice. Minor Characters and character batch creation expose independent universe-style selectors.

Character and Narrative Candidate Boards share review position, candidate actions,
and captured input links. The current Character review offers selected view
images and has a separate status area for candidate actions. Narrative offers
the target's selected image in a chooser. Minor Characters automatically
displays the selected image beside a different candidate when available.

## Recent Renders

Recent Renders appears between Story Telling and Universe when the selected
universe has recorded harvests. Each activity row shows the latest harvested
image when its file was captured, a full-screen Review latest action, an Open
board link, and the number of qualifying images harvested there. Older saved
rows without an image path still link to their board and mark the preview
unavailable. The latest image on a board sets its position. The saved snapshot keeps the newest eight images plus any
others under 24 hours old when the latest harvest was recorded. The server
sends the saved snapshot on connection and pushes updates after successful
harvests, including those collected while the dashboard is on another page.
