# Local testing

Zet maintains a small Playwright suite for Joe's local application. It has exactly three fast task scenarios: library and Narrative authoring, Character-Assembly followed by Costume-Dressing, and the new Narrative Scenes pipeline through final assembly. Scene and story coverage uses `/narrative`, `/api/narrative`, and `NarrativeStories`. The retiring Scene Builder and local scene-batch workflows remain usable in the dashboard but have no maintained test coverage.

Run the default suite with:

```powershell
npm run test:e2e
```

Each scenario receives a fresh disposable Test universe. Its library, local pipeline state, File Proxy queue, generated images, and SQLite index are isolated from normal application data. Playwright runs serially with bounded waits and retains failure traces and logs under `test-results`.

To inspect the seed in a separate dashboard process and port, run:

```powershell
npm run test:library
```

This opens `http://127.0.0.1:8766/narrative` against an inspection copy. Stop the server with `Ctrl+C`.

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

## Coverage policy

Joe explicitly approves each new test, scenario, or material coverage expansion. The approval must identify the user task and why the existing scenarios are insufficient. Existing tests can be repaired to preserve their approved purpose. Do not add exhaustive cases, snapshots, coverage targets, test frameworks, or dependencies without that approval.
