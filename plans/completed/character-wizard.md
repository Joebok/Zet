# Character Wizard
Status: complete

## Goal

Replace the clipboard interview with a resumable Luna 6 vision interview for creating a character and first phase or editing a saved Character.md. Keep the shared character manual as the template reference.

## Work packets

1. Template authoring and validation. CharacterWizardService uses the repository skeleton, manual, section metadata, universe style and existing validators. Check a valid create draft and verify a targeted edit preserves other source text.
2. Durable interview. Register the Character Wizard role and continuation. Keep ordered references and answers under the owning universe. Check isolated queued responses, reload, retry and cross-universe rejection.
3. Approval. Use the shared onboarding scaffold and creation lock for staged publication. Reuse SourceEditorService for existing masters. Check no pre-approval record, repeated accept, duplicates and stale edits.
4. Dashboard and documentation. Wire New Character and Character Overview, retain manual setup, and remove the clipboard interview. Check Chromium and the maintained fast scenarios.

## Verification

The initial maintained fast suite passed all four scenarios. A disposable browser and API test passed with stubbed queue responses for invalid uploads, one and three references, interview rounds, retry, reload, approval, repeat acceptance, stale and successful edits, inherited style, explicit fallback and universe isolation. The check exposed a Windows line-ending mismatch between model output and the textarea. The wizard now normalizes returned text before comparing it. The final isolated Chromium run on an alternate port passed all five scenarios, including the four maintained tests and the disposable wizard journey. Python AST checks, JavaScript syntax checks and git diff --check passed.

No maintained test was added. Live model adherence was outside the isolated verification.
