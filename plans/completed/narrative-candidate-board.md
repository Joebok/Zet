# Narrative Candidate Board
Status: complete
Specification: Docs/COMPONENTS/CANDIDATE_BOARD.md

## Packets

1. Shared controls and indicators. Added prompt authoring, suggestions, quality pills, lock glyph, and Earlier prompt advisory. Shared cards and review suppress the Complete label.
2. Narrative mount and settings. Mounted one board per target with separate dialog host. Moved prompt and settings to the component and retired duplicate controls and prompt history.
3. Candidate actions and evidence. Routed actions to existing services, retained guarded deletion, and mapped captured prompts, inputs, and comparison images. Reused inline raster delivery.
4. Progress and Luna. Merged compact progress by current occupant and job and refreshed detail on terminal changes. Reconciled interrupted reviews and invalidated rankings on artwork changes.
5. Cleanup and validation. Retired the legacy helper and Narrative review markup. Updated affected documentation and maintained scenario selectors.

## Validation

- npm.cmd run test:e2e passed all four approved fast scenarios. Latest run took 41.0 seconds and emitted a nonfatal Windows socket reset from the test server.
- Disposable Chromium checked Draft/Final pills, locked and Earlier prompt indicators, missing duration, failure, capacity, the always-visible model picker and Write Prompt, custom model names, exact captured prompt and input marker, zoom persistence, compact review, and Escape focus restoration.
- Disposable Python checked inline extensionless PNG delivery, unreadable capture rejection, and Luna invalidation on membership and harvest changes.
- JavaScript syntax, Python AST parsing, and git diff --check passed.
- Live model/render execution, deployment, and real-device checks were outside this implementation run. Task restore, the Inventory jump, lettering confirmation, and concurrent stale-response scenarios were inspected in code but were not separately exercised end to end.
