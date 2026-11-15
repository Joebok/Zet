# Minor Character Style and Front follow-up
Status: complete
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
- Status: complete. The deployed selector retained its override through reload and navigation, and completed Intake and authoring records reported their effective model.

### WP2 — Correct Front Inventory destination
- Dependencies: none.
- Files/interfaces: `zet/web/static/minor_characters.js`.
- Work: Link to the actual Inventory page using the app's supported route and selection parameter. Confirm the selected asset ID matches the published Front lock.
- Acceptance: Clicking the post-lock link opens Inventory on asset `68aa6508-facb-4092-9d2c-5b64e17117c2`.
- Validation: Browser navigation and selected Inventory asset assertion on the Test workspace.
- Status: complete. Chromium opened the exact published Front asset using the updated Inventory handoff.

### WP3 — Candidate interview keyboard focus
- Dependencies: none.
- Files/interfaces: `zet/web/static/minor_characters.js`.
- Work: Keep the existing review action descriptor and adapter path. Close review, select the candidate as evidence, and focus feedback. Submit only through the page's Interview button. Guard unresolved reviews and give stale reviews an explicit Dismiss action.
- Acceptance: The candidate becomes selected evidence, focus lands in Interview feedback, and a request starts only on explicit submission.
- Validation: Disposable browser check with the authoring request intercepted and inspected; verify candidate ID, evidence selection, focus, and zero backend mutation.
- Status: complete. The updated keyboard flow selected evidence and focused feedback before submission.

### WP4 — Verify review-state preservation during board updates
- Dependencies: none.
- Files/interfaces: `zet/web/static/minor_characters.js` adapter only if a defect is reproduced. Do not edit `candidate_board_component.js` or its stylesheet.
- Work: With a review open, change comparison and zoom, apply a same-candidate progress update, and verify comparison, zoom, focus, and candidate remain stable. Use a disposable fixture or intercepted update so no render or model job is submitted.
- Acceptance: Same-candidate updates retain local review state. Document any adapter-side incompatibility and fix it without expanding the shared component contract.
- Validation: Browser fixture that drives the public board update path and asserts comparison, transform, focus, and candidate identity.
- Status: complete. A prepared progress update preserved candidate, comparison, zoom, and focus with review open.

### WP5 — Final regression checks
- Dependencies: WP1-WP4.
- Files/interfaces: no permanent test additions without approval.
- Work: Re-run the isolated model, navigation, and focus checks. Run the existing approved Character-to-Costume and Narrative smoke scenarios, syntax checks, and diff checks.
- Acceptance: Requested gaps pass, Candidate Board source/stylesheet diff is empty, and no unrelated user changes are included.
- Validation: Existing project commands in `Docs/Testing.md`, JavaScript/Python syntax checks, `git diff --check`.
- Status: complete. Fast regressions, disposable recovery, and the live Style to Front workflow passed. The Gemma-specific prompt failure is recorded below.

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
- Zet Test revision `c8a12a81` was used for live verification. The Authoring Model picker accepted `gemma4:12b`, retained it across reload and navigation, and displayed the effective model on the completed Intake.
- The Gemma workspace `abdabd4f0c0742178254c001380f0267` used Joe Source. Three Intake requests completed in about 43 seconds and filled all three fields. Directions repeated Appearance and included incidental scenery. The saved Style prompt is the next checkpoint for assessing whether those details carry forward.
- After reboot, the existing Gemma Style Write Prompt job `a15ddf09f0284b18bcea8fc3ca766124` had completed. Its queue record spans about 20 minutes including the reboot. Qwen's queued Intake also completed and filled all three fields in workspace `64e1a6b7f90b467fb07b05b9fd0c1dc8`.
- The recovered Gemma Style prompt repeated canonical art-style directions and carried forward the lawn and panel stack. It misread the source shirt's “YOYO” graphic as a drum and “TOYO.” Style Draft slot 1 reproduced these details. The Draft completed in about 134 seconds.
- Gemma's Style interview `05bd45575cc241509f90bdca37596b42` completed in about 37 seconds. AI Queue shows three requests at about 23, 7, and 6 seconds. The proposal matched the requested gray background and preservation constraints without adding a style change. Applying it correctly made the saved prompt stale, then started rewrite `3922a846d970460a9874c55c900b3617`.
- The rewrite (AI Queue request `AI_97aa2ab45c1d8a2d69b278efa3b48fe8`) was still running after eight minutes. The Ollama log showed over 20,000 generated tokens on the active request. AI_Proxy received no output-token limit, and the system instruction was about 25,000 characters including five Qwen guidance modules. These measurements establish an unbounded generation problem on this run. The contribution of the guidance length is unverified.
- The live comparison paused at the Style rewrite before resuming with the capped aliases and managed Ollama recovery.
- The interrupted interview replay passed with prepared responses and the real structured-job service over a disposable queue. After three requests completed across two service instances, each stage had exactly one queue publication and one cached result.
- With managed Ollama enabled, `Zet-Image-2:latest` Style rewrite `57d022485e69454d88b89290df794a5c` triggered an Ollama restart about five minutes after dispatch. AI_Proxy retried under the same queue request `AI_844787c1b415a60bdb48de0c02229450`. The retry reached 12,288 output tokens in about 290 seconds and ended with Ollama's `length` reason. Zet rejected the unterminated JSON. The saved gray-background edit remained available.
- `Zet-Image-1:latest` Style rewrite `431e405d8a7e4f62a6bf8ef2072bcf96` completed in 106 seconds from queue publication to collection, including a storage pause. Its gray background was correct and its scenery was omitted, but the prompt retained Intake's drum, TOYO, and slippers. The test operator corrected the graphic and footwear in the prompt before rendering. Draft `40bcedb0bde347699582b957d9b6d996` showed the gray background, YOYO graphic, plaid trousers, sneakers, and welcoming pose. It was privately locked as the Front reference.
- `Zet-Image-1:latest` completed Front prompt writing, candidate-evidence interview, and prompt rewrite. The initial prompt included stale Intake traits even with the correct locked image attached. The accepted straight-on refinement made the prompt stale. The rewrite used the image as the reference for identity and costume and dropped the inaccurate descriptions. The first prompt took about 69 seconds in the queue, the three interview stages took about 31, 8, and 7 seconds, and the rewrite took about 11 seconds.
- Both Front Drafts completed and their captured inputs matched the exact locked Style image by SHA-256. `codex:gpt-6-luna` ranked the revised Draft `0380ee92a99647b48a03f6b46aafe271` first. The Front lock published approved Inventory asset `bc97ca5a-ada2-4b19-b3c3-96cf12e9fd0e`. Chromium opened that exact asset from Front after reload.
- Live workflow acceptance covers successful execution with local authoring and Luna ranking. Visual details can be refined with the existing Zet tools. Gemma Write Prompt remains model-specific evidence of a capped but unusable response, and the timeout recovery itself was verified. The original zJoe workspace served as the read-only baseline.
