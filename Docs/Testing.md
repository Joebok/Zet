# Local testing

Zet maintains exactly **three fast Playwright task scenarios** and **one separately invoked live Narrative check**. This is the validation owner for the agent knowledge base. The recovered commits `b3d695a`, `3f6acbe`, and `257fdeb` retired the former Python/browser suites and GitHub Actions gates in favor of representative local tasks. See [AGENTS.md](../AGENTS.md) and the [delivery workflow](../.github/CODEX_WORKFLOW.md). Old test paths in tickets refer agents to this baseline; they are not instructions to recreate deleted tests.

Scene and story coverage uses `/narrative`, `/api/narrative`, and `NarrativeStories`. Scene Builder and local scene-batch execution are retired; their offline archive has no maintained scenario. Passing the baseline is not evidence of every subsystem contract or live rendering quality.

## Approved fast scenarios

All three are implemented in [fast.spec.mjs](../tests/e2e/fast.spec.mjs). The S1–S3 names below are navigation labels for those existing scenarios, not extra tests.

| Label / exact test title | User task and assertions | Scope limit |
| --- | --- | --- |
| S1 — `library and narrative authoring save and reload through the dashboard` | Upload/restore the Traveler character template; edit/restore costume name; save story title, scene setting, and element appearance; reload and display the reference image; inspect persisted source files | Uses seeded library images/records. Does not cover every catalog operation, merge, migration or universe lifecycle |
| S2 — `character-to-costume workflow previews prerequisites and creates a real run` | API preview/create/start a front-only Character-Assembly run; deliver prepared image/gate responses; wait for ranking; select/lock; repeat for Costume-Dressing using the assembly prerequisite and verify costume availability | Seeds Body/Head locks and uses one front candidate. Does not generate Body/Head batches or test all views, ranking comparisons, cancellation or recovery |
| S3 — `narrative interview, prompt, render, retry, and final assembly persist` | Dashboard interview/synthesis; render backdrop/subscene; fail and retry a subscene render; select/lock sources; add assembly layers, synthesize/render/select/lock final assembly; reload and verify story summary/image availability | Prepared text/image answers exercise persisted job/application flow, not actual LLM synthesis, image quality, or every provenance/protection case |

The suite mixes browser actions, API calls, and filesystem assertions. In particular S2 is primarily API-driven; do not describe it as a complete browser journey through every character control. [CODE_MAP.md](CODE_MAP.md) maps capabilities to these scenarios and their gaps.

## Commands and prerequisites

Run the default suite with:

```powershell
npm run test:e2e
```

On Windows, `npm.cmd run test:e2e` avoids PowerShell script-policy restrictions. Its pretest setup uses `npm ci` when the locked Playwright packages are missing and installs Chromium only when the matching browser executable is absent. Browser downloads use Playwright's shared user cache, while npm packages are installed into the current checkout or worktree. [package.json](../package.json) calls [playwright.config.mjs](../playwright.config.mjs), which runs only `fast.spec.mjs` on Chromium with one worker, a 90-second scenario timeout, 8-second default assertion timeout, and port **8765**. The local-front helper has a bounded 70-second poll. Reuse of an existing server is disabled; keep suites serial across worktrees and resolve port conflicts before rerunning.

Use an existing verified Python 3.11+ runtime, project packages, Node, Playwright and Chromium. The configs call `python3 -B tests/e2e/server.py`; verify that interpreter before running. The pretest setup restores only dependencies pinned by `package-lock.json` and the required Chromium browser; it does not change dependency declarations. There is no routine pytest, coverage, lint/type-check, or GitHub Actions test command in the current baseline.

## Fixture and response boundaries

[server.py](../tests/e2e/server.py) copies [tests/library](../tests/library/README.md) into `test-results/narrative-e2e/<mode>/` at process startup. The seed owns `Test/universe.json`, `seed.json`, Traveler character/costume sources, reference images, and prepared response images. It is never written back from a run. App construction seeds Narrative records through real services and creates valid Body/Head batch specs and locks; fixture-only `/__test/*` routes are added by this server, not production routes.

Before each fast scenario, `/__test/reset` replaces the Narrative story and resets the Traveler local lock/batch state and File Proxy folders, then reseeds prerequisites. The app, Test universe, and entity catalog persist within the run; this is **not a full database rebuild per scenario**. S1 restores the source template/costume edits it makes. Library/queue paths are disposable; the derived index uses a separate temporary directory outside Git with exit cleanup. Producer-local queue routes/receipts are keyed by the disposable queue path, distinct from the normal queue.

