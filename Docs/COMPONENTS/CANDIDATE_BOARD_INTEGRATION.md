# Subscribe to the Candidate Board

The dashboard shell loads the board stylesheet, shared image glyphs, and
review zoom helper. Import `mountCandidateBoard` from
`/static/candidate_board.js`. Give it two empty hosts. Put the board host where
Render Controls and the grid belong. Put the dialog host outside the board
and any form. The five active Character Asset Container pipelines are the
reference integration. When adopting the component, replace the page's
existing board and review rendering with the mount and reuse its workflow
handlers through the adapter. Narrative uses the optional prompt authoring section for its model picker and Write Prompt.
[Character adapter](../../zet/web/static/character_asset_container.js)

Minor Characters also mounts the component for all six assets. Render Controls
edit the next prompt body. Review shows the exact saved render prompt. The
review-only Interview action hands the candidate ID back to the page's existing
interview workflow.
[Minor Character adapter](../../zet/web/static/minor_characters.js)

Completed image durations use AI_Proxy's worker execution time, excluding queue
and dashboard polling delays. Older or imported images without worker timing
retain the local elapsed-time value.

## Supply the model

- `scope` has a stable `key`, `title`, and optional `view`. Include universe
  and asset or target identity in the key. Keep `revision` separate.
- `slots` contains eight ordered records with stable string `key`, optional
  `candidate`, and optional `actions`. A candidate has `id`, `quality`
  (`draft` or `final`), and `status`. Supply `thumbnail` and `image` as
  `{url, label, version?}`. For mutable images, give each version a cache-safe
  URL and a changed version. Supply an uncropped thumbnail. The component fits
  the whole image in its 4:3 well and falls back to `image` when `thumbnail`
  is absent. Include applicable `elapsedSeconds`, `locked`,
  `error`, `notices`, `earlierPrompt`, `humanAssessment`, `prompt`, `negativePrompt`,
  ordered `inputs` (`{label, url?, marker?}`), optional `renderSettings` rows
  (`{label, value}`), and `provenance` lines. Use the saved request for inputs
  and settings. A marker is literal prompt text such as `<image3>`. Set
  `reviewable: false` for records that cannot be inspected.
- Supply `selectedId` and optional `lunaReview` with `status`, `criteria`,
  `error`, and `entries` keyed by candidate ID. Each entry has `rank` and
  `assessment`. Use the status mapping below for workflows that offer Luna.
- An action has `key`, `label`, optional `glyph`, `role` (a shared button
  class), `placement` (an array of `card`, `review`, `controls`, or `settings`),
  `group` for board actions (`prompt`, `render`, `luna`, or `bulk`),
  and optional `disabledReason`, `mode`, `count`, and `value`. Omit
  unsupported actions. Use `lock` and `unlock` for their corresponding
  actions. Supply their availability from the workflow's current state.
- Slot generation and the two bulk-delete descriptors come from the component.
  Pass `renderActive` and `replacementBlock` on slots. The component uses mode
  readiness for slot renders too. Pass `bulkBlock` for a workflow-wide block.
- `renderControls.fields` contains labeled `{key, label, type, value}`
  fields, with optional `disabled` and select `options` as `{value, label}`.
  Fields render in a vertical stack by default. Set `fieldsLayout: "inline"`
  for a responsive row of related settings. Board actions with `settings`
  placement appear below those fields inside the Prompt and render settings
  disclosure.
  Supported types are text, textarea, select, and checkbox. Optional
  renderControls.promptFields places the prompt actions and feedback in a
  noncollapsible Prompt authoring section. Text fields can provide suggestions
  and a placeholder. Suggestions allow free-form input. The component
  supplies the four render shortcuts. Provide known disabled reasons in
  `renderControls.readiness` by shortcut key such as `render-draft-4` or
  mode such as `draft`. Supply `promptStatus` and `renderStatus` as needed.
- `comparisons` lists eligible `{key, label, image}` records and
  `comparisonDefaults` optionally lists initially shown keys. Use
  `selected` to recommend the board's automatic Selected
  option. The viewer handles explicit choices and image-load errors.
  The shared review uses comparison images and labels. Its single prompt and
  ordered inputs disclosure, including **Render settings**, comes from the
  candidate under review.

### Map saved render evidence

Map `inputs` in the submitted binding order. Put the source name, view, and
quality in `label` when known, such as `Character Assembly · Back Left 3/4 · Final`
or `Overskirt Embroidery`. Supply the literal `marker` used by that prompt when
available. The component displays it as text before the label, for example
`<image3> Overskirt Embroidery`. Omit `url` for an input without a viewable
capture. The component displays its label as plain text.

