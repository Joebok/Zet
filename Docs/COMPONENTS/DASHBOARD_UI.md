# Dashboard presentation and image input

The [UI style guide](../UI_STYLE_GUIDE.md) owns the target visual and interaction
standards, including button/glyph roles, card anatomy, review dialogs, immediate
action acknowledgement, and feedback beside its initiating action. Adoption is
partial; this component document records implemented behavior and verification limits.

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

The Character Development **Overview** button mounts the character/phase/costume
grid in the shared dashboard shell. **Assets → Character Overview**, above
Body-Reference, retains the existing character setup page (`page=onboarding`).
The compact section selector exposes both destinations. The former standalone
`/local-character-overview` URL redirects to `/?page=local-overview`, retaining
query context. Its template and header links are retired.

`local_character_overview.js` owns scoped card rendering, universe-bound requests
and image URLs, per-card generation/stop feedback, duplicate submission fencing,
and polling only while mounted. Unchanged snapshots retain focus; late responses
cannot update another activation. Cards have no Create task button; the dashboard
task control remains available. `zet.css` owns the responsive grid and image wells.
Disposable Chromium checks cover desktop/390px navigation, action feedback,
request universe and the redirect; no physical-device or live-render check was run.

The dashboard uses the existing palette in [zet.css](../../zet/web/static/zet.css).
The [2026-10-27 compliance register](../UI_COMPLIANCE_REVIEW.md) records current
page reachability, bounded alignment changes and unverified states. Local Character
Overview now uses the shared light tokens and per-slot action outcomes, fences
duplicate slot submissions, and avoids rebuilding unchanged snapshots during polling.
Refinement shows request acknowledgement and errors beside each action group.
Shared preview wells use subtle-surface tokens. These changes do not establish
complete style-guide or physical-device compliance.
Primary teal identifies the main action and selected images. Selection also has a
text label and stable inset border; it does not mean that an image is locked.
Published images retain a separate Locked label. Success, warning, and danger
tokens describe completion, attention, and errors. Clear slot uses an outlined
danger action. Backend services still own every protection and state transition.

## Character and costume template editor (2026-10-26)

Character and costume template edit actions, including the pipelines' **Edit master template**, character setup's **Edit character template**, Costumes table's **Open**, and asset template buttons, open the current canonical master in the Template Editor. Pipeline edits do not open proposal popups; saved batch versions retain their frozen sources. Use **Restart from current masters** to review edited masters for a batch. [template_editor.js](../../zet/web/static/template_editor.js) keeps one native textarea draft with an inert, escaped decoration layer. **View: Off** shows raw text normally; the eight orientation choices dim inapplicable prose without disabling editing. One selector sets matching head/body orientations. Applicability follows compiler view rules, independently of pipeline section selection; costume mode annotations retain their union without another selector.

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
available. Existing Narrative targets with images prioritize results and collapse
direction/generation inputs on compact screens. Other targets keep authoring
available. Desktop editing retains columns and expanded inputs.

Review dialogs use fixed viewport positioning and dynamic height with a `vh`
fallback. Local candidate review preserves originating gallery position/focus,
offers reference/candidate comparison, and removes the empty reference column
when no comparison exists. Decisions, selection, close, and navigation stay outside
scrolling details. Polling preserves the current candidate, unsaved decision,
comparison choice, details expansion/scroll, and focus.
[local_asset_pipeline.js](../../zet/web/static/local_asset_pipeline.js) owns this
interaction; [narrative.js](../../zet/web/static/narrative.js) adapts shared styles
to Narrative's independent records. Minor Characters retains its own comparison
controller and selected-versus-preview distinction.

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

The Minor Characters list uses a responsive card grid with each character's name,
locked FRONT image (or an empty-image placeholder), and Edit/Delete buttons.
Clicking the image or Edit opens the existing editor; Delete retains its confirmation
and preserves published Inventory images.

Direct Minor Characters links skip the shell's legacy `/api/assets` startup load;
these universe-local workspaces do not require a selected phase's `Assets.json`.
The controller's script cache key includes the five-view revision so cached code
cannot retain bindings to the removed side selector.

Post-render trial thumbnails open a viewing-only dialog with Previous/Next buttons,
left/right arrow keys, and Close/Escape. Navigation includes ready images in the
current round and preserves the displayed trial while polling. Each trial card and
the viewer offer a read-only generation prompt dialog, sourced from the frozen
trial input exposed by `LocalPostRenderPromptService.detail`, rather than the
current proposed template. Closing the image viewer restores thumbnail focus.

## Compact image cards and review (2026-10-20)

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
browser, activation errors, and horizontal overflow. Run automated checks against
the isolated fixture:

```powershell
# Verify Python 3, then start tests/e2e/server.py --mode fast separately.
$env:ZET_DASHBOARD_URL = "http://127.0.0.1:8765/"
$env:ZET_UI_OUTPUT = "test-results/ui-inspection"
npm.cmd run capture:ui
```

`ZET_UI_PAGES` optionally selects comma-separated destinations. Default captures
cover desktop, 1133 × 610 and 1133 × 560 iPad mini landscape, 1024 × 640, and phone
sizes. Activation errors mean partial evidence, even without overflow. See
[Testing](../Testing.md) for the four maintained fast scenarios, isolation, and
approval requirements for new permanent tests.

## Managed LLM Roles (2026-10-22)

Config now renders the shared role registry, with active and compatibility/retired groups, separate model defaults, per-role inherited/overridden model choices, provider/capability requirements, Qwen applicability indicators and collapsible Template Editor links. [LLM roles](LLM_ROLES.md) owns the inventory and semantics. Disposable fixture checks cover actual override/save/reload/clear and source opening at 1280px/390px; physical-device and live-model behavior remain unverified.

## Costume-Dressing controls (2026-10-26)

`local_asset_pipeline.js` presents saved per-view render mode/reference choices and one three-action Stage menu. FRONT only offers its supported mode. Independent mode readiness supplies disabled reasons and Run ready views. Dressing's progression summary reports completion, names ready views, or directs the operator to a blocked view's prerequisite when saved settings make no view ready. Completed runs also receive completed-state control guidance, so Assembly no longer says to render FRONT after every view is already selected. These copy changes are implemented locally; populated mode/save-state and Assembly journey acceptance remain open. The existing post-render page/controller presents persistent accomplished/in-progress criteria, suggestion view/mode checkboxes, a cumulative source diff, four private target-view images, advisory assessments and earlier rounds. Criteria errors and save progress appear beside the checklist; suggestion blocking reasons, progress, empty results and failures appear beside Suggest. Unsaved checklist changes block analysis/trial/save actions. Other character pipelines retain their Character.md workflow. Prompt Generator Pilot entry points and pages are retired. Domain behavior belongs to [Local Characters](LOCAL_CHARACTERS.md#costume-dressing-modes-and-adjustments-2026-10-26).

## Universe creative settings
The header Universe Settings action is available in both workspaces. One form saves canonical art style and all lettering defaults, with a preview, unsaved-navigation protection and read-only identity/storage/layout details. Story lettering overrides take precedence; changes do not rewrite previously finished images.

## Backdrop source controls (2026-10-29)

Narrative places source linking before authoring. Linking mode selectively exposes local unchanged reuse, Reference crop/adaptation, or Regenerate seeding. Crop supports exact numeric coordinates, pointer movement and lower-right resizing, independent of output size. Existing image cards remain accessible in all modes.
