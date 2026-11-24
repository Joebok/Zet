# UI review evidence capture

Create a plan for using Zet_Tester to collect evidence that lets a reviewer assess Zet's interface, explain problems, locate the relevant source, and later verify corrections. Base the design on inspected code and representative workflows.

## In scope

- Extend existing Zet_Tester capture and reporting mechanisms where practical.
- Adapt or create cases when they improve review coverage. This request authorizes planning those changes; execution follows plan acceptance and an explicit request to proceed.
- Inventory active pages and workflow states, then plan direct browser testing for gaps in Zet_Tester case coverage.
- Cover desktop and tablet. Joe selected this scope on 2026-11-24. Phone coverage is outside this plan.
- Plan screenshots, environment metadata, compact UI structure, geometry, selective styles, interaction history, application context, and source references.
- Define an evidence manifest, selective retrieval, storage limits, and a representative bundle example.
- Break implementation and collection into Luna sized work packets with named files, dependencies, acceptance checks, and validation.

## Verified infrastructure

Paths below are relative to Zet unless they explicitly point to the adjacent Tester checkout. Findings are from source inspection on 2026-11-24; no browser runs have verified them during planning.

| Owner | What exists | Implication for this plan |
| --- | --- | --- |
| [Tester runner](../../../Zet_Tester/run.mjs) | Four parsed case types: character, minor-character, narrative-scene, image-generation. Loads template steps/checkpoints, verifies Test release/library scope, launches Codex and the browser, records attempts and verifies final workflow reports. | Add opt-in capture configuration and context here. Do not assume a Playwright test fixture controls these workflows. |
| [Tester browser](../../../Zet_Tester/browser.mjs) | Persistent Chromium context; serial file-based command dispatch through `runAction`; `snapshot` returns `ariaSnapshot` plus grouped select options; `screenshot` writes full-page PNG. No declared viewport profile, geometry export, or structured action ledger. | This is the central checkpoint and action capture boundary. Preserve the existing command contract. |
| [Tester checkpoint parser](../../../Zet_Tester/case-markdown.mjs) | Markdown checkpoint IDs and prerequisites, template fallback, generated prompt-improvement checkpoints. | Workflow restart points are coarser than UI review states. Keep existing restart semantics and add evidence checkpoint IDs separately. |
| [Tester case templates](../../../Zet_Tester/cases/) | Character/Costume, Minor Characters, Narrative through assembly, and Image Generation/reconstruction procedures. | Reuse these user tasks and add a small number of named captures at useful states. Do not run each model variant solely for duplicate UI evidence. |
| [Existing page sweep](../../Scripts/capture-dashboard-ui.mjs) | `capture:ui` takes viewport PNGs, revision/dirty state, route and basic overflow metadata at five fixed sizes. Uses internal page activation and network idle waits. | Reuse the entry point and capture logic, replacing stale destinations, fixed profiles, and readiness assumptions as needed. Internal activation with autosave skipped cannot prove real navigation or unsaved-change behavior. |
| [Fast E2E configuration](../../playwright.config.mjs), [tests](../../tests/e2e/) | Twenty tests in 17 fast spec files; single worker, prepared fixtures, retained failure traces. Separate live spec. | Reuse prepared state patterns for gaps. The 20-test baseline supersedes older four-test notes. Functional coverage does not imply useful screenshots already exist. |
| [Fixture server](../../tests/e2e/server.py) and [runner](../../Scripts/run-e2e.mjs) | Isolated fast/live storage, fixture roots and resume support. Successful E2E runs delete their run directory. | Capture collection must retain its own evidence outside automatically removed test results. Do not silently connect Zet_Tester to the fixture: its active-release guard is a separate contract. |

The current `Zet_Tester/tester.toml` is locally modified and contains a malformed `runs_dir` assignment. `parseSettings` skips malformed lines and the runner then requires this field. This is a source-confirmed startup blocker for that config, not a reason to edit Joe's changes during planning. The example config also omits the runner's required `active_release` key.

## Proposed coverage map

Each row needs explicit captures, direct interaction observations, or an identified blocker. A screenshot of a redirected page does not count for the requested destination. Final route inventory must compare the menu, canonical route mapping, mounted auxiliary pages, and nested workspaces at the revision being reviewed.

