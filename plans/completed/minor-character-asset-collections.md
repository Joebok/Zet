# Minor Characters on shared Asset Collections and Candidate Boards

Status: complete for implementation and isolated validation

## Implemented packets

1. Versioned collections and offline preview in the Minor Character service
   and migration command. Kept collection IDs, six asset IDs and the original
   session location. Verified Final-lock, Draft-only and corrupt-image fixtures.
2. Prompt writing and interview actions through the shared durable AI workflow.
   Reused Narrative proposal validation and review presentation. Verified
   prepared proposals, explicit application and late-prompt fencing.
3. Shared mixed-quality board and image transport. Verified eight slots,
   Draft and Final on the same board, captured input inspection and off-page
   application using prepared queue answers.
4. Symbolic publication and offline migration. Verified a stable Inventory ID
   across unlock and relock, journal recovery after an interrupted workflow
   write, and migration resume after interruption. Reconciliation recognizes
   the converted records.
5. Documented the workflow, data model, ownership, AI roles and rollout in
   ADR 0050 and the component notes.

## Validation

- The approved `npm run test:e2e` suite passed all four scenarios in 42.5 seconds.
- A disposable browser/API journey passed in 23.5 seconds. It covered the
  Style lock gate, proposal application, preserved alternatives, mixed
  quality, captured inputs, publication, protected deletion and changing
  Style anchors without disturbing a locked view.
- Disposable migration and symbolic-lock recovery checks passed. JavaScript
  syntax, Python imports for the service and migration, and diff checks passed.
- No permanent test scenario was added. Live image quality was outside these
  prepared-response checks.

Production conversion remains a separate reviewed operation. Generate the
universe-specific manifest and obtain approval before applying it with writers
stopped. The existing legacy service remains available to settle its durable
background work before conversion.
