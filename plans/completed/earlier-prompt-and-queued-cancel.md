# Earlier prompt badges and queued render cancellation
Status: completed

## Goal
Show the shared Earlier prompt badge and withdraw unclaimed image renders across all four active boards.

## Work packets
1. Authored prompt comparisons in Minor Characters and Image Generation. Verify saved edits and completed/upscaled evidence.
2. Character view prompt checks via its compiler. Verify effective template edits and unchanged output.
3. File Proxy withdrawal and metadata cleanup. Verify claim race and interrupted save in an isolated queue.
4. Character, Minor Characters, and Narrative actions. Depends on packet 3. Verify slot and attempt ownership and Draft preservation.
5. Image Generation child cancellation and shared card feedback. Depends on packet 3. Verify sibling preservation and slot reuse.

## Validation
Disposable private queue checks, npm run test:e2e, and git diff --check.


## Implementation and decisions
- Use the ready Ask rename as the dispatch boundary. The hidden bundle and short-lived
  board cleanup intent allow interrupted cancellation to resume. A claimed job
  continues through normal harvest.
- Use saved prompt text and original generation evidence. Character compares compiled
  text for the open view. Prompt differences are advisory and persist with the
  candidate or Image Generation assignment.
- Route the shared card action through the existing workflow actions. Queued
  upscales preserve their Drafts and ad hoc multi-render batches keep sibling indices.

## Observed validation
- Disposable private-queue checks passed for all four boards. They exercised stale
  attempt rejection, claim then harvest, interrupted withdrawal recovery, prompt
  changes before harvest, queued upscale cancellation, sibling harvests, slot
  reuse, and locking a candidate with an Earlier prompt badge.
- Disposable Chromium check passed for the Narrative Cancel button, empty-slot reuse,
  and already-started feedback with a simulated dispatcher claim.
- Python AST and changed JavaScript syntax checks passed. `git diff --check` passed.

- npm.cmd run test:e2e passed all four approved fast scenarios (44.0 seconds).
