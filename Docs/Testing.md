# Local testing

AI job repair validation (2026-10-16): the four maintained fast scenarios passed
in 33.4 seconds. The shared prepared-envelope helper now uses protocol terminal
status `SUCCEEDED`; its scenario purpose is unchanged. Disposable isolated checks
passed for read-only inspection, disk discovery by an existing collector, two OS
processes collecting one answer, interrupted image/receipt commits, transport vs.
worker failure, image/cancellation admission, deterministic follow-up identity,
reconstruction replay, a render waiting beyond its caller deadline, and mixed
Image Generation/Assembly/Minor Character work. An intentionally failing legacy
collector did not block a registered handler. No live inference or production
deployment was performed, and no permanent scenario was added.

Zet maintains exactly **four fast Playwright task scenarios** and **one separately invoked live Narrative check**. This is the validation owner for the agent knowledge base. The recovered commits `b3d695a`, `3f6acbe`, and `257fdeb` retired the former Python/browser suites and GitHub Actions gates in favor of representative local tasks. See [AGENTS.md](../AGENTS.md) and the [delivery workflow](../.github/CODEX_WORKFLOW.md). Old test paths in tickets refer agents to this baseline; they are not instructions to recreate deleted tests.

Fast fixtures keep operational storage in a process-unique temporary root outside
the Git checkout, as the production TaskWorkflow guard requires. The E2E server
removes only that exact temp directory at shutdown; it never uses normal Zet
AppData, queue or index roots.

Minor Characters (2026-10-15) were verified with disposable prepared-response service/browser journeys, including selected versus locked views, nonblocking advisory review, source/candidate comparison and Inventory handoffs. Those checks are not maintained scenarios. All three approved scenarios passed (26.7s); see the [completed plan](../plans/completed/minor-characters-workspace.md) for evidence and scope limits.

Scene and story coverage uses `/narrative`, `/api/narrative`, and `NarrativeStories`. Scene Builder and local scene-batch execution are retired; their offline archive has no maintained scenario. Passing the baseline is not evidence of every subsystem contract or live rendering quality.

## Minor Character alignment validation (2026-10-15)

The current style alignment -> selected style -> independent view alignment -> selected view -> true-up workflow passed disposable prepared-response service/API and Chromium journeys. Checks cover one-reference short prompts, selection/lock gates, same-slot repeated carry, recipe-only undo and alternate corrections, regeneration after undo, reload, review failure, immutable publication, stale revisions/late results, excluded retired records, comparison looping, main navigation and feedback edits during an in-flight autosave. Desktop and 800px screenshots were inspected. These scripts/artifacts remain ignored under `test-results`; no maintained scenarios were added.

`npm.cmd run test:e2e` passed all three existing scenarios in 27.7 seconds. Python AST checks, `node --check` for the changed dashboard scripts, and `git diff --check` passed. This establishes isolated software behavior, not live image quality; no live model/render calls or production deployment were performed. See [ADR 0015](DECISIONS/0015-minor-character-alignment.md) and the [completed plan](../plans/completed/minor-character-alignment.md).

## Approved fast scenarios

All four are implemented in [fast.spec.mjs](../tests/e2e/fast.spec.mjs). The S1–S4 names below are navigation labels for those existing scenarios, not extra tests.

| Label / exact test title | User task and assertions | Scope limit |
| --- | --- | --- |
| S1 — `library and narrative authoring save and reload through the dashboard` | Upload/restore the Traveler character template; edit/restore costume name; save story title, scene setting, and element appearance; reload and display the reference image; inspect persisted source files | Uses seeded library images/records. Does not cover every catalog operation, merge, migration or universe lifecycle |
| S2 — `character-to-costume workflow previews prerequisites and creates a real run` | API preview/create/start a front-only Character-Assembly run; deliver a prepared image response; wait for ranking; select/lock; repeat for Costume-Dressing using the assembly prerequisite and verify costume availability | Seeds Body/Head locks and uses one front candidate. Does not generate Body/Head batches or test all views, ranking comparisons, cancellation or recovery |
| S3 — `narrative interview, prompt, render, retry, and final assembly persist` | Dashboard interview proposals, review/Apply and synthesis; render backdrop/subscene; fail and retry a subscene render; select/lock sources; add assembly layers, synthesize/render/select/lock final assembly; reload and verify story summary/image availability | Prepared text/image answers exercise persisted job/application flow, not actual LLM synthesis, image quality, or every provenance/protection case |

