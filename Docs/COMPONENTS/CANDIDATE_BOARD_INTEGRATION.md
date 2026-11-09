# Subscribe to the Candidate Board

The dashboard shell loads the board stylesheet, shared image glyphs, and
review zoom helper. Import `mountCandidateBoard` from
`/static/candidate_board.js`. Give it two empty hosts. Put the board host where
Render Controls and the grid belong. Put the dialog host outside the board
and any form.

## Supply the model

- `scope` has a stable `key`, `title`, and optional `view`. Include universe
  and asset or target identity in the key. Keep `revision` separate.
- `slots` contains eight ordered records with stable string `key`, optional
  `candidate`, and optional `actions`. A candidate has `id`, `quality`
  (`draft` or `final`), and `status`. Supply `thumbnail` and `image` as
  `{url, label, version?}`. For mutable images, give each version a cache-safe
  URL and a changed version. Include applicable `elapsedSeconds`, `locked`,
  `error`, `notices`, `humanAssessment`, `prompt`, `negativePrompt`,
  ordered `inputs` (`{label, url?}`), and `provenance` lines. Set
  `reviewable: false` for records that cannot be inspected.
- Supply `selectedId` and optional `lunaReview` with `status`, `criteria`,
  `error`, and `entries` keyed by candidate ID. Each entry has `rank` and
  `assessment`. Use `OBSOLETE` for a saved result that is no longer current.
- An action has `key`, `label`, optional `glyph`, `role` (a shared button
  class), `placement` (an array of `card`, `review`, or `controls`),
  `group` for board actions (`prompt`, `render`, `luna`, or `bulk`),
  and optional `disabledReason`, `mode`, `count`, and `value`. Omit
  unsupported actions. Use `lock` and `unlock` for their corresponding
  actions. Supply their availability from the workflow's current state.
- `renderControls.fields` contains labeled `{key, label, type, value}`
  fields, with optional `disabled` and select `options` as `{value, label}`.
  Supported types are text, textarea, select, and checkbox. The component
  supplies the four render shortcuts. Provide known disabled reasons in
  `renderControls.readiness` by shortcut key such as `render-draft-4` or
  mode such as `draft`. Supply `promptStatus` and `renderStatus` as needed.
- `comparisons` lists eligible `{key, label, image}` records and
  `comparisonDefaults` optionally lists initially shown keys. Use
  `selected:<candidate id>` to recommend the board's automatic Selected
  option. The viewer handles explicit choices and image-load errors.
  A comparison may also include `prompt`, `negativePrompt`, ordered `inputs`
  (`{label, url?}`), and `provenance`. The review renders these in the same
  disclosure format as the active candidate. Reference links open separately
  so the review remains available.

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
result in one model update. For protected bulk actions, keep the workflow's
existing preview, per-effect approval, and guarded commit. Surface errors
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
