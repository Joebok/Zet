# Character regen current inputs
Status: complete

## Goal
Regenerate using current eligible references while retaining slot ownership and frozen retry inputs.

## Work packets
- WP1: Aligned compact revision and candidate review context with the worker. Complete.
- WP2: Render action contexts fence target slots and selections independently of source freshness. Complete.
- WP3: Preparation checks current reference bytes, source identity and governing source hashes before commit; it repeats up to three times on drift. Frozen Retry remains unchanged. Complete.
- WP4: Approved fast suite passed all four scenarios (43.9s). A disposable real Assembly operation queued a regenerated FRONT with ordered Body and Head references (11.3s). Stubbed checks covered five pipeline identities and both modes for changed/missing sources, target fencing, reprepare and frozen Retry. Real compilers outside Assembly and live rendering were not exercised. Complete.

## Constraints
Do not change production queue or library data, add permanent tests, or run live rendering. Preserve selection, lock, universe, attempt, and ordered binding guards.
