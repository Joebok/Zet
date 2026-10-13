# Development and verification

Run commands from the repository root. [Testing](Testing.md) owns the approved three-scenario fast baseline, isolated Test library, and separately invoked live Narrative check. Use [CODE_MAP](CODE_MAP.md) for implementation navigation and [AGENTS](../AGENTS.md) for authority boundaries.

## Runtime and prerequisites

- Python **3.11+**, declared in [pyproject.toml](../pyproject.toml). Prefer `python3`. If unavailable, verify a fallback with `<candidate> -c "import sys; assert sys.version_info.major == 3"`, then reuse it. Verification here used Python 3.14.6 on Windows.
- Runtime packages are [requirements.txt](../requirements.txt): FastAPI, Markdown, NumPy, Pillow, Uvicorn, OpenCV. No routine Python unit-test suite or GitHub Actions test workflows remain after V5 recovery.
- Browser tooling is [package.json](../package.json), [playwright.config.mjs](../playwright.config.mjs): Playwright/Chromium, Three.js, and Node. Python server rendering/templates and checked-in static files serve the normal dashboard.
- Optional AI Proxy, Ollama, ComfyUI, and Narrative Codex subprocess tooling are needed only for corresponding live features. Fast E2E fixtures do not establish that those services/models are available.
- Restore dependencies already declared by the project's lockfiles when needed. Ask Joe before adding, upgrading, replacing, or working around dependencies.

## Setup and execution

Only commands explicitly reported under Observed verification were executed successfully. Setup, inspection launch, vendor copying and the optional live check were not run during this documentation refresh.

| Purpose | Command / source | Notes |
| --- | --- | --- |
| Windows virtual environment | `.\setup_venv.bat` | Creates `.venv`, upgrades pip and installs runtime requirements; inspect [script](../setup_venv.bat). |
| macOS environment | `python3 -m venv .venv`, `source .venv/bin/activate`, `python3 -m pip install -r requirements.txt` | README workflow; installation needs authorization. |
| Windows launch | `.\run_zet_web.bat` | Activates `.venv`; refuses a duplicate 0.0.0.0:8081 listener; script uses its environment's `python`. |
| macOS launch | `./run_zet_web.command` | zsh launcher checks port 8081 and executes `python3`; unlike the Windows launcher, it does not activate `.venv`, so select the environment first. |
| Explicit local launch | `python3 -B -m zet.web.app --config config.toml --host 127.0.0.1 --port 8081` | Browser at localhost:8081. `Ctrl+C` stops it. App construction initializes stores/recovery; use an appropriate library, not an accidental live test target. |
| Approved fast tests | `npm run test:e2e` | Three serial Playwright task scenarios against disposable fixtures. The pretest setup restores locked npm packages and the matching Chromium browser when missing. |
| Inspect test library | `npm run test:library` | Separate inspection copy on 127.0.0.1:8766; see [Testing](Testing.md). |
| Optional live Narrative check | `npm run test:e2e:live` | Run only when Joe requests it, with the environment and prerequisites in [Testing](Testing.md). |
| Three.js vendor update | `npm run build:three` | Copies runtime assets via [copy-three-runtime.mjs](../Scripts/copy-three-runtime.mjs); run only for relevant asset changes. |
| UI capture | `npm run capture:ui` | Inspect [capture-dashboard-ui.mjs](../Scripts/capture-dashboard-ui.mjs) arguments and target before running. |

Configure platform base paths in [config.toml](../config.toml), then universe binding applies; see [DATA_MODEL](DATA_MODEL.md). Zet and AI Proxy must share the queue root. The launchers' 0.0.0.0 host exposes the service on network interfaces; the explicit local command above uses loopback.

Fast browser tests use fixed port **8765**, one worker, and a disposable fixture in `test-results/narrative-e2e/fast`. [server.py](../tests/e2e/server.py) prepares this fixture from [tests/library](../tests/library/README.md). Run suites serially across worktrees because they share the port. The fast suite uses prepared queue answers; live artistic quality remains unverified.

## Observed verification

**V5 recovery, verified on 2026-10-11:** `npm.cmd run test:e2e` passed all **3 scenarios in 21.5s**. No packages were installed and the optional live check was not run. The recovered application, testing, configuration, and workflow files match the source V5 tip. See the [recovery plan](../plans/completed/recover-v5-history.md).

**Documentation refresh at `676e048`, verified on 2026-10-11:** `npm.cmd run test:e2e` completed the existing **3 fast scenarios successfully**. Playwright's `test-results/playwright/.last-run.json` reported `passed` with no failed tests. Python 3.14.6 and Node v24.18.1 were verified. No packages, tests, or scenarios were added; the inspection server and optional live check were not invoked.

### Historical verification before V5 recovery

The first documentation audit recorded 185 Python passes, 12 subtest passes and two cutover fixture failures across two selections. That suite is retired: these are **historical results, not outstanding failures in the approved E2E baseline**. The original commands/results can be recovered with `git show 676e048:Docs/DEVELOPMENT.md`; the [original completed plan](../plans/completed/agent-knowledge-base.md) preserves its audit outcome. Do not run or recreate deleted tests merely to reproduce that historical check.

## Debugging and failure triage

