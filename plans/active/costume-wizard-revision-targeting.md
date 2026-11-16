# Costume Wizard revision targeting
Status: active

## Goal
Make Costume Wizard interview sections targetable through Zet Test's browser helper so a resumed private draft can be corrected and retested.

## Current behavior
The wizard renders each interview card as an unnamed section. The tester helper's `--in` scope requires a named article. Click/fill/select parsing can also remove label words when optional flags are absent. The resumed Luna-Zet draft remains at TEST_READY with its first test saved.

## Desired behavior
Section cards expose stable accessible article names. Browser commands preserve the complete accessible label with or without optional scope flags. Revision actions retain existing revision fencing and test history.

## Impact analysis
- Dashboard: `zet/web/static/zet.js` section rendering.
- Tester: adjacent `Zet_Tester/browser.mjs` command parsing.
- No API, stored-session, or migration changes.
- Existing S2 covers Assembly/Dressing. A disposable browser check covers Wizard revision targeting.

## Invariants and constraints
Use prepared responses and isolated browser fixtures. Leave the saved Luna-Zet draft unchanged. Preserve click confirmation behavior and exact accessible-name matching.

## Implementation steps
### WP1 - Name interview cards
- Dependencies: none.
- Files/interfaces: `zet/web/static/zet.js`.
- Work: render cards as articles and associate each existing heading through a stable section-key-derived ID.
- Acceptance: Chromium exposes a uniquely named Upper body and waist article containing its revision field and Refine section button.
- Validation: disposable Chromium accessibility and scoped-action check.
- Status: complete.

### WP2 - Preserve helper labels
- Dependencies: none.
- Files/interfaces: `Zet_Tester/browser.mjs`.
- Work: parse click scope flags only when supplied; parse fill/select labels up to --in or --value; show --in in click usage.
- Acceptance: unscoped click/fill/select and scoped section/slot actions resolve exact intended controls.
- Validation: node syntax check and disposable browser-helper checks.
- Status: complete.

### WP3 - Verify correction and regression
- Dependencies: WP1, WP2.
- Files/interfaces: disposable browser fixture; existing Zet S2 scenario.
- Work: exercise section refinement with the saved revision and direction, apply its prepared replacement, then submit a private render while retaining prior test history.
- Acceptance: one upper-section refinement uses the expected revision and direction; replacement reaches preview; retest records the new revision and preserves Test 1.
- Validation: disposable prepared-response browser check; focused S2; syntax and diff checks.
- Status: partial. Focused S2 passed. The disposable helper script did not finish within the command window, so the prepared-response revision and test-history flow remains unverified.

## Validation
Observed: `node --check browser.mjs` passed; `git diff --check` passed in both repositories; `npm.cmd run test:e2e -- --grep character-to-costume` passed all four scenarios (48.9s). The disposable browser helper check did not complete within its command window. The requested prepared-response wizard flow is unverified.

## Progress and decisions
Implementation began 2026-11-16. Report evidence and Chromium reproduction confirmed the below-fold targeting failure, unnamed article scope, and optional-label parsing defects. WP1 and WP2 are implemented. Existing user changes in both repositories were preserved.
