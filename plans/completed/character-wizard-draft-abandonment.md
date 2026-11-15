# Character Wizard draft abandonment

Status: complete

## Goal

Let operators clear any unfinished Character Wizard interview from Resume draft, including retired interviews and interrupted publication.

## Current behavior

The retirement guard runs before abandonment. The section-based action leaves the shared button disabled after reopening intake. The picker can show identical labels for current and retired drafts.

## WP1 - Service and saved state

- Dependencies: none.
- Files: `character_wizard_service.py` and `character_wizard_sections.py`.
- Handle abandonment under the session lock and fence late model results. Leave published data and draft evidence intact. A draft advancing between display and click can still be abandoned by session ID.
- Project retired records without requiring current authoring sections. Distinguish retired records in the picker.
- Acceptance and validation: disposable service checks for current and retired records, publication recovery, repeated abandonment, and preserved evidence.
- Status: complete.

## WP2 - Wizard controls and documentation

- Dependencies: WP1 response and picker fields.
- Files: `character_wizard.js`, [operator guide](../../Docs/CHARACTER_WIZARD_GUIDE.md), [data model](../../Docs/DATA_MODEL.md).
- Keep Abandon draft available on every unfinished interview. Re-enable it when reopening intake and label retired drafts.
- Acceptance and validation: disposable browser check for successive abandons, JavaScript syntax, approved fast E2E suite, and `git diff --check`.
- Status: complete.

## Progress

The ZetTester state contains three retired failures. The current Gemma / Adult interview reached DRAFT. The browser's section action incremented the dialog generation when reopening intake, which skipped re-enabling the shared Abandon draft button.

## Validation

- Disposable service checks passed for retired, running, failed, question, draft, and interrupted publication states. The checks covered stale revisions, repeated abandonment, rejection for an accepted session, preserved files, and fencing a late attempt.
- A disposable Chromium check used the wizard markup and controller with fixture responses. It abandoned a current draft, a retired draft, and an interrupted publication in succession.
- `npm run test:e2e` passed all four approved fast scenarios. `node --check zet/web/static/character_wizard.js` and `git diff --check` passed.
- The recorded run and ZetTester state were inspected read-only. No live inference ran.
