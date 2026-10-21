# Character review latency
Status: complete

## Goal and current behavior
Reduce verified character-page save/selection overhead and tolerate denied browser
storage. The reported Assembly batch has 64 candidates. A read-only service profile
took 2.55s: 4,940 path resolutions, 39 JSON reads, and 56 slot prerequisite calls.
The running HTTP detail request took 7.51s; server contention/version may differ.
The supplied console error did not reproduce in a fresh in-app browser.

## Impact and constraints
Owners: library_reference_service.py (portable read/write boundary),
render_slot_service.py (shared slot presentation), zet.js (startup preferences).
Docs: LOCAL_CHARACTERS, DATA_MODEL, Testing. Preserve universe/version/containment
validation, publication integrity, selection fences, and user edits. No persisted
schema change, live generation, production mutations, dependencies or new scenarios.

## Luna sized implementation packets
### WP1 — Deduplicate path conversion within a document
- Files: zet/services/library_reference_service.py.
- Dependencies: none. Reuse identical typed-path conversions only during one walk.
- Acceptance: same decoded/encoded values, invalid paths/owners still rejected,
  later reads observe changes; fewer filesystem resolutions on reported batch.
- Validation: disposable serialization parity/guard checks and read-only profile.
- Status: complete.

### WP2 — Reuse loaded projection and per-view prerequisite results
- Files: zet/services/render_slot_service.py, local_character_progression_service.py,
  local_view_reference_service.py, local_prompt_improvement_service.py.
- Dependencies: none. Compute stage reasons once per view per detail call; use
  already loaded progression/recipe state for presentation rather than decode
  entire state documents again. Disk-backed compiler/reference reads stay fresh.
- Acceptance: unchanged control reasons and pending-slot availability.
- Validation: disposable control parity check; approved S2.
- Status: complete.

### WP3 — Guard startup preferences and verify integration
- Files: zet/web/static/zet.js; affected documentation and this plan.
- Dependencies: WP1/WP2. Default to in-memory filter state when storage is denied.
- Acceptance: blocked storage cannot abort dashboard startup or filter changes.
- Validation: disposable JS denied-storage check, node syntax, approved fast E2E,
  git diff --check and final diff inspection. No permanent tests added.
- Status: complete.

## Risks and validation limits
Caches must be scoped to a single walk/detail call to avoid stale files or state.
Fresh browser console was clean; cannot attribute the exact reported error to Zet
without its stack. Isolated checks do not establish production UI latency or live
model quality. No application restart/deployment is authorized by this plan.

## Progress
Initial path/slot deduplication preserved full detail equality, but reduced the
profile only from 2.60s to 2.26s. Follow-up inspection found projection reloading
the entire candidate state to retrieve progression and recipes. WP2 includes
using the loaded run for those projections. The first disposable guard script
failed its expected-call-count assertion because the fixture reused the same
dictionary object eight times: a later visit saw its already converted absolute
path. Corrected it to independent JSON-style records and reran successfully.

## Final results
Final read-only before/after profile: 2.668s -> 0.928s (65% less profiled service
time), 39 -> 26 JSON reads, 4,940 -> 1,652 path resolutions, 56 -> 8 prerequisite
calls. Entire presented 64-candidate response remained equal. No production
reviews/selections were changed. An isolated temporary copy of the reported batch
saved and reloaded keep/reject/undecided through the real workflow service.

Final `npm.cmd run test:e2e`: all four approved scenarios passed (42.5s), including
Assembly/Dressing selection and publication. Earlier intermediate run passed with
a transient background queue PermissionError; final run was clean. Disposable
serialization checks passed for roundtrip, owner/version/traversal rejection,
per-walk resolution and Body BACK recipe defaults. The optional symlink retargeting
check could not run: Windows denied symlink creation (1314). No permissions changed.
Disposable JavaScript checks passed with blocked and available browser storage;
Python AST, `node --check zet/web/static/zet.js` and `git diff --check` passed.

Affected component/data documentation updated; entry-point ownership and schemas
are unchanged, so no code-map change or ADR is needed. No permanent tests added.
Running server deployment/restart and actual production click timing remain
unperformed; restart Zet and reload the dashboard to apply the local changes.
Exact source of the supplied console error remains unconfirmed.
