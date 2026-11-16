# Narrative control names and tester targeting
Status: active

## Goal
Fix Narrative Scene form labels and make repeated elements, targets, and assembly controls addressable from Zet Tester.

## Work packets

### WP1 - Stable accessible field names
- Files: zet/web/static/narrative.js.
- Work: separate field labels from guidance, associate help with aria-describedby, and retain existing field IDs and form names.
- Acceptance: Appearance notes and direction fields resolve by concise labels.
- Validation: S1 authoring and disposable browser checks.
- Status: complete.

### WP2 - Named repeated records
- Files: zet/web/static/narrative.js.
- Work: name element actions, assignment checkboxes, target cards, source options, and assembly layer cards by their records.
- Acceptance: repeated records are independently locatable while their record IDs remain action targets.
- Validation: S3 and disposable duplicate-item checks.
- Status: partial. Target title collisions and source element mapping remain to verify.

### WP3 - Tester locator safeguards
- Files: Zet_Tester/browser.mjs and run.mjs.
- Work: reject ambiguous controls/options, support article scopes, and use the top visible dialog for actions.
- Acceptance: helper fails safely when ambiguous and can target a uniquely named control in an article.
- Validation: script syntax and browser helper checks.
- Status: partial. Integration scenarios remain.

### WP4 - Regression and knowledge updates
- Files: tests/e2e/fast.spec.mjs, Narrative and Tester docs.
- Work: update existing S1/S3 locators and document targeting syntax.
- Acceptance: existing suite passes and docs match helper behavior.
- Validation: npm.cmd run test:e2e, node --check, git diff --check.
- Status: partial.

## Progress
S1 and S3 locators were updated after accessible names changed. A follow-up E2E suite passed 4/4. Earlier full-suite attempts timed out and showed Windows file sharing noise. No live inference was used.

