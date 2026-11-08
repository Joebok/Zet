# Candidate board controls and character view navigation
Status: complete

## Luna-sized packets

- WP1 groups conditional Costume Dressing, view recipe, and Head FRONT settings in index.html and narrative.css. Acceptance is compact grouping with no space reserved for hidden settings.
- WP2 aligns Aspect ratio and Prompt with generation and groups delete actions in the shared renderer. Acceptance is desktop alignment and narrow wrapping on Character and Narrative.
- WP3 adds the character view picker using the current scope and navigation path. Acceptance is direct switching, deep links, and browser history.

The packets are independently implementable. Validate with the approved fast E2E suite, disposable isolated Chromium checks, JavaScript syntax checks, and git diff --check. Document dashboard behavior and record results before archiving.

## Results

All three packets are complete. The dashboard uses the existing routes and data. The shared toolbar and its Character and Narrative consumers use the updated static asset version.

- `npm.cmd run test:e2e` passed all four approved fast scenarios (42.5 seconds).
- Disposable isolated Chromium validation passed (6.9 seconds). It covered non-FRONT Dressing, Head FRONT, a Body view recipe, Assembly, and a Narrative subscene. It checked desktop and narrow layout, keyboard view navigation, history and reload, a compiled Assembly prompt, and both Character delete confirmations with intercepted preview responses and cancelled confirmation.
- JavaScript syntax checks and `git diff --check` passed.
