# Minor Character Style and Front follow-up
Status: active
Related specification: [Candidate Board](../../Docs/COMPONENTS/CANDIDATE_BOARD.md)

## Goal
Finish the Minor Character Style and Front usability work while keeping the shared Candidate Board component, stylesheet, and public contract unchanged.

## Verified current behavior
- The six Asset Container cards wrap at 1440, 768, and 390 px. Each preview measures 160 px high.
- A Test workspace completed Intake, Style interviews with rejection and acceptance, prompt rewriting, Style Draft generation and Luna review, private Style locking, Front interviews with acceptance, Front Draft generation and Luna review, and published Front locking.
- Inventory contains approved Front asset `68aa6508-facb-4092-9d2c-5b64e17117c2`.
- Prompt and interview jobs recorded `codex:gpt-6-luna`. Intake completed but did not expose its effective model in its public job record.
- Candidate review opens with focus on Close. Zoom In scales the image, and Close returns focus to the originating candidate control.
- The Candidate Board Interview action posted the intended candidate ID and populated the evidence selector. Focus did not end up in Interview feedback after the dialog closed.
- The Front Inventory link points to `?page=inventory`, which falls back to Recent Renders rather than opening Inventory.
- zJoe was not modified. Test workspace: `zJoe - Pipeline Review 20261115`.

## Implementation packets
### WP1 — Complete model selection and effective-model reporting
- Dependencies: none.
- Files/interfaces: `zet/web/templates/index.html`, `zet/web/static/minor_characters.js`, `zet/services/minor_character_service.py`.
- Work: Use one vision-capable Authoring Model picker across the container and all six views. Persist the workspace choice for the current browser session and freeze the resolved model at submission. Keep Luna's ranking model identified separately.
- Acceptance: Each action can use its role default or an explicit vision-capable model. Submitted jobs expose the model that actually ran. AI Jobs agrees with the workspace record.
- Validation: Isolated ZetTester workspace, one default and one explicit override across the three text actions; refresh and compare job records.
- Status: pending. Intake and prompt model controls were not visible in the deployed Test UI. Intake effective model was not present in its completed job response.

### WP2 — Correct Front Inventory destination
- Dependencies: none.
- Files/interfaces: `zet/web/static/minor_characters.js`.
- Work: Link to the actual Inventory page using the app's supported route and selection parameter. Confirm the selected asset ID matches the published Front lock.
- Acceptance: Clicking the post-lock link opens Inventory on asset `68aa6508-facb-4092-9d2c-5b64e17117c2`.
- Validation: Browser navigation and selected Inventory asset assertion on the Test workspace.
- Status: pending. Current link opens Recent Renders.

### WP3 — Candidate interview keyboard focus
- Dependencies: none.
- Files/interfaces: `zet/web/static/minor_characters.js`.
- Work: Keep the existing review action descriptor and adapter path. Close review, select the candidate as evidence, and focus feedback. Submit only through the page's Interview button. Guard unresolved reviews and give stale reviews an explicit Dismiss action.
- Acceptance: The candidate becomes selected evidence, focus lands in Interview feedback, and a request starts only on explicit submission.
- Validation: Disposable browser check with the authoring request intercepted and inspected; verify candidate ID, evidence selection, focus, and zero backend mutation.
- Status: pending. Candidate ID handoff and evidence selection passed. Focus assertion failed.

### WP4 — Verify review-state preservation during board updates
- Dependencies: none.
- Files/interfaces: `zet/web/static/minor_characters.js` adapter only if a defect is reproduced. Do not edit `candidate_board_component.js` or its stylesheet.
- Work: With a review open, change comparison and zoom, apply a same-candidate progress update, and verify comparison, zoom, focus, and candidate remain stable. Use a disposable fixture or intercepted update so no render or model job is submitted.
- Acceptance: Same-candidate updates retain local review state. Document any adapter-side incompatibility and fix it without expanding the shared component contract.
- Validation: Browser fixture that drives the public board update path and asserts comparison, transform, focus, and candidate identity.
- Status: pending. Zoom and close focus were checked, but no progress/update was driven while review remained open.

### WP5 — Final regression checks
- Dependencies: WP1-WP4.
- Files/interfaces: no permanent test additions without approval.
- Work: Re-run the isolated model, navigation, and focus checks. Run the existing approved Character-to-Costume and Narrative smoke scenarios, syntax checks, and diff checks.
- Acceptance: Requested gaps pass, Candidate Board source/stylesheet diff is empty, and no unrelated user changes are included.
- Validation: Existing project commands in `Docs/Testing.md`, JavaScript/Python syntax checks, `git diff --check`.
- Status: pending.

## Constraints
Use Zet Test and disposable fixtures. Keep zJoe unchanged. Do not add maintained tests, scenarios, or dependencies. Preserve the Candidate Board component, stylesheet, and adapter contract.

## Progress
- The end-to-end Style and Front workflow completed on Test. Style slot 3 is privately locked. Front slot 2 is locked and published.
- Corrected the earlier Unknown quick character session diagnosis: test API detail requests must use the dashboard's active universe context and omit the extra `universe_id` query parameter. Browser and matching API requests succeeded.
- The checkout implements the shared selector, exact Inventory handoff, view navigation, interview handoff, review guard, and explicit dismissal.
- The narrower authoring packet sends one request per blank Intake field. Interviews observe each frozen image separately and generate the scoped proposal from their labeled observations. New jobs freeze the effective model and call sequence. Older active jobs retain the original sequence. Write Prompt remains a single call.
- All four existing fast scenarios passed in 44.3 seconds. Disposable service checks passed for the Intake request shape, Interview attachment separation, shared model, empty proposals, pending continuation propagation, and stage-specific failures.
- A separate service check rejected stale acceptance and blocked replacement of pending review by Interview or Write Prompt. Dismissal cleared the stale review without editing the template.
- A disposable Chromium check loaded the updated workspace UI with prepared progress. Candidate identity, comparison, 1.25× zoom, and focus survived a render status update. Keyboard handoff selected evidence and focused feedback without submitting a request. The workspace model choice survived reload and navigation. Left Profile used the locked Style reference, Continue to Front worked, and Inventory opened the exact published Front asset.
- The running Zet Test release is `0c232154`. The live local-model comparison requires a Test runtime running the updated backend.