| Symptom | Inspect first |
| --- | --- |
| Import/module failure | Verified interpreter, dependencies, repository working directory, and [fixture server](../tests/e2e/server.py) logs |
| Server starts but work is not ready | `/api/health` in [web/app.py](../zet/web/app.py), index/recovery status, per-workflow jobs; health is HTTP readiness |
| Library appears empty/stale | Correct universe and request context, authoritative catalog, indexed generation/freshness/error rows; do not delete authoritative SQLite |
| Local source is unavailable | Locked flag, stale marker, batch ID/spec, locked image existence/checksum, qualifier/view |
| Jobs do not move | Queue root agreement, ask/running/answer readiness, producer and universe ownership, local route, external worker; see [QUEUES](COMPONENTS/QUEUES.md) |
| Answer is ignored | Current attempt, superseded marker, receipt, job status, output readiness, relevant service's ownership validation |
| Local backend/profile rejected | [local_render_policy.py](../zet/services/local_render_policy.py), registered Qwen profile/diffusion model, external service availability |
| Prompt has wrong views or references | Source map, dependency manifest, ordered inputs, tagged template domains, generation/analysis variants; see [PROMPTS](COMPONENTS/PROMPTS.md) |
| Windows replacement/lock errors | Persistent workflow locks, atomic-write retries, another process/Dropbox holding files; do not remove live locks |

Useful artifacts include `Prompt_Source_Map.json`, `Prompt_Compile_Diagnostics.json`, `dependency_manifest.json`, queue ask/answer/proxy-result/harvest manifests, Narrative job errors, and local run state. [PerformanceInstrumentation](../zet/services/performance_instrumentation.py) can record endpoint timings when supplied to `create_app`; [ProcessService](../zet/services/process_service.py) discovers dashboard/harvester processes. Queue debug retention can be enabled via `ZET_AI_QUEUE_DEBUG` or config; respect receipt/retention logic rather than retaining arbitrary shared payloads.

## Known knowledge gaps and future investigation

- Live AI Proxy cross-machine synchronization, ComfyUI node/model compatibility, Ollama, Codex availability, and visual output quality were not tested. macOS launch was not exercised here.
- The three fast scenarios passed after recovery and again during this documentation refresh. They do not establish exhaustive subsystem coverage or live rendering quality; the previous Python/browser suites are retired.
- Traditional/local generation, record/entity catalogs, and Scene Builder/Narrative coexist. Some README/design notes predate active policy. Investigate the relevant boundary before proposing retirement/migration; this task does not approve it.
- Large facade/routes and callback-driven catalog/index integration warrant impact tracing for cross-component edits. No general refactor or architectural cleanup assessment was performed.
- No repository-wide lint/type-check command is declared in package scripts or pyproject. Do not invent a required check or infer quality from existing cache directories.

## Observed Narrative retirement validation (2026-10-12)

`npm.cmd run test:e2e` passed the unchanged three fast scenarios in 23.9 seconds.
Migration apply/verify and actual resume confirmed 2 stories, 28 scenes and 28 exact
legacy image checksums; resume did not alter Narrative JSON. Source folders and the
existing three-scene Narrative story matched the backup byte-for-byte. Disposable
Candidates/source-review/usage/deletion checks and a read-only dashboard inspection
passed. `git diff --check`, JavaScript syntax and active Python parsing passed.
No live model/render check was run. [Completed plan](../plans/completed/narrative-scene-retirement.md)
records commands/outcomes, backup and remaining stub review issues.

## Render-slot implementation validation (2026-10-12)
Approved `npm.cmd run test:e2e` passed all three fast scenarios after backend/recovery integration (24.8 seconds); S2 also passed independently. Default Windows `python3` resolves to an unusable WindowsApps alias on this host. Verified Python 3 at `C:/Python314/python.exe`; an ignored `test-results/runtime/python3.cmd` shim was placed first on the command's PATH for the harness. Python compilation, JS syntax checks for changed slot browser files, and `git diff --check` passed. Restricted-network Chromium bootstrap failed; the approved pinned setup/suite succeeded with sandbox escalation. No production dependencies or maintained tests were added, and no live renderer or normal creative library was used. Joe subsequently approved four disposable follow-up checks: costume batch-link restoration, card containment, current-prompt/Recompile behavior, and overlapping slot actions. They passed using prepared responses, including live arrivals during review with an unsaved human decision preserved, late cleared-answer fencing, and Image Generation containment at 1365/850/640 pixels. The final approved fast baseline also passed (3 tests, 23.0 seconds). Full Body/Head generation and general recovery remain outside maintained coverage. See [completed plan](../plans/completed/standard-render-slots.md).

## GitHub pickup and production releases

[GitHub task workflow](GitHub_Task_Workflow.md) owns capture/setup, worker authority,
quota and deployment. Automated work sets ZET_WORKER_MODE=1 and loads only disposable
development configuration. prepare_issue_workspace prepares the existing inspection
seed from an isolated worktree; it does not load the live library. Production uses
Zet_Runtime/releases/<sha> with stable state and its existing authored-data roots.
After the first explicit promotion, run_zet_runtime.bat starts that release. Merged
main must contain the new deployment contract before first promotion. Inspect
runtime/state operation records and production.log for recovery; do not reset local
edits or move/rebuild creative data to bypass a blocker.
