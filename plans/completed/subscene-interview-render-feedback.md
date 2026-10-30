# Rendered-image feedback in subscene interviews
Status: complete

## Goal and constraints
Allow a single explicitly chosen subscene render to inform one interview turn.
Freeze the candidate artwork and retain labeled text findings for later turns,
without automatically resending images. Explicit replay uses frozen evidence;
restart clears conversation and findings. Follow the approved conversation plan,
universe isolation, queue ownership, image integrity and existing test policy.

## Work packets
### WP1 — Evidence and transport
- Files: narrative_generation_service.py, narrative_proxy_service.py.
- Validate candidate and vision model before restart; freeze bytes and identity;
  attach only to the current request, preserving recovery and exact replay.
- Acceptance: replacement cannot change frozen evidence; continuation has no image.
- Validation: disposable isolated service checks.
- Status: complete.

### WP2 — Findings and history
- Files: narrative_prompt_service.py, narrative_interview_service.py,
  narrative_generation_service.py.
- Add visual findings, current-image guidance and historical observation labels;
  preserve legacy records, proposal review and restart fencing.
- Acceptance: subsequent turns receive findings but not old pixels.
- Validation: disposable history/replay/restart checks.
- Status: complete; depends on WP1.

### WP3 — Dashboard
- Files: narrative.js and shared model picker as needed.
- Add one-candidate picker, preview, one-turn behavior and replay notice; preserve
  pending selection through polling and reject stale candidate identities.
- Acceptance: attach, submit, continue, replay and restart work as specified.
- Validation: disposable isolated browser checks.
- Status: complete; depends on WP1–WP2.

### WP4 — Validation and knowledge
- Files: affected Narrative, data and AI-job documentation; this plan.
- Run approved E2E baseline, syntax and diff checks; review final diff; record
  observed results and move this plan to completed when all work is done.
- Acceptance: no unapproved permanent tests or production/live service writes.
- Status: complete; depends on WP1–WP3.

## Progress
Existing uncommitted restart-interview changes belong to the preceding authorized
work and were preserved. `npm.cmd run test:e2e` passed all four scenarios (42.2s).
A disposable browser journey passed image selection, preview, candidate-ID request,
and selection retention on a rejected request. Disposable isolated service checks
passed frozen evidence, replacement, text-only continuation, findings, exact replay,
invalid and fresh restart; a transport check verified the staged image and manifest.
Python syntax, JavaScript syntax and `git diff --check` passed. No live AI calls or
production library writes were made. Dedicated browser verification did not exercise
a real vision model; image-based responses require a vision-capable model.