S4 — `unified AI queue collects all universes in the background and shares model selection`
was explicitly approved on 2026-10-16. It submits prepared Codex/Ollama work across
Test/TestOther universes, verifies automatic queue loading and filtering, leaves
source pages while collection runs, checks durable history after reload, and verifies
popup mutual exclusion/vision filtering plus server-side capability rejection.
No real AI execution occurs. Fixture envelopes preserve original request bytes and
include terminal output inventories.

The suite mixes browser actions, API calls, and filesystem assertions. In particular S2 is primarily API-driven; do not describe it as a complete browser journey through every character control. [CODE_MAP.md](CODE_MAP.md) maps capabilities to these scenarios and their gaps.

## Commands and prerequisites

Run the default suite with:

```powershell
npm run test:e2e
```

On Windows, `npm.cmd run test:e2e` avoids PowerShell script-policy restrictions. Its pretest setup uses `npm ci` when the locked Playwright packages are missing and installs Chromium only when the matching browser executable is absent. Browser downloads use Playwright's shared user cache, while npm packages are installed into the current checkout or worktree. [package.json](../package.json) calls [playwright.config.mjs](../playwright.config.mjs), which runs only `fast.spec.mjs` on Chromium with one worker, a 90-second scenario timeout, 8-second default assertion timeout, and port **8765**. The local-front helper has a bounded 70-second poll. Reuse of an existing server is disabled; keep suites serial across worktrees and resolve port conflicts before rerunning.

