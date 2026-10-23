# Development and verification

## Responsive UI verification (2026-10-19)

Implemented compact navigation, viewport-anchored image review, shared card/action
styles, and touch image input; see [Dashboard UI](COMPONENTS/DASHBOARD_UI.md) and
the [active acceptance plan](../plans/active/ipad-responsive-ui-and-style-consistency.md).
Verified Python 3.14 through `python3` before fixture runs. The existing
`npm.cmd run test:e2e` four-scenario suite passed in 41.1 seconds. Changed browser
scripts and the capture script passed `node --check`; `git diff --check` passed.
Disposable fixture/browser checks and known gaps are recorded in [Testing](Testing.md).

The capture command now requires `ZET_DASHBOARD_URL`; it defaults to a fresh ignored
output directory instead of deleting `Docs/UI` captures. Final reports/captures
for 25 destinations at five sizes are under ignored `test-results/ui-responsive-final`.
The inspection fixture cannot fully load Pipeline Controls without legacy
`Pipelines.json`. Physical-iPad/native clipboard acceptance remains open. An
existing Image Generation backend `self.app` AttributeError blocked its prepared
render-submission check; the UI viewer was inspected using prepared browser data.
No production process was started, restarted, or deployed for this work.

Run commands from the repository root. [Testing](Testing.md) owns the approved four-scenario fast baseline, isolated Test library, and separately invoked live Narrative check. Use [CODE_MAP](CODE_MAP.md) for implementation navigation and [AGENTS](../AGENTS.md) for authority boundaries.

## Verification note (2026-10-17)

Storage recovery and AI job cleanup changes passed a disposable isolated check for
a transient root-stat failure and deletion of a `RECOVERY_REQUIRED` record with no
producer metadata. `npm.cmd run test:e2e` passed all four approved scenarios
(39.1 seconds). No production queue, library, or live AI service was used.

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
| Approved fast tests | `npm run test:e2e` | Four serial Playwright task scenarios against disposable fixtures. The pretest setup restores locked npm packages and the matching Chromium browser when missing. |
| Inspect test library | `npm run test:library` | Separate inspection copy on 127.0.0.1:8766; see [Testing](Testing.md). |
| Optional live Narrative check | `npm run test:e2e:live` | Run only when Joe requests it, with the environment and prerequisites in [Testing](Testing.md). |
| Three.js vendor update | `npm run build:three` | Copies runtime assets via [copy-three-runtime.mjs](../Scripts/copy-three-runtime.mjs); run only for relevant asset changes. |
| UI capture | `npm run capture:ui` | Inspect [capture-dashboard-ui.mjs](../Scripts/capture-dashboard-ui.mjs) arguments and target before running. |

Configure platform base paths in [config.toml](../config.toml), then universe binding applies; see [DATA_MODEL](DATA_MODEL.md). Zet and AI Proxy must share the queue root. The launchers' 0.0.0.0 host exposes the service on network interfaces; the explicit local command above uses loopback.

Machine-local state is configured in `[Storage]`; Windows production uses
`E:/Zet/AppData`, and the shared AI queue remains at `BaseAIQueuePath`. Start with
the read-only report and cutover preview before relocating any existing files:

```powershell
python3 -B -m zet.scripts.manage_storage --config config.toml
python3 -B -m zet.scripts.manage_storage --config config.toml --cutover-preview
```

The cutover preview is bounded and includes file paths/checksums for proposed
operational copies; regenerate it after stopping Zet/collector/worker processes.
Preview does not copy, delete or modify its source. Review the complete manifest;
then `--migrate-from <manifest> --confirm-offline` verifies the source inventory,
copies each file with checksum verification, and preserves the original. Rebuild
the configured universe indexes and run `--verify-indexes` before restarting.
`--apply` is an explicit seven-day local queue-retention sweep. `--compact-indexes`
is an explicit offline operation; stop all Zet instances first. Never copy old
derived index databases during relocation. Shared transport and the external archive
remain report-only until their records have verified ownership and no remaining
consumer.

Fast browser tests use fixed port **8765**, one worker, and a disposable fixture under the system temp directory's `Zet-test-results/<checkout-name>/run-*/narrative-e2e/fast` (or `ZET_TEST_RESULTS_ROOT/run-*/narrative-e2e/fast`). [server.py](../tests/e2e/server.py) prepares this fixture from [tests/library](../tests/library/README.md). Successful runs remove their fixture and Playwright output; failed runs retain both. Run suites serially across worktrees because they share the port. The fast suite uses prepared queue answers; live artistic quality remains unverified.

## LAN and Tailscale HTTPS on Joe's Windows machine

Use **https://zet.schonbok.net** on the LAN or **https://zet2.schonbok.net** through
Tailscale. Caddy handles both certificates and forwards requests to the existing
Python server on port 8081; Python still uses its normal startup.

[LAN HTTPS troubleshooting](LAN_HTTPS.md) is the primary reference for the DNS,
certificate renewal, Windows service/firewall, private files, diagnostic commands,
credential changes, and recovery. The [completed deployment plan](../plans/completed/lan-https.md)
records the original implementation and acceptance checks.

## Observed verification

**V5 recovery, verified on 2026-10-11:** `npm.cmd run test:e2e` passed all **3 scenarios in 21.5s**. No packages were installed and the optional live check was not run. The recovered application, testing, configuration, and workflow files match the source V5 tip. See the [recovery plan](../plans/completed/recover-v5-history.md).