The server suppresses Ollama catalog refresh and supplies prepared local-prompt observations. Fast helper functions deliver prepared envelopes/images/gate text into the private File Proxy folders. Narrative envelopes include proxy-result inventory and an external-consumer harvest marker; local-pipeline answers use their own reconciliation path. This exercises packaging, persistence and supported result application without running the external dispatcher, Ollama, Codex, or ComfyUI. It does not independently prove all readiness, ownership or stale-result rejection branches.

Failure traces are retained under `test-results/playwright`. `/__test/retain-failure` copies the Test library, queue, and fixture config to `test-results/narrative-e2e/failures/scenario-<number>-<title>/`. Inspect these plus terminal output before rerunning; another run prepares fresh mode data.

To inspect the seed in a separate dashboard process and port, run:

```powershell
npm run test:library
```

This opens `http://127.0.0.1:8766/narrative` against an inspection copy. Stop the server with `Ctrl+C`.

Inspection uses `test-results/narrative-e2e/inspection`, not the normal library. It shares port 8766 with the live check; do not run both at once.

## Optional live Narrative check

The live check is separate and is never part of the fast suite:

```powershell
$env:ZET_LIVE_TEST_ENABLED = "1"
$env:ZET_LIVE_TEST_NARRATIVE_MODEL = "your-installed-ollama-model"
$env:ZET_LIVE_TEST_CHECKPOINT = "your-installed-comfyui-checkpoint"
# Optional when ComfyUI is not at its default address:
$env:ZET_LIVE_TEST_COMFYUI_URL = "http://127.0.0.1:8188"
npm run test:e2e:live
```

It preflights the Zet and AI Proxy Python runtimes, the configured Ollama model, and the ComfyUI service/checkpoint. It starts AI Proxy with a run-local registry, runtime configuration, and private queue; normal AI Proxy configuration and queues are not changed. Prepared backdrop and subscene inputs keep the live portion focused on real final-assembly prompt synthesis and rendering. Its overall timeout defaults to 20 minutes and can be changed with `ZET_LIVE_TEST_TIMEOUT_MS`. Missing prerequisites block the live check; Joe reviews artistic quality.

[playwright.live.config.mjs](../playwright.live.config.mjs) selects only [live.spec.mjs](../tests/e2e/live.spec.mjs), port **8766**, one worker, 30-second assertions, and `test-results/playwright-live`. The server expects sibling `AI_Proxy` with its existing `.venv` runtime; it starts a private File Proxy process with external ComfyUI and records `test-results/narrative-e2e/live/ai-proxy.log`. The check verifies final synthesis/render completion, selection/lock, reload and displayed/published image. It skips when the explicit enable flag or preflight requirements are absent; **skipped means unverified, not passed**. Run only when Joe requests this live check, and follow the existing ComfyUI operating instructions.

## Coverage policy

Joe explicitly approves each new test, scenario, or material coverage expansion. The approval must identify the user task and why the existing scenarios are insufficient. Existing tests can be repaired to preserve their approved purpose. Do not add exhaustive cases, snapshots, coverage targets, test frameworks, or dependencies without that approval.

For a change, locate the relevant S1–S3 assertions, run the approved baseline, and inspect uncovered contracts in authoritative code. Do not add tests for retiring Scene Builder/local scene-batch workflows. Plan/test references must distinguish scenario coverage from source-only verification. [DEVELOPMENT.md](DEVELOPMENT.md) records actual command outcomes; [ADR 0004](DECISIONS/0004-local-task-testing-baseline.md) records the policy change.

The existing `/narrative` test links redirect into the mounted dashboard editor. The approved S1–S3 scenarios retain their purpose. The 2026-10-12 retirement used separate disposable/manual migration and Candidates checks; these are not additional maintained tests. No live rendering was performed.

## Approved disposable slot-fix checks (2026-10-12)
Joe approved four one-time check groups for reported issues: costume batch-link restoration, card containment, current-prompt/Recompile behavior, and overlapping slot actions. The disposable fixture used a separate Test library/private queue, prepared images/gates/rankings, and no live models. All groups passed, including Image Generation containment at 1365/850/640 pixels and preserving an unsaved review choice while images arrived. Scripts/results are ignored `test-results` artifacts, not new maintained scenarios. The approved S1–S3 suite remains unchanged and passed afterward (3 tests, 23.0 seconds). See the [completed plan](../plans/completed/standard-render-slots.md) for limits and exact observations.