| Review surface | Existing Tester coverage | Planned additions and direct checks |
| --- | --- | --- |
| Shell and Character Overview | Incidental to character cases | Context selectors, menus, empty and populated hub, expanded cards, template editor, rename/archive preview and cancel, navigation with unsaved edits. |
| Character Wizard and Costume Wizard | Character template | Intake, interview, editable proposal, acceptance, private costume preview and feedback. Capture before advancing. |
| Body Reference, Head Image Edit, Assembly, Dressing | Character cases | Container overview and board, references, prompt preview, empty/queued/finished/selected/locked states, review/comparison dialog, template improvement and validation feedback. One representative three-view character case first. |
| Minor Characters | Three ready cases and template | Intake, Style and official-view boards, interview/refinement, private versus published locks; direct rename/delete preview and cancel where absent. |
| Image Generation | Coverage case and template | Gallery and asset detail, text/image input, ordered references, style insertion, reconstruction, comparison and correction, review, render/cancel feedback. |
| Stories, scenes, backdrop, subscene, assembly | Tea-party case and template | Story and scene lists/editors, references, interviews, source placement and pinned inputs. Keep this within Narrative and NarrativeStories storage. |
| Narrative crop, lettering, animation | No equivalent Tester case found | Direct journeys informed by existing finishing and animation E2E specs, including editor, validation/confirmation, preview and saved result. These may create drafts even when entered by a seemingly read-only button. |
| Candidates and Zines | No dedicated Tester case found | Candidate source/import review; populated Zine page selection, layout and print preview. Use existing zine E2E preparation patterns where suitable. |
| Identity Keys, Turnarounds, Costumes, Compare | Costume Wizard only covers part of Costumes | Direct source pickers, empty/populated lists, saved output, paired comparison and view navigation. Existing source-consumption E2E provides relevant setup patterns. |
| Image Inventory | Incidental input/output selection | Search/filter, picker, asset detail/edit, reference/alias controls and save feedback. Reuse inventory-edit fixture patterns. |
| Universes, create/settings, species, Template Editor | Partial character/template interaction | Direct list/create/edit states, style/species controls, long content and save/conflict feedback; existing E2E journeys cover several setup paths. |
| AI Queue, Config, Pipeline Inspection/Controls, manuals | Incidental model/job selection | Direct populated/empty/error states where supported, role/model dialogs, long settings, manuals and disclosures. Treat unavailable compatibility controls as such. |
| Recent Renders and shared overlays | No dedicated Tester case found | Recent-result navigation, fullscreen image viewer, image picker, comparison/zoom, notifications, task capture preview and focus return. Do not submit external tasks during review collection. |

Legacy Scene Builder, Streamlit, standalone Render Console, retired batch pages, and Head Image Construct are not active review targets. Canonical redirects should be recorded once as aliases. Old sweep defaults and older dashboard prose contain retired names; inspect source and mounted routes before treating a page as active.

For each surface, use a small set of relevant states: empty, populated, editing, pending, success, validation/error, selected/locked and modal. Mark states as captured, blocked, not applicable, or still missing with a reason. Do not promise every state on every page.

## Proposed capture design

Both collection paths should use one versioned evidence contract:

```text
Tester workflow + named captures ----> shared collector ----> state bundles
Direct browser journeys + page sweep -> shared collector ----> run manifest + coverage ledger
```

Place reusable capture code in a proposed `Zet_Tester/evidence.mjs`. Let Tester's browser controller call it directly; let Zet's capture script load it from an explicit configured path. Keep dependencies one-way: Tester supplies the collector, and Zet's optional capture command consumes it. Do not copy the extractor into both repositories or add a production UI dependency. Confirm this cross-checkout interface in the pilot before expanding coverage.

Add an opt-in `--evidence` mode to Tester, a named `capture` browser command, and a small capture profile/configuration contract. These names are proposals, not existing CLI options. Leave ordinary `snapshot`, `screenshot`, workflow status, resume and result assertions compatible. Capture failure must appear as incomplete evidence separately from functional workflow status; it must not cause a completed render or accepted save to be repeated.

Central hooks can record actions, outcomes and failures without editing every case. Use named captures for meaningful intermediate states, dialogs and durable checkpoint boundaries; do not take expensive bundles after every fill or polling snapshot. Record a before-and-after pair for a selected set of consequential interactions. Keep action failures distinct from observed UI errors.

### Evidence inventory and gaps

