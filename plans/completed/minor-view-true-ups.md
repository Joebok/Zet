# Minor Character view true-ups
Status: complete
Related issue/specification: reported disabled controls on Jero's Front view.

## Goal and current behavior
MinorCharacterWorkflow already renders view true-ups, but Continue requires an
explicit selection. Read-only inspection of Jero found a rendered FRONT preview,
no FRONT selection, alignment mode and busy=false. Both controls are consequently
disabled. Make the preview's transition discoverable and usable, retaining edits.
No production data changes, deployment, live rendering or permanent tests.

## Impact and constraints
The workflow service owns revision-fenced transitions and selected-image carry;
minor_characters.js and index.html own preview targeting and guidance. The existing
board action payload can carry candidate_id without a new endpoint or schema.
Preserve current-slot membership, view ownership, locks, immutable source bytes,
and custom-only refinement when review is pending or failed. Documentation owners:
LOCAL_CHARACTERS.md, CODE_MAP.md and Testing.md. No durable architecture change.

## Implementation packets
### WP1 — Advance an explicit current preview
- Dependencies: none.
- Files: zet/services/minor_character_workflow_service.py.
- Work: allow Continue to atomically select the supplied rendered current-view
  candidate, retaining matching saved feedback/suggestions; keep selected fallback.
- Acceptance: invalid/stale candidates are rejected before mutation; only the
  advanced image remains in its original slot; Inventory locks remain unchanged.
- Validation: disposable isolated service checks, including render payload capture.
- Status: complete.

### WP2 — Expose the transition and explain refinement readiness
- Dependencies: WP1.
- Files: zet/web/static/minor_characters.js, zet/web/templates/index.html.
- Work: enable Continue for a rendered preview, submit its ID, show inline guidance,
  retain typed feedback and checked suggestions, update script cache key.
- Acceptance: all five views can advance from an unselected preview and use Try
  these changes; Style keeps its existing direct refinement behavior.
- Validation: disposable Chromium journey with prepared responses; JS syntax check.
- Status: complete.

### WP3 — Verify and document
- Dependencies: WP1 and WP2.
- Files: affected component/code-map/testing docs and this plan.
- Work: run approved fast regressions and disposable focused checks, inspect final
  diff, record results and archive the plan.
- Acceptance: checks pass without live AI or normal-library writes.
- Validation: npm.cmd run test:e2e; git diff --check.
- Status: complete.

## Progress and results
- Initial inspection confirms an existing refinement implementation; the blocker
  is the implicit selection prerequisite, not missing model support.
- The public website could not be read with the web tool; its read-only JSON API
  supplied the current workspace state. Production was not mutated.
- No persistent schema or new service/endpoint was needed. The transition remains
  in the existing workflow owner; no ADR or data-model change is required.

## Final results
- Continue accepts an explicit rendered current-view preview and selects/carries
  it atomically with matching saved feedback/suggestions. Existing selected-image
  API calls remain valid. The controller enables the action and explains the gate.
- Disposable service and Chromium checks passed all five views, custom-only failed
  review, corrections plus feedback, single-canvas payloads, preserved source bytes,
  explicit versus prior selection, selected fallback, Inventory lock preservation,
  stale/invalid request rejection, reload and direct Style refinement.
- Chromium reproduced the original disabled controls before loading the fix. No
  page errors occurred; the narrow guidance screenshot was inspected.
- `npm.cmd run test:e2e`: all four approved scenarios passed in 44.1 seconds.
- Python AST, JavaScript syntax, final diff review and `git diff --check` passed.
- No permanent tests, dependencies, production mutations, deployment or live AI
  calls. Software behavior is verified; live render quality was not evaluated.
