# Dashboard presentation and image input

The dashboard uses the existing palette in [zet.css](../../zet/web/static/zet.css).
Primary teal identifies the main action and selected images. Selection also has a
text label and stable inset border; it does not mean that an image is locked.
Published images retain a separate Locked label. Success, warning, and danger
tokens describe completion, attention, and errors. Clear slot uses an outlined
danger action. Backend services still own every protection and state transition.

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