| Evidence | Available now | Proposed minimum |
| --- | --- | --- |
| Visuals | Tester full-page PNG; sweep viewport PNG | Viewport PNG for every checkpoint; selective full-page, dialog/region, and scrolled-container images with reasons. Preserve original resolution. |
| Context | Case, inputs, source hashes, prompt/report, checkpoint and attempt files | Reference these records and attach objective, workflow stage, prerequisites, expected outcome and action ID. Clearly distinguish supplied context from observed UI. |
| Environment | Sweep basic dimensions, browser string, route, revision and dirty flag | Browser/version, CSS viewport, DPR, document dimensions, document/container scroll, visual viewport, theme, motion and pointer/touch settings, actual route and active region. Mark desktop zoom unknown when unobservable; visual viewport scale is a separate value. |
| Structure | Tester ARIA snapshot returned to its agent | Persist a compact ARIA snapshot and node table for visible controls, headings, labels, landmarks and selected layout ancestors; include disabled/expanded/selected states and useful hidden-state metadata without dumping hidden text. |
| Geometry | Sweep horizontal overflow booleans | Stable node references within each capture, parent relationships, bounding boxes, scroll/client sizes, clipping ancestors, fixed/sticky positioning and viewport intersection. Report overlap/overflow candidates as observations, not automatic defects. |
| Styling | No dedicated export found | Whitelist fonts, colors, spacing, borders, grid/flex, sizing, overflow and stacking for sampled nodes/ancestors, relevant classes and Zet CSS tokens. |
| Behavior | Codex JSONL and prose report | Structured browser-command ledger with target, timestamps, outcome, active element/focus and related captures; bounded page errors, console errors, failed requests and HTTP failures. Exclude credentials and request/response bodies. |
| Source correlation | Existing IDs/classes, code map and component docs | Small source map from route/region/selector to controller, template, shared component and stylesheet. Include revision and mapping confidence. Keep inferred ownership separate from observed DOM facts. |

Use CSS pixels for geometry. Store both viewport-relative boxes from `getBoundingClientRect` and document scroll offsets. Screenshot records must state their CSS origin, pixel size, scale and crop/scroll transform, so viewport, full-page, region and scrolled-container images can be mapped back to nodes. Do not assume a full-page screenshot reveals clipped inner containers.

Use bounded readiness checks: expected route, active workspace, expected heading/state, relevant image decode and fonts. Polling pages may never become network-idle. Capture loading intentionally when requested, and capture settled content only when its condition passes. Record readiness timeouts, state changes during sampling, missing images and partial files. Do not freeze business timers or suppress actual errors to obtain a clean screenshot.

### Desktop and tablet profiles

Proposed starting profiles reuse the existing 1920x911 desktop and 1133x610 tablet landscape sizes, add 810x1080 tablet portrait, and use 1133x560 only for focused short-height checks. Record actual CSS dimensions, DPR and touch/pointer settings. The short-height profile does not simulate the native iPad keyboard.

Complete each meaningful mutating workflow once. Revisit saved states at other sizes without repeating generation or publication. Capture transient states at the active workflow profile and mark missing cross-size transient evidence honestly. Give image boards, review dialogs, long editors, pickers, navigation and unsaved-change flows priority at both tablet orientations.

Browser touch emulation supports layout and pointer checks. It cannot establish physical iPadOS behavior for clipboard permission, native pickers, fullscreen, virtual keyboard or pen input. Keep any physical-device evidence separately labeled and report unverified device behavior.

## Proposed evidence bundle

Keep evidence under Tester's configured run/attempt directory, with direct journeys writing into a sibling evidence run using the same contract. Use relative artifact paths so a selected bundle can be moved without depending on the original checkout.

```text
<run-or-resume-attempt>/evidence/
  manifest.json
  coverage.json
  README.md
  actions.jsonl
  source-map.json
  captures/
    character-body-front-review/desktop/001/
      state.json
      viewport.png
      ui.aria.yml
      nodes.json
      styles.json
      diagnostics.json
```

The manifest should expose schema version, collector version, run/parent attempt, Tester revision, actual dashboard release revision, dirty state where applicable, context, profiles and capture entries. Do not report the checkout's Git HEAD as the running dashboard revision when Test uses a packaged release. Identify unknown versions explicitly. Coverage entries reference captures or explain gaps; they are not silently counted as passes.

Illustrative `state.json` for the existing character template's Body Reference FRONT review, with placeholders rather than collected evidence:

```json
{
  "schema_version": 1,
  "capture_id": "<run>/<attempt>/character-body-front-review/desktop/001",
  "state_key": "character/body-reference/front/review",
  "origin": "zet-tester",
  "case": "character-Luna",
  "checkpoint": "character-pipelines",
  "profile": "desktop",
  "context": {"universe": "ZetTester", "character": "<case character>", "phase": "Adult"},
  "objective": "Compare a completed FRONT candidate with its references before selecting it",
  "last_action_id": "<open-review-action>",
  "expected": "Candidate, references, saved prompt and review actions are available",
  "observed": {"route": "<actual URL>", "active_region": "<observed region>", "candidate_id": "<observed ID>"},
  "artifacts": {"viewport": "viewport.png", "structure": "ui.aria.yml", "nodes": "nodes.json", "styles": "styles.json", "diagnostics": "diagnostics.json"},
  "capture_status": "<complete|partial|failed>",
  "limitations": []
}
```