Map `renderSettings` from the same saved request. Give each row a readable
label and display value, such as `{label: 'Costume Reference View', value: 'Front'}`.
Include applicable recorded settings and omit blank or irrelevant fields.
Format nested metadata into rows in the adapter. The board displays these
rows in review, while `renderControls.fields` holds settings for the next render.

### Serve captured input links

The board opens a supplied `inputs[].url` in a separate tab. The subscribing
workflow's endpoint must authorize access to the scoped candidate and input
and serve the bytes captured for that render. A link should still show those
bytes after the source asset changes.

Serve the image with its raster `Content-Type` and
`Content-Disposition: inline`. Detect the type from the captured bytes
when a filename cannot establish it, including for extensionless files.
Return an unavailable response for missing or unreadable captures. Where
the endpoint previously served downloads, publish a fresh link URL to bypass
cached responses and require revalidation for future requests. Character uses
`delivery=inline` as a URL cache key and `Cache-Control: private, no-cache` in
the response. The query parameter does not select or authorize the capture.
[Character input endpoint](../../zet/web/character_asset_container_router.py)

### Publish Luna lifecycle state

| Adapter status | Shared Review Status |
| --- | --- |
| No recorded status | Not started |
| `RUNNING` | Started |
| `COMPLETE` | Finish |
| `OBSOLETE` | Outdated |
| `FAILED` | Failed |
| `INTERRUPTED` | Interrupted |

Use the `luna` group for the review action. Publish the accepted start and
later progress or results through `update(model)`. Return success without a
separate start message, and report a rejected start with an error outcome.
Pass service failure text as `lunaReview.error`. The workflow determines
when a ranking becomes obsolete. Keep recorded entries in an obsolete result
if available so the component can show them as previous.

## Connect workflow actions and polling

The adapter owns domain actions. Dispatch by intent `key`. Built-in render
shortcut keys have the form `render-draft-1` or `render-final-4`. The intent
includes `mode` and `count`. Candidate actions include `candidateId`,
`slotKey` and `expectedOccupant`. Intents also carry `scopeKey`, `revision`,
`origin`, and current `fields`. Use the fields your existing handler needs.

```js
import {mountCandidateBoard} from '/static/candidate_board.js';

let current = await loadBoardDetail();
const board = mountCandidateBoard({boardHost, dialogHost}, toBoardModel(current), {
  onEdit({field, value}) {
    rememberDraft(field, value);
  },
  async onAction(intent) {
    try {
      // For lock/unlock, call the existing candidate handler with its
      // scope, candidate ID and request fields. The server owns publication.
      const result = await applyWorkflowAction(intent);
      if (!result || !isCurrentScope(intent.scopeKey)) return {status: 'cancelled'};
      publish(result.detail);
      return {status: 'success', message: result.message,
        reviewCandidateId: result.reviewCandidateId};
    } catch (error) {
      return {status: 'error', message: error.message};
    }
  },
});

function publish(detail) {
  current = detail;
  board.update(toBoardModel(current));
}

// The page calls this after accepting a compact progress response.
function applyProgress(progress) {
  publish(mergeProgress(current, progress));
}
```

The functions in the example belong to the subscribing page. A successful
Lock can also update selection and Inventory linkage. Publish the service's
result in one model update. For bulk deletes, pass the server preview's affected slots, active Draft slots,
and protected effects to `confirmCandidateDeletion`. Keep each workflow's
preview and guarded commit endpoints. Surface errors
directly. Any refresh on error follows the workflow's existing behavior.

While visible work is active, merge compact progress for the current board
and occupant into the last accepted detail. Publish when displayed data
changes. When work settles, refresh detail for the image, elapsed time, or
Luna assessment. Combine completions from the same poll. Apply the same
scope and freshness checks the workflow already uses to discard late
responses. Stop polling and call `board.dispose()` on exit.

Use `beforeReviewLeave({scopeKey, candidateId, nextId})` when the page already
guards unsaved decisions. Return false to keep the current review. Use
`onEvent` for `review-open`, `candidate-change`, `review-close`, and
`comparison-change` notifications. The last includes `keys` and
`activeKey`. Use `update(model)` for UI data, including updates that arrive
while review is open. The module owns the DOM for both hosts.
See the [UI ownership decision](../DECISIONS/0051-candidate-board-ui-ownership.md).

## Report harvested images

Call `record_harvests` in the shared Candidate Board service after persisting
accepted image results. Supply the stable attempt IDs, the canonical board
route, and a display label. Supply a separate board ID when route values can
change for the same board. A successful upscale counts as a new harvest.
Imports, reused images, and failed attempts leave the snapshot alone.
Image Generation associates a render with its named board reservation and
reports each successful child independently.
