# Scoped AI_Proxy render access for issue workers
Status: complete
Related request: Joe wants Codex to queue approved ComfyUI-backed render jobs through AI_Proxy without a separate terminal handoff.

## Goal
Permit an explicit issue-worker render call to use the existing AI_Proxy queue while keeping ordinary issue-worker production configuration loads blocked. Limit creative-library access to a private work root and preserve queue/preset/storage validation. This change prepares the path for later approved render experiments; it does not authorize additional images beyond the completed Tsaeytte pilot.

## Current behavior
`ConfigService.load` rejects every non-development config when `ZET_WORKER_MODE=1`. The private Tsaeytte pilot also refuses submission in worker mode. Its normal-terminal path submits through `AIProxyService.stage_render_task_local_render_ask`, which packages ComfyUI requests into the shared File Proxy queue. Direct ComfyUI HTTP submission is outside Zet's normal route.

## Luna sized work packets

### WP1 — Add an explicit, scoped config load
- Dependencies: none.
- Files/interfaces: `zet/services/config_service.py`; private work root and existing config/preset paths.
- Work: add a named render-only opt-in that can load local production render settings in worker mode only when its work root is a real directory under this checkout's ignored `test-results/`. Bind all creative-library paths in the returned Config to that private root; retain the configured AI_Proxy queue and machine state paths needed for transport. Normal `load` remains blocked.
- Acceptance: standard worker load fails; scoped load returns only a private creative root and current queue/preset; invalid roots and production-role configs fail.
- Validation: disposable Python assertions for positive and negative cases; no live queue call.
- Status: complete. Ordinary worker load and unsafe work roots fail; the scoped load binds creative paths under the private root and retains AI_Proxy transport settings. The production-role check is in code; it was not exercised against a production-role fixture because this checkout's config is local.

### WP2 — Route the private render harness through that opt-in
- Dependencies: WP1.
- Files/interfaces: ignored `test-results/tsaeytte-costume-evidence/pilot.py` and its frozen manifest.
- Work: let its existing hash/budget-checked submission and collection use the scoped config in worker mode. Preserve AI_Proxy staging/collection and the 16-completed-image cap; do not submit a new job from the completed manifest.
- Acceptance: worker-mode dry verification/configuration succeeds, with no source batch or queue mutation; repeat runs on the completed manifest do not submit jobs.
- Validation: `pilot.py verify` and a read-only worker config probe.
- Status: complete. The completed pilot's evaluator connected through AI_Proxy under worker mode and reused 19 existing evaluations without a new ask. Source manifest verification still passes. The next prepared batch will provide the first live submission through this path.

### WP3 — Document and review
- Dependencies: WP1–WP2.
- Files/interfaces: `Docs/DEVELOPMENT.md`, `Docs/INVARIANTS.md`, active plan.
- Work: document the opt-in's narrow purpose, its private root requirement, and the continued AI_Proxy/ComfyUI routing. Review final diff for unrelated changes.
- Acceptance: no global worker guard removal, no direct ComfyUI path, no dependency or permanent test.
- Validation: Python parse/checks, `git diff --check`, source hash verification and final status review.
- Status: complete. Development, invariant and code-map documentation updated; no dependency or permanent test added.

## Constraints
- Do not queue additional Tsaeytte images now; the prior investigation consumed its 16-image budget. A future fix experiment will freeze new asks and state its render budget first.
- Preserve existing user edits in the two local-character prompt-improvement UI files and the prior investigation artifacts.

## Final results
- Added the explicit `worker_render_root` opt-in to `ConfigService.load`. It requires worker mode, this checkout's local `config.toml`, and an existing directory within ignored `test-results/`; returned creative paths point only to that directory. The default issue-worker guard is unchanged.
- Updated the private Tsaeytte harness to use that opt-in and AI_Proxy under worker mode. The completed 16-image manifest does not authorize another render; no new image was queued during validation.
- Validation: disposable worker boundary check passed; `pilot.py evaluate` reused 19 saved evaluations under worker mode; `pilot.py verify` passed for 44 protected sources and 19 recorded asks; Python parsing and `git diff --check` passed. `npm run test:e2e` passed all four approved fast scenarios. A transient Windows file-use warning appeared during usage maintenance, but did not fail a scenario.
- Live submission through the scoped worker path remains unverified until the next separately budgeted experiment.
