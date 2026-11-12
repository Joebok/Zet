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
- Status: complete. Separate library, config and AI_Proxy storage were provisioned. Proxy subscriber validation passed.

### WP2 - Release updater
- Dependencies: WP1.
- Files/interfaces: Update_Test.ps1 and a standard-library Test release controller/launcher.
- Work: fetch and stage merged main, run the approved four-scenario release checks, validate library compatibility, start/stop verified processes on port 8082, atomically record active release only after health identity checks, and restore the prior release on startup failure.
- Acceptance: Deploy, Start and Stop operate only on Test and preserve production health identity.
- Validation: syntax checks and disposable first/repeat deploy, rollback and listener ownership checks.
- Status: in progress. Test is running on 8082 at revision 662a386a4d33e421d8afca7f1f0b691a3185ee0d. The approved release E2E suite passed (4/4). Startup failure/rollback was not induced.

### WP3 - Zet_Tester release identity
- Dependencies: WP2.
- Files/interfaces: Zet_Tester/run.mjs and tester.toml.
- Work: Read active-release.json and require revision, release config path, and selected universe to match before browser or agent startup. Do not start a development server in managed mode.
- Acceptance: configured Test accepted; production or unavailable/mismatched service rejected.
- Validation: existing character-RZ.md --validate.
- Status: in progress. The runner verifies release config path, revision, boot ID and selected universe before live work. Its existing case validation passed. Live Codex work was not started.

### WP4 - AI_Proxy and operational docs
- Dependencies: WP1, WP2.
- Files/interfaces: private proxy registry/runtime and Zet/Talker documentation.
- Work: Configure a private subscriber rooted at the Test queue and document lifecycle, logs, and shared-backend live-run constraints.
- Acceptance: subscriber validation does not enqueue work or alter production proxy configuration.
- Validation: AI_Proxy validate-subscriber and git diff --check.
- Status: in progress. The private registry and runtime are configured. `validate-subscriber zet` passed. Development documentation was added. The C: journal requirement was met while retaining the queue on D:.

## Validation
Run the four approved npm E2E scenarios during release staging. Run Zet_Tester character-RZ.md with --validate. Check health and config path on ports 8081 and 8082 and compare production revision and boot ID before and after.

## Risks and alternatives
Both proxy instances use the same Ollama and ComfyUI backends. Test live inference must be scheduled while production inference is idle.

## Progress and decisions
Latest merged origin/main is the selected release source. A dedicated updater is used to keep Test actions separate from production.

## Final results
The active Test release still includes the legacy fallback that displayed a synthetic Moonsea in the universe chooser. A source fix now limits that fallback to legacy root-level authoring folders; a disposable check found only ZetTester in the Test library. The already deployed release has not yet received this source change. `npm.cmd run test:e2e` passed all four approved scenarios, Tester `--validate` passed, Python/Node syntax checks passed, proxy subscriber validation passed, and `git diff --check` passed. Production remained on port 8081 with its original boot ID. Live Tester execution and Test redeployment with the Moonsea fix remain outstanding.