The example shows the shape of the record, not a final schema. Before implementation, settle field names and required versus optional data within WP2. Keep stable state keys across runs and unique capture IDs per occurrence/attempt. Match comparisons by state key, data context, profile and revision; unequal data is a documented comparison limit.

## Volume, retention and sensitive data

Index summaries first and keep heavy files separately addressable. Hash artifact bytes and reuse exact duplicate files within a run; retain separate context and occurrence records. Defer visual similarity detection unless exact deduplication and checkpoint selection prove insufficient. Dynamic text and images can change hashes without creating a useful new review state.

Start with one representative case per workflow family and targeted direct journeys, then fill the coverage ledger. Record artifact count, bytes and capture duration in the pilot before proposing limits. Cap diagnostic buffers and optional full-page/scroll captures, and record truncation. Keep prior runs; no automatic retention deletion in this phase. Any later cleanup requires a separate decision about which evidence to remove.

Use Test data. Omit cookies, storage dumps, auth headers, arbitrary environment variables and network bodies. Redact configured sensitive fields in exported text and metadata; if a screenshot would expose one, mask that region explicitly and record the mask. Never silently redact reviewed interface content. Hosted review remains a later choice; do not upload bundles as part of capture.

## Proposed Luna sized work packets

These packets are implementation work to begin only after plan acceptance and an explicit request to proceed. One agent executes them sequentially. Each owns a bounded responsibility; a packet does not authorize delegation.

### WP1 - Finalize coverage and collection configuration

- Dependencies: settle live AI/data boundary below.
- Files/interfaces: this plan; proposed `Zet_Tester/ui-review/coverage.json`, `Zet_Tester/tester.evidence.toml`; `Zet_Tester/tester.example.toml`, `README.md`; menu and canonical route source inspected for inventory.
- Work: enumerate actual active destinations, nested states and shared overlays; select representative cases; map existing outputs and setup prerequisites. Supply a separate valid evidence config, including active release and isolated run output, without overwriting the modified local config.
- Acceptance: every active surface has a collection route, prerequisite and required profiles, or a named blocker/exclusion. Test library, queue and running release are verified before writes.
- Validation: use existing `--validate` for selected cases/config when their Test universe is available. Inspect route mapping and capture coverage independently; case validation does not prove dashboard readiness.
- Status: proposed.

### WP2 - Deliver one complete state bundle

- Dependencies: WP1.
- Files/interfaces: proposed `Zet_Tester/evidence.mjs`, minimal caller in `browser.mjs`, evidence schema/README and source-map records.
- Work: implement viewport capture, environment/context, compact ARIA/node/geometry/style exports, coordinates, manifests and honest partial outcomes. Pilot a populated Character review dialog and a scrolled inner panel.
- Acceptance: a reader can identify a small control in the screenshot, find its node/ancestors/styles and responsible source, and distinguish missing data from absent UI. Artifact paths resolve after moving the bundle.
- Validation: `node --check` on changed modules; disposable Chromium pilot at desktop/tablet sizes; inspect PNGs and compare selected node bounds against screenshots. Add no permanent suite by default.
- Status: proposed.

### WP3 - Integrate Tester capture controls and action records

- Dependencies: WP2.
- Files/interfaces: `Zet_Tester/run.mjs`, `browser.mjs`, `dashboard.mjs` if needed for config selection, README and case templates; preserve `case-markdown.mjs` checkpoint contract.
- Work: wire opt-in mode, profiles, named capture metadata, bounded diagnostics and structured actions. Add only useful checkpoint instructions to four workflow templates and any overriding selected case procedures. Preserve ordinary/resume artifact contracts and before/after associations.
- Acceptance: disabled capture adds no evidence extraction; enabled runs connect captures to case/attempt/actions. Resumes append evidence and never repeat a verified completed write because capture failed.
- Validation: syntax checks, selected case `--validate`, disposable command/attempt exercises including collector failure and duplicate names; inspect generated prompt and resume records. Functional workflow status and evidence completion remain separate.
- Status: proposed.

### WP4 - Cover pages outside Tester workflows

