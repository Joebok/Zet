# Prompt Generator Pilot rotation mode
Status: complete
Related specification: user-approved plan in this chat (2026-10-25).

## Goal and current behavior
Add Doll-dressing and Rotate creation choices to Costume Dressing Pilot, with one
resumable session per view and mode. Reuse CostumeRotationService and the existing
guided four-seed cycle. Before this change Pilot always used normal slot preparation and
discovered one active session per view. Stage Rotation already compiled the correct
ordered dressed edit base / Assembly orientation reference / costume resources.

## Impact and constraints
Owners: rotation preparation, PromptPacket, LocalPromptGeneratorService,
PromptGeneratorCycle, PilotAIReview, batch/Pilot browser controls and Qwen adapter.
Documentation: Local Characters, Prompts, Data Model, Invariants, Code Map, Testing.
Preserve legacy hashes and read-only migration, immutable reference bytes, universe
isolation, approval gates, separate adoption/selection/locking and Head-Image Edit.
No new dependencies, permanent tests, live AI calls, production writes or deployment.

## Work packets
- WP1 (complete): costume_rotation_service.py; retain facts/declarations from compiler.
  No dependencies. Accept unchanged ordered staging; validate isolated compilation.
- WP2 (complete): local_prompt_generator_service.py and models/prompt_generator.py;
  mode-specific frozen hashed packets. Depends WP1. Validate disposable packet checks.
- WP3 (complete): prompt_generator_cycle_service.py and adoption provenance;
  mode-specific discovery/restart and legacy defaults. Depends WP2. Validate isolated
  coexistence/resume/archive/restart/replay and invalid mode checks.
- WP4 (complete): batch/Pilot JS/template, review context and Qwen adapter; creation
  dialog and mode labels/guidance. Depends WP3. Validate node --check and isolated browser.
- WP5 (complete): affected knowledge and final review. Depends WP1-WP4. Validate
  npm.cmd run test:e2e, Python syntax, git diff --check; archive this plan on completion.

## Progress and results
- Initial inspection: clean checkout; authoritative owners match the approved plan.
- Existing source-selection recipes and nearest selected-view fallback are reused.
- Disposable compilation exposed normal dressing's incompatible source-angle lock.
  Rotate now uses its compiler-specific required clauses instead of dressing constraints.
- Packet declaration parsing separates decoded declaration containers from reference
  entries; verified actual rotation-template source-map extraction and frozen analysis bytes.
- Session mode defaults live in projections, leaving legacy stored packet hashes intact.
- Entity library publication retains mode and ordered reference roles/source view.
- Extended ADR 0032 with the approved mode-specific session identity and constraints.

## Final results
- All five packets complete. Mode dialog, immutable packets, independent resume,
  mode-preserving restart, AI context and adoption/catalog provenance implemented.
- `npm.cmd run test:e2e`: four scenarios passed twice (39.1s, final 39.6s).
- Python AST for six changed modules, node --check for both changed JS files,
  git diff --check and final diff review passed.
- Disposable isolated checks passed eight Stage Rotation handoffs, unchanged source
  batch bytes, overlays, packet parity/metadata/roles, legacy file/hash preservation,
  invalid modes, frozen resume after recipe changes, restart failures/success,
  concurrent opens, two prepared guided rounds per mode, replay, adoption, catalog
  provenance and corrupt-image rejection. Existing guided harness passed five-round
  Doll-dressing and Head-Image Edit regressions including retries and late-result fences.
- Chromium passed real batch dialog/default/cancel/source label, unrendered target,
  mode-specific resume, reload/history/restart and desktop/narrow containment. No
  uncaught browser errors; screenshots inspected. Evidence: ignored test-results/pilot-rotation/.
- No permanent tests, dependencies, live model calls, normal-library writes or
  deployment. Live artistic quality is unverified. No remaining implementation blockers.
