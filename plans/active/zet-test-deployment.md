# Zet Test deployment
Status: active
Related issue/specification: none

## Goal
Provide a separately managed Zet release at 127.0.0.1:8082 using a dedicated library, queue and machine state. Zet_Tester must verify Test release identity before it launches an agent.

## Current behavior
Production releases are staged under Zet_Runtime/releases and run on 8081. Zet_Tester currently starts the development checkout with config.toml on 8081. Production and that config both select ZetTester. AI_Proxy runs against the production queue.

## Desired behavior
Update_Test.ps1 deploys merged origin/main, starts the last Test release, and stops only Test processes. Test config, data, state and AI_Proxy queue are isolated. Zet_Tester validates exact active release identity before a live run.

## Implementation steps
### WP1 - Isolated Test data and config
- Dependencies: none.
- Files/interfaces: Runtime_Test/config.test.toml, Zet_Library_Test, Zet_Test.
- Work: Create isolated library and queue roots, seed a fresh ZetTester descriptor using existing style settings, configure local role and private state paths.
- Acceptance: resolved Test paths are disjoint from production paths and universe selection is ZetTester.
- Validation: load config with release Python and inspect effective paths without constructing ZetApp.
- Status: pending.

### WP2 - Release updater
- Dependencies: WP1.
- Files/interfaces: Update_Test.ps1 and a standard-library Test release controller/launcher.
- Work: fetch and stage merged main, run the approved four-scenario release checks, validate library compatibility, start/stop verified processes on port 8082, atomically record active release only after health identity checks, and restore the prior release on startup failure.
- Acceptance: Deploy, Start and Stop operate only on Test and preserve production health identity.
- Validation: syntax checks and disposable first/repeat deploy, rollback and listener ownership checks.
- Status: pending.

### WP3 - Zet_Tester release identity
- Dependencies: WP2.
- Files/interfaces: Zet_Tester/run.mjs and tester.toml.
- Work: Read active-release.json and require revision, release config path, and selected universe to match before browser or agent startup. Do not start a development server in managed mode.
- Acceptance: configured Test accepted; production or unavailable/mismatched service rejected.
- Validation: existing character-RZ.md --validate.
- Status: pending.

### WP4 - AI_Proxy and operational docs
- Dependencies: WP1, WP2.
- Files/interfaces: private proxy registry/runtime and Zet/Talker documentation.
- Work: Configure a private subscriber rooted at the Test queue and document lifecycle, logs, and shared-backend live-run constraints.
- Acceptance: subscriber validation does not enqueue work or alter production proxy configuration.
- Validation: AI_Proxy validate-subscriber and git diff --check.
- Status: pending.

## Validation
Run the four approved npm E2E scenarios during release staging. Run Zet_Tester character-RZ.md with --validate. Check health and config path on ports 8081 and 8082 and compare production revision and boot ID before and after.

## Risks and alternatives
Both proxy instances use the same Ollama and ComfyUI backends. Test live inference must be scheduled while production inference is idle.

## Progress and decisions
Latest merged origin/main is the selected release source. A dedicated updater is used to keep Test actions separate from production.

## Final results
Pending.