- Dependencies: WP2; WP1 coverage map.
- Files/interfaces: `Scripts/capture-dashboard-ui.mjs`, proposed `Zet_Tester/ui-review/direct-journeys.mjs` and journey definitions, collector interface, relevant existing E2E setup patterns; fixture server only if a concrete setup gap requires a bounded extension.
- Work: share the collector with the existing sweep; select desktop/tablet profiles and canonical routes; replace network-idle-only readiness. Add targeted direct browser journeys for the uncovered rows, with actual controls for navigation, editing, dialogs, focus and scrolling. Avoid adding a generic new Tester case type solely to navigate pages.
- Acceptance: each gap row has populated evidence and representative interaction results, or a documented blocker. Every image records requested and actual page. No retired redirect inflates coverage.
- Validation: syntax checks; run the selected direct journeys against the agreed isolated environment; visually inspect representative populated pages and dialogs at each primary profile. Fixture-only behavior and real Test behavior must be labeled separately.
- Status: proposed.

### WP5 - Collect representative workflows and fill evidence gaps

- Dependencies: WP3, WP4 and required saved data/live execution decision.
- Files/interfaces: selected existing/adapted Tester case files and run outputs; direct journey outputs; coverage ledger.
- Work: collect one character workflow, one Minor Character, one Narrative and one Image Generation journey as available. Reuse completed results for cross-profile inspection, supplement direct pages, and capture transient states intentionally. Stop dependent branches at real blockers without losing completed evidence.
- Acceptance: every required surface/profile/state is represented or explicitly blocked with the last observed state and a next action. Action results, UI evidence and generated image quality are separate outcomes.
- Validation: inspect workflow reports and source/candidate identities, capture completeness and diagnostic errors; open representative screenshots and selectively read bundles. Execution commands depend on the agreed environment and must be recorded exactly when run.
- Status: proposed.

### WP6 - Verify and hand off the review package

- Dependencies: WP5.
- Files/interfaces: evidence manifest/README/coverage and source map; `Zet_Tester/README.md`; [Dashboard UI](../../Docs/COMPONENTS/DASHBOARD_UI.md) capture section and [Testing](../../Docs/Testing.md) if their commands or boundaries change.
- Work: validate paths/schema/coordinates, totals and limits, publish a local review entry point, document selection/comparison instructions, remaining gaps and source ownership. Update Code Map only if significant entry points move.
- Acceptance: a reviewer can start with one compact manifest, select a workspace/state/profile, substantiate an observation and find the relevant implementation without reading an entire run. No review findings or UI fixes are required by this evidence-capture plan.
- Validation: changed module syntax and focused checks; run `npm.cmd run test:e2e` in Zet if Zet capture/fixture integration changed, preserving the 20-scenario baseline; run `git diff --check` and review diffs in both repositories. Do not run the separate live E2E spec unless requested.
- Status: proposed.

## Risks and limits

- Tester's active-release checks and fast E2E's fixture server are different runtime contracts. Choose each journey's runtime explicitly; never weaken the release guard just to reuse fixture preparation.
- Exporting geometry is sampling a changing page. Record observation times and state mismatches; avoid presenting independently captured files as perfectly atomic.
- A source map can identify candidates for investigation but cannot always prove which CSS rule caused a layout. Preserve observed classes, ancestry and computed values alongside inferred ownership.
- Real pending/error states may be brief or unavailable in saved data. Prepared responses can reproduce some presentation states but must be labeled. Do not fabricate captures or intentionally disrupt normal services.
- Heavy capture can alter timing. Collect at named checkpoints, measure the pilot, bound work and preserve normal polling behavior. Retrying a capture must not retry the application action.
- Persisting case-specific text, images and prompts increases storage and may include private material. Keep bundles local and scoped to Test; review any later sharing separately.

## Open questions

- Should collection reuse existing Test results first and allow targeted live AI/model/render work only for missing states, or stay limited to saved results and prepared responses? This changes WP1 preparation and WP5 execution. No live work is authorized by this planning turn.
- The proposed collector location, profiles, packet breakdown and bundle structure await whole-plan review. Routine details can be refined during the pilot within the accepted scope.

## Decisions and planning progress

- Joe selected desktop and tablet coverage on 2026-11-24.
- Local repository planning convention selects this file as the canonical brief. Preserve one agent throughout research and implementation unless Joe later requests delegation.
- The user permits adapting/creating Tester cases for broader review coverage. This does not automatically expand Zet's maintained fast E2E baseline or authorize live model/render calls during planning.
- Current chat title observed as `Plan UI review evidence capture`; no title change was necessary.

## Validation observed

Planning only. Inspected the supplied proposal, plan guidance, knowledge index/code map, relevant dashboard/style/testing documentation, both repositories' capture/browser/runner configuration, case templates, route canonicalization and fast E2E definitions. No tests, dashboard workflows, model calls, resets, or capture implementation have run. `git diff --check` passed for the Zet planning changes. Zet_Tester's pre-existing local `tester.toml` modification remains untouched.
