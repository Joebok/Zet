# Phase-change mode sources
Status: active

## Goal
Support separate Draft and Final phase-change sources for Head Image and Head Image Edit, and configure the existing Tsaeytte Youth batch without rerunning Draft.

## Work packets
- WP1: Implement mode-scoped snapshots, provenance, and cross-pipeline locked-source resolution. Validate with isolated temporary-library checks. Status: pending.
- WP2: Route source selection through mode-aware API, render preparation, review, and staging; preserve existing frozen work. Validate legacy and mode isolation. Status: pending.
- WP3: Add creation and existing-batch source controls with mode-specific previews. Validate both pipelines in a disposable browser. Status: pending.
- WP4: Recheck Adult locks, retain matching Draft provenance, and configure the Youth batch's Final source. Verify unchanged Draft state and prepared Final references. Status: pending.
- WP5: Update affected documentation, run approved E2E and syntax checks, review the diff, and archive this plan. Status: pending.

## Constraints
Preserve existing workspace changes, Draft selections and locks, and frozen requests. Do not start renders or add permanent tests. The existing source update resets Draft work and cannot be used for the requested Final configuration.

## Progress
Local implementation is in progress. Mode-aware source storage, rendering, source API, and dashboard controls have been added. A disposable isolated check verified Final source assignment leaves Draft state unchanged and is idempotent. The first approved fast suite passed four scenarios; a final suite is in progress after further edits. The hosted server is reachable but is serving the previous dashboard controller, so the production batch has not been configured. Source-picker browser validation, runtime availability, and production batch configuration remain outstanding.

After the user updated Zet, the hosted controller was confirmed updated. The Adult Draft and Final FRONT lock keys, candidates, batches and hashes were rechecked, then assigned through the mode-aware source API to Youth batch `20261023_070525_864928`. Before/after comparison preserved Draft selections, candidate paths, hashes, request identities and locks. The served Final snapshot checksum matched the Adult Final lock, and the Final FRONT slot control reported `can_generate: true`. No render was submitted. Browser validation and inspection of a prepared render request remain outstanding.