**Documentation refresh at `676e048`, verified on 2026-10-11:** `npm.cmd run test:e2e` completed the existing **3 fast scenarios successfully**. Playwright's `test-results/playwright/.last-run.json` reported `passed` with no failed tests. Python 3.14.6 and Node v24.18.1 were verified. No packages, tests, or scenarios were added; the inspection server and optional live check were not invoked.

**Machine-local storage cutover, verified on 2026-10-16:** configured storage is
active at `E:/Zet/AppData`. The offline copy checksum-verified 45,364 files
(69,729,912 bytes); a daily retention pass removed 25,125 expired completed-detail
files (46,752,461 bytes) and protected receipt-less and unresolved records. The
fresh Moonsea index has one active generation and passed SQLite `integrity_check`
at 2,437,120 bytes after application reconciliation. Dashboard health, universe
discovery, job/recent-harvest endpoints and selected image access were checked; the
selected image checksum matched the library record. The shared AI Proxy was
restarted with 0 queued and 0 running jobs. The approved old C: queue and migration
state files and old index set were removed; a residual-only preview also found and
removed two stale index databases under the same approved Indexes root. The old
C: Indexes root is absent and the old queue tree contains no files. The shared
transport queue and external archive were not cleaned; the archive scan remains
bounded/incomplete. The dashboard's `project/.indexed-dashboard/entity-library`
provider error was traced to valid assets without linked entities and fixed by
allowing their indexed semantic category to remain empty. The persisted error
clears on the next dashboard reconciliation. `npm.cmd run test:e2e` passed all
four approved scenarios (32.1s);
Python compilation and `git diff --check` passed. No live model/render request was
issued.

### Historical verification before V5 recovery

The first documentation audit recorded 185 Python passes, 12 subtest passes and two cutover fixture failures across two selections. That suite is retired: these are **historical results, not outstanding failures in the approved E2E baseline**. The original commands/results can be recovered with `git show 676e048:Docs/DEVELOPMENT.md`; the [original completed plan](../plans/completed/agent-knowledge-base.md) preserves its audit outcome. Do not run or recreate deleted tests merely to reproduce that historical check.

## Existing-library path update

Install and select a release whose readers/writers support the library's path format, then stop every Zet server and harvester for that library. The command reads `config.toml` and universe descriptors without constructing `ZetApp`, applies recognized typed path updates, and verifies them directly. Pass every known former library root explicitly; repeat `--old-library-root` and `--route-root` when needed:

```powershell
python3 -B -m zet.scripts.normalize_library_references `
  --config config.toml `
  --old-library-root "C:\Users\Joe\Projects\Zet_Library_v5"
```

If `python3` is unavailable, verify a Python 3 fallback as described above and use it for the command. A nonzero result includes unresolved operational record/field references. The report separately counts old-root text outside typed path fields; that text stays unchanged. The command writes atomically per JSON record, creates no backup payloads, and stores a compact local report with counts and a content fingerprint. Do not open converted data with an older release; code rollback alone is incompatible. For recovery that requires an older reader, use the retained library copy. Applying this command to the production library and restarting production are separate rollout actions.

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

## Portable library-reference implementation validation (2026-10-14)

Python 3.14.6 compilation, `git diff --check`, and disposable checks for two relocations, old-root mapping, typed prompt-source hashes, shared run-state writes, queue routes, checksum preservation, traversal/foreign-universe rejection, full updater apply/verify, and byte-stable reruns passed. An earlier approved E2E run passed all three scenarios. The latest run after shared state writers were converted passed S2/S3 but timed out in S1: the Narrative list response returned a different story ID than `/__test/context`, and loading that ID returned 404. This mismatch remains unresolved; no tests or scenarios were added. No live library update, production restart, or live rendering was performed.

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


## Unified AI jobs validation (2026-10-16)

`npm.cmd run test:e2e`: **4 passed (34.2s)**. The explicitly approved new isolated scenario
is included. Python AST and changed browser-script syntax checks, introduced Markdown
links, and `git diff --check` passed. Disposable prepared-response checks covered
restart continuation, duplicate application, incomplete transfer, retained harvest
failure/retry, ownership fencing, offline/malformed model catalogs and recoverable
history. A transient Windows state-read sharing violation was found and repaired
before the final Zet baseline passed. No dependencies or live backend calls were
added. Upgrade AI_Proxy registrations before migrated Zet; no production rollout
was performed. See the [completed plan](../plans/completed/unified-ai-jobs.md).

## Storage recovery verification (2026-10-17)
The approved four-scenario `npm.cmd run test:e2e` baseline passed after the storage
recovery implementation. Python compilation and JavaScript syntax checks passed;
`git diff --check` passed. No maintained scenario was added or expanded. The
prepared local-answer helper now preserves the ask's actual attempt ID, and the
fixture Runtime folder isolates recovery evidence from normal application state.

Disposable checks passed for fresh execution attempts behind a logical job ID,
root identity/two-probe recovery, offline bootstrap with real ZetApp construction,
C-resident continuation reservation, incomplete index scan rejection, missing
catalog protection, child publication reattachment and protected runner rechecks.
A controlled proxy crash preserved its surviving worker's local slot while cloud
work ran; successful old execution published without replay. A deliberately stalled
probe returned paused status without blocking independent resources or spawning
more workers. Initial validation exposed a fixture attempt mismatch and a repeated
completion race; the helper and receipt barrier were repaired before passing runs.

Real E: disconnection, live inference, manual external-backend settlement and
production deployment/restart were not performed. Operational contracts and code
owners: [storage recovery](COMPONENTS/STORAGE_RECOVERY.md).