The bootstrap removes only the lifecycle-exported `npm_config_allow_scripts`
override (including case and hyphen variants) from its nested `npm ci`
environment, allowing npm to read script policy directly from `.npmrc` or
`package.json`. It preserves the remaining environment, including `userconfig`,
cache, registry, and other script controls. npm 11.16 rejects that environment
override for project installs even when the original setting came from `.npmrc`;
see [npm's lifecycle export bug](https://github.com/npm/cli/issues/9912).
Do not work around this failure by enabling all scripts, editing allowlists, or
changing locked dependencies.

On 2026-10-13, disposable clean projects running npm 11.16.0 reproduced the old
helper's `EALLOWSCRIPTS` failure. The repaired helper passed cold and warm lifecycle
bootstraps with user `.npmrc`, project `.npmrc`, and `package.json` policies, plus
an uppercase/hyphen environment override. Package manifests, lockfiles, and
configuration files stayed unchanged. The approved `npm.cmd run test:e2e`
baseline then passed all three scenarios in 28.2 seconds using verified Python
3.14.6 through `ZET_TEST_PYTHON`. These bootstrap checks are disposable, not new
maintained scenarios. Issue #46's worker validation receipt at `1c21be2` remains
failed until the repair is integrated into that worktree and its helper validation
is rerun; the passing checkout baseline does not replace that receipt.

On 2026-10-13, directly bootstrapping the failed staged release `8917920` also
passed; its approved `npm.cmd run test:e2e` baseline then passed all three scenarios
(26.3 seconds). This validated staging only; production promotion was not retried.

Use an existing verified Python 3.11+ runtime, project packages, Node, Playwright and Chromium. The configs call `python3 -B tests/e2e/server.py`; verify that interpreter before running. The pretest setup restores only dependencies pinned by `package-lock.json` and the required Chromium browser; it does not change dependency declarations. There is no routine pytest, coverage, lint/type-check, or GitHub Actions test command in the current baseline.

## Fixture and response boundaries

[server.py](../tests/e2e/server.py) copies [tests/library](../tests/library/README.md) into `test-results/narrative-e2e/<mode>/` at process startup. The seed owns `Test/universe.json`, `seed.json`, Traveler character/costume sources, reference images, and prepared response images. It is never written back from a run. App construction seeds Narrative records through real services and creates valid Body/Head batch specs and locks; fixture-only `/__test/*` routes are added by this server, not production routes.

Before each fast scenario, `/__test/reset` replaces the Narrative story and resets the Traveler local lock/batch state and File Proxy folders, then reseeds prerequisites. The app, Test universe, and entity catalog persist within the run; this is **not a full database rebuild per scenario**. S1 restores the source template/costume edits it makes. Library/queue paths are disposable; the derived index uses a separate temporary directory outside Git with exit cleanup. Producer-local queue routes/receipts are keyed by the disposable queue path, distinct from the normal queue.

The server suppresses Ollama catalog refresh and supplies prepared local-prompt observations. Fast helper functions deliver prepared envelopes and images into the private File Proxy folders. Narrative envelopes include proxy-result inventory and an external-consumer harvest marker; local-pipeline answers use their own reconciliation path. This exercises packaging, persistence and supported result application without running the external dispatcher, Ollama, Codex, or ComfyUI. It does not independently prove all readiness, ownership or stale-result rejection branches.

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

Shared reconstruction/true-up (2026-10-15) has no maintained scenario. Ignored disposable prepared-response checks exercise intent-aware reports, original-source render exclusion, corrections/retry, three-view wizard publication, front replacement, selected-result ancestry and stale selection. A disposable browser check exercises both new controls and resume/dirty-field behavior. These checks use isolated storage/prepared models and images; Freydis's actual identity/style quality requires separate visual acceptance. Maintained S1–S3 remain unchanged.

For a change, locate the relevant S1–S4 assertions, run the approved baseline, and inspect uncovered contracts in authoritative code. Do not add tests for retiring Scene Builder/local scene-batch workflows. Plan/test references must distinguish scenario coverage from source-only verification. [DEVELOPMENT.md](DEVELOPMENT.md) records actual command outcomes; [ADR 0004](DECISIONS/0004-local-task-testing-baseline.md) records the policy change.

The existing `/narrative` test links redirect into the mounted dashboard editor. The approved S1–S3 scenarios retain their purpose. The 2026-10-12 retirement used separate disposable/manual migration and Candidates checks; these are not additional maintained tests. No live rendering was performed.

## Narrative interview review checks (2026-10-13)

S3 now verifies that a prepared interview leaves the narrative unchanged until Apply, then
continues its existing prompt/render/assembly journey. The maintained scenario count and
purpose are unchanged. Disposable backend checks used a copy of Group Photo JSON records,
checking review validation, old-reply normalization and exact replay schema, selected apply/
reject/override/Shared behavior, repeat application and first-mention reference bindings.
Original source record hashes remained unchanged. Prompt prose checks used prepared text;
they do not establish live LLM fidelity or rendered height/pose accuracy.

Disposable Chromium checks covered row defaults, explicit choices versus all three bulk actions,
pending-review reload/polling/close/reopen, Shared override clearing, override Save inputs and
collapsed indicators. Prompt comparison checks included unsaved edits, reversion, generated
replacement, reload, an open image review, missing prompts, local crop/reuse and line endings.
Desktop/narrow screenshots were inspected; comparison text contrast was checked after correcting
an inherited code-block color. These scripts/screenshots are ignored `test-results` artifacts,
not additional maintained scenarios. No live model or render services were used.

## Approved disposable slot-fix checks (2026-10-12)
Joe approved four one-time check groups for reported issues: costume batch-link restoration, card containment, current-prompt/Recompile behavior, and overlapping slot actions. The disposable fixture used a separate Test library/private queue, prepared images and rankings, and no live models. All groups passed, including Image Generation containment at 1365/850/640 pixels and preserving an unsaved review choice while images arrived. Scripts/results are ignored `test-results` artifacts, not new maintained scenarios. The approved S1–S3 suite remains unchanged and passed afterward (3 tests, 23.0 seconds). See the [completed plan](../plans/completed/standard-render-slots.md) for limits and exact observations.

## GitHub workflow validation (2026-10-13)

The maintained S1–S3 purpose and count are unchanged. Fixture configuration explicitly
uses Runtime.Role=development. ZET_TEST_PYTHON optionally selects a verified staged
release interpreter for the same baseline. Disposable checks cover capture/retries,
claims/trusted replies/quota, browser attention and two-instance deployment recovery;
these do not create a permanent suite. Worker validation and deployment staging share
a fixed-port check lock outside Git. No live check was run. See the active workflow
plan for exact observed results and remaining real pilot/promotion gates.

Worker validation streams directly to its ignored log. Its timeout stops only the
owned command process tree, avoiding a descendant-held output pipe blocking recovery.
A disposable parent/child timeout check verified retained output and a failed
revision checkpoint. Windows sandbox cleanup may require the saved automatic review
for this exact isolated check; three printed scenario successes without successful
runner completion are insufficient to mark a PR ready.

The real sandbox pilot exposed physical queue-state and compiler-config leaks in
the old fixture. build_app now sets the active fixture config and a fixture-only
queue-state root. Compiler script helpers honor that active config; normal queue
state paths remain unchanged without the test override. Worker validation keeps
locked npm/browser caches inside ignored test-results and selects its own verified
Python environment. These repair the approved scenarios without adding coverage.
