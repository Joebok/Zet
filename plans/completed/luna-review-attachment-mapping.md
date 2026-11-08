# Fix Luna review attachment mapping

Status: completed

The Woodland review numbered eight copies of Assembly evidence while omitting
explicit attachment numbers for the eight finished outputs. Queue hashes
confirmed that all outputs were sent.

1. Shared review request in `local_image_ranking_service.py`. Build one ordered
   attachment list and its prompt, with candidates first and verified evidence
   deduplicated. Check the manifest and hashes with a disposable queue replay.
2. Character boards in `character_asset_container_service.py`, after packet 1.
   Supply saved production records and Dressing role guidance. Check mixed
   origins, unavailable inputs and a legacy import in a disposable fixture.
3. Narrative boards in `narrative_generation_service.py`, after packet 1.
   Supply candidate-local evidence and preserve review settlement. Check
   distinct Narrative bindings, run `npm.cmd run test:e2e` and
   `git diff --check`, and update the component docs and code map.

Use isolated fixtures for validation. Preserve the existing board and review
records. Live verification uses an explicit rerun once the fix is deployed.

## Validation

- The read-only Woodland replay staged eight output hashes matching the saved
  review, one shared Assembly attachment, and two correctly mapped frozen prompts.
- Disposable mixed Dressing and Narrative checks passed. They covered the three
  Dressing modes, import without inputs, missing and changed evidence, and
  distinct Narrative bindings.
- `npm.cmd run test:e2e` passed all four scenarios in 44.1 seconds.
  A transient usage-maintenance file lock in the test directory did not fail
  the suite. `git diff --check` passed. Live assessments await deployment.
