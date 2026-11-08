# Minor Character source intake

Status: complete

## Goal

Let the operator populate the shared MinorCharacter.md fields from the saved
Inventory image before Style Alignment. Preserve authored content and keep
source observations separate from intentional changes to the aligned reference.

## Current behavior and impact

Container settings edits the source and shared template fields. The Style
Alignment interview edits only source-to-reference changes. The collection
already has durable AI authoring continuations and a compact progress endpoint.
Intake adds an optional collection-level job to the existing runtime record.
Local Characters, Data Model, Code Map, LLM Roles and ADR 0050 own the affected
workflow and contracts.

## Work packets

### WP1 - Queue and apply intake

- Files and interfaces include `minor_character_service.py`, `minor_character_router.py` and `llm_role_service.py`.
- Reuse the Minor Character authoring continuation and common AI_Proxy JSON path.
  Capture the selected source bytes and ask for structured descriptions of the
  blank shared fields. Check the template hash and source before applying.
- Acceptance requires template-only population without a canonical style,
  preservation of authored fields and rejection of stale or malformed results.
- Validation uses an isolated prepared-response check.
- Status: complete.

### WP2 - Expose intake in Container settings

- Depends on WP1. Owns `minor_characters.js` and `index.html`.
- Flush edits before requesting intake and show progress and the result in
  Container settings. Use the visible asset's existing progress poll.
- Acceptance requires a usable action across assets and saved fields on reload.
- Validation uses an isolated Chromium check and JavaScript syntax check.
- Status: complete.

### WP3 - Verify and document

- Depends on WP1 and WP2. Update the named knowledge owners and archive this plan.
- Run `npm run test:e2e` and `git diff --check`. Keep checks isolated and use
  disposable intake coverage. Live inference is outside the validation scope.
- Status: complete.

## Validation and results

- `npm run test:e2e` passed all four approved scenarios in 44.9 seconds.
- A disposable Chromium/API scenario passed against the isolated fixture queue.
  It verified the source bytes and role on the published request, intake with
  no canonical style, preservation of existing fields and in-progress edits,
  persistence after reload, and consumption by Style Alignment prompt writing.
  It also checked duplicate requests, a stale template, and a malformed result.
- A disposable settlement check passed source-byte fencing and replay after
  the atomic template write but before the runtime status save.
- Python AST parsing, JavaScript syntax checking, and `git diff --check` passed.
  Live inference and artistic output remain unverified.
- [ADR 0050](../../Docs/DECISIONS/0050-minor-character-asset-collections.md)
  records the distinction between intake observations and intentional changes.
