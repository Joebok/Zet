# UI review evidence capture

Create a plan for using Zet_Tester to collect evidence that lets a reviewer assess Zet's interface, explain problems, locate the relevant source, and later verify corrections. Base the design on inspected code and representative workflows.

## In scope

- Extend existing Zet_Tester capture and reporting mechanisms where practical.
- Adapt or create cases when they improve review coverage. Joe explicitly authorized implementation of this plan on 2026-11-24.
- Inventory active pages and workflow states, then plan direct browser testing for gaps in Zet_Tester case coverage.
- Cover desktop and tablet. Joe selected this scope on 2026-11-24. Phone coverage is outside this plan.
- Perform all selected workflows as new runs on the release under review. Earlier runs used different releases and cannot supply evidence or generated workflow outputs for this campaign.
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
| [Fast E2E configuration](../../playwright.config.mjs), [tests](../../tests/e2e/) | Twenty tests in 17 fast spec files; single worker, prepared fixtures, retained failure traces. Separate live spec. | Reuse journey and assertion patterns for gaps, and prepared fixtures for collector validation. Review evidence must come from fresh runs on the selected Test release. The 20-test baseline supersedes older four-test notes. |
| [Fixture server](../../tests/e2e/server.py) and [runner](../../Scripts/run-e2e.mjs) | Isolated fast/live storage, fixture roots and resume support. Successful E2E runs delete their run directory. | Capture collection must retain its own evidence outside automatically removed test results. Do not silently connect Zet_Tester to the fixture: its active-release guard is a separate contract. |

The current `Zet_Tester/tester.toml` is locally modified and contains a malformed `runs_dir` assignment. `parseSettings` skips malformed lines and the runner then requires this field. This is a source-confirmed startup blocker for that config, not a reason to edit Joe's changes during planning. The example config also omits the runner's required `active_release` key.

The local Test active-release record currently names revision `d6143b9f4c7550e8b3ec3dd56cc86c3ebb5b60d1`, matching the checkout HEAD observed during planning. This is a file/source observation, not a live health check or a permanent choice of campaign release. Tester's existing startup check compares `/api/health` revision, instance and boot ID with the active-release record.

## Agreed freshness and release boundary

All selected Character, Minor Character, Narrative and Image Generation cases must run from their beginning, including their AI authoring, rendering and review steps. Adapt cases to use unique campaign names and current prerequisites. Earlier screenshots, reports, candidates, locks, accepted wizard sessions and generated scene outputs are historical material only; they do not satisfy this campaign's evidence requirements.

Pin the Test release at campaign start and record its revision, release/config identity and boot ID. Verify these through the active-release record and `/api/health` before each run, on resume and at capture checkpoints. If the release changes, stop collection and start a separate campaign; do not combine versions into one review package. A restart with the same revision still requires identity, storage and in-flight-work reconciliation before continuing.

Use original reference files and explicitly declared Inventory inputs as case inputs, with their hashes and provenance recorded. These are distinct from generated results from an earlier run. When a direct journey needs generated character or scene outputs, it must use results created by this campaign. Keep dependency order: fresh character publication can provide sources for Identity Keys/Turnarounds/Compare, and fresh Narrative assembly can provide sources for lettering/animation/Zines.

Generate each selected workflow once, then revisit its newly created states at desktop and tablet sizes. Reusing this campaign's outputs for cross-profile captures avoids duplicate generation and keeps the compared data consistent. This does not permit reusing outputs from older runs. Interrupted new runs may resume only within the same campaign/release after verifying saved scope and current work.

Prefer unique names and additive test data. Do not reset or delete older work to obtain a fresh run. Preserve existing protected-effect previews and explicit approvals if deletion becomes necessary. All model/render work goes through Zet and AI_Proxy. This decision defines future collection scope; planning does not start those runs.

Use prepared responses only to validate the collector or as separately labeled supplemental diagnostics when a state cannot safely be reproduced. They do not replace fresh Test-release workflow evidence or turn a missing live state into a completed coverage item.

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
| Narrative crop, lettering, animation | No equivalent Tester case found | Direct journeys using fresh campaign assembly outputs, informed by existing finishing and animation E2E interactions, including editor, validation/confirmation, preview and saved result. Entry actions can create drafts. |
| Candidates and Zines | No dedicated Tester case found | Candidate source/import review; populated Zine page selection, layout and print preview, using fresh campaign sources. Reuse existing zine journey patterns. |
| Identity Keys, Turnarounds, Costumes, Compare | Costume Wizard only covers part of Costumes | Direct source pickers, empty/populated lists, saved output, paired comparison and view navigation, using fresh published campaign outputs. Existing source-consumption E2E provides interaction patterns. |
| Image Inventory | Incidental input/output selection | Search/filter, picker, asset detail/edit, reference/alias controls and save feedback on new campaign items. Reuse inventory-edit journey patterns. |
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

Add a campaign ID, pinned release identity, run start time, input provenance, newly created output IDs, and per-capture health identity. The campaign index joins Tester runs and direct journeys without copying them. A capture with unknown or mismatched release identity remains in diagnostics but cannot satisfy review coverage. Source references must resolve against the captured release, rather than an unrelated current checkout.

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

The example shows the shape of the record, not a final schema. Settle field names and required versus optional data in WP2a before writing the extractor. Keep stable state keys across runs and unique capture IDs per occurrence/attempt. Match comparisons by state key, data context, profile and revision; unequal data is a documented comparison limit.

## Volume, retention and sensitive data

Index summaries first and keep heavy files separately addressable. Hash artifact bytes and reuse exact duplicate files within a run; retain separate context and occurrence records. Defer visual similarity detection unless exact deduplication and checkpoint selection prove insufficient. Dynamic text and images can change hashes without creating a useful new review state.

Start with one new representative case per workflow family and targeted direct journeys, then fill the coverage ledger. Do not rerun every model variant unless it exercises a distinct interface state required by the inventory. Record artifact count, bytes and capture duration in the pilot before proposing limits. Cap diagnostic buffers and optional full-page/scroll captures, and record truncation. Keep prior runs as history; no automatic retention deletion in this phase. Any later cleanup requires a separate decision about which evidence to remove.

Use Test data. Omit cookies, storage dumps, auth headers, arbitrary environment variables and network bodies. Redact configured sensitive fields in exported text and metadata; if a screenshot would expose one, mask that region explicitly and record the mask. Never silently redact reviewed interface content. Hosted review remains a later choice; do not upload bundles as part of capture.

## Proposed Luna sized work packets

These packets are implementation work to begin only after plan acceptance and an explicit request to proceed. One agent executes them sequentially. Each owns a bounded responsibility; a packet does not authorize delegation.

### WP1 - Finalize coverage and a fresh campaign configuration

- Dependencies: none; freshness and live-run scope are settled above.
- Files/interfaces: this plan; proposed `Zet_Tester/ui-review/coverage.json`, `Zet_Tester/tester.evidence.toml`; `Zet_Tester/tester.example.toml`, `README.md`; menu and canonical route source inspected for inventory.
- Work: enumerate active destinations and state requirements; select representative cases and unique campaign names; identify original inputs and new-output dependencies. Supply a separate valid evidence config, active-release identity and isolated output root without overwriting the modified local config.
- Acceptance: every active surface has a collection route, prerequisite and required profiles, or a named blocker/exclusion. Verify Test library, queue, source inputs and running release before writes; no old generated output can satisfy a new case prerequisite.
- Validation: use existing `--validate` for selected cases/config when their Test universe is available. Inspect route mapping and capture coverage independently; case validation does not prove dashboard readiness.
- Status: complete.

### WP2a - Capture visuals, context and the manifest

- Dependencies: WP1.
- Files/interfaces: proposed `Zet_Tester/evidence.mjs`, minimal caller in `browser.mjs`, schema/README.
- Work: implement opt-in viewport capture, environment/context, release identity, versioned manifests, unique capture paths and partial outcomes. Define required/optional fields and screenshot transforms.
- Acceptance: a state bundle is readable and movable, its release/profile/context are explicit, and incomplete files or release mismatches cannot be counted as completed evidence.
- Validation: `node --check` on changed modules; disposable Chromium capture at desktop/tablet sizes; inspect PNGs, manifest references and failure records. Add no permanent suite by default.
- Status: complete.

### WP2b - Add structure, geometry, styles and source correlation

- Dependencies: WP2a.
- Files/interfaces: collector extraction module, node/style schema and source-map records.
- Work: persist compact ARIA and node structure, bounded geometry/ancestor/styles, clipping/scroll information and release-specific source ownership. Add region and scrolled-container captures only where needed.
- Acceptance: a reader can locate a small control in a screenshot, correlate its node/ancestors/styles and source, and distinguish observed facts from inferred layout concerns.
- Validation: syntax checks; disposable populated dialog and inner-scroll pilot; compare selected node bounds with PNGs and test crop/scroll transforms. Pilot fixture images validate capture mechanics only.
- Status: complete.

### WP3 - Integrate Tester capture controls and action records

- Dependencies: WP2b.
- Files/interfaces: `Zet_Tester/run.mjs`, `browser.mjs`, `dashboard.mjs` if needed for config selection, README and case templates; preserve `case-markdown.mjs` checkpoint contract.
- Work: wire opt-in mode, profiles, named capture metadata, bounded diagnostics and structured actions. Add only useful checkpoint instructions to four workflow templates and any overriding selected case procedures. Preserve ordinary/resume artifact contracts and before/after associations.
- Acceptance: disabled capture adds no evidence extraction; enabled runs connect captures to case/attempt/actions. Resumes append evidence and never repeat a verified completed write because capture failed.
- Validation: syntax checks, selected case `--validate`, disposable command/attempt exercises including collector failure and duplicate names; inspect generated prompt and resume records. Functional workflow status and evidence completion remain separate.
- Status: complete.

### WP4a - Share collection with direct browser journeys

- Dependencies: WP2b; WP1 coverage map.
- Files/interfaces: `Scripts/capture-dashboard-ui.mjs`, proposed `Zet_Tester/ui-review/direct-journeys.mjs`, collector interface.
- Work: load the shared collector in the existing sweep, add selected profiles/canonical destinations and bounded readiness, and define the direct-journey context/action contract. Enforce the same release identity as Tester.
- Acceptance: one direct browser journey creates the same bundle format and records requested/actual page, profile and release. Retired redirects cannot inflate coverage.
- Validation: syntax checks and a disposable navigation/collector smoke check. Production review captures follow WP5; fixture checks are labeled validation only.
- Status: complete.

### WP4b - Define character and library gap journeys

- Dependencies: WP4a.
- Files/interfaces: direct journey definitions for Character Overview, Identity Keys, Turnarounds, Compare and Image Inventory.
- Work: encode targeted visible-control interactions and named captures, consuming fresh campaign character outputs and creating uniquely named key/turnaround/Inventory items as needed. Include rename/archive/delete previews and cancel without deleting older data.
- Acceptance: these gap rows have executable state prerequisites and useful captures for both device classes.
- Validation: syntax and disposable journey mechanics; actual source selection, populated UI and interaction evidence verified during WP5.
- Status: complete.

### WP4c - Define Narrative production gap journeys

- Dependencies: WP4a.
- Files/interfaces: direct journey definitions for finishing/lettering, animation, Candidates and Zines.
- Work: adapt interaction patterns from existing approved E2E specs to campaign-created Narrative outputs. Capture editing, source selection, preview, validation/confirmation and saved result where applicable.
- Acceptance: downstream states have traceable fresh source IDs and remain within Narrative storage and API boundaries.
- Validation: syntax and disposable mechanics; execute on fresh Test-release outputs during WP5, not archived scene data.
- Status: complete.

### WP4d - Define settings, navigation and shared overlay journeys

- Dependencies: WP4a.
- Files/interfaces: direct journey definitions for Universes/settings/species, Template Editor, AI Queue/Config, Pipeline Inspection/Controls, manuals, Recent Renders and shared dialogs.
- Work: cover uncovered controls and important states; use campaign-owned settings/items, restore any temporary global settings and record restoration, cancel external task submission. Inspect focus, actual navigation, scroll and long-content behavior.
- Acceptance: each listed surface has a bounded journey or explicit unavailable-state record; settings changes and restoration are recorded.
- Validation: syntax and disposable mechanics; final capture against pinned Test release during WP5. Physical-device behaviors stay explicitly unverified unless observed on hardware.
- Status: complete.

### WP5 - Collect representative workflows and fill evidence gaps

- Dependencies: WP3 and WP4a-d.
- Files/interfaces: selected existing/adapted Tester case files and run outputs; direct journey outputs; coverage ledger.
- Work: execute the collection subpackets below sequentially, using new campaign scope and complete fresh workflows. Reuse only this campaign's outputs for cross-profile/direct inspection. Capture transient states during execution and stop dependent branches at real blockers without losing completed evidence.
- Acceptance: every required surface/profile/state is represented by this release's new runs or explicitly blocked with the last observed state and next action. All prerequisites have input or fresh-output provenance. Action results, UI evidence and generated image quality are separate outcomes.
- Validation: inspect workflow reports and source/candidate identities, capture completeness and diagnostic errors; open representative screenshots and selectively read bundles. Execution commands depend on the agreed environment and must be recorded exactly when run.
- Status: complete.

Each WP5 subpacket is a separate bounded execution task. It owns its selected case/journey output, report and coverage rows, inherits the release/uniqueness rules, and validates its workflow report, capture manifest, representative PNGs and diagnostics before moving on:

| Subpacket | Work and dependencies | Acceptance |
| --- | --- | --- |
| WP5a | Run one fresh Character case from wizard through requested three-view pipelines and costume; depends on WP3. | New accepted templates, candidate/review/publication evidence and unique output IDs; blockers recorded by branch. |
| WP5b | Run one fresh Minor Character case; depends on WP3 and verified original Inventory input. | Intake, private Style and requested official views captured with new results. |
| WP5c | Run one fresh Narrative case through assembly; depends on WP3 and declared source inputs, including WP5a/b outputs if selected as references. | New story, scene, targets, candidates and published assembly with source identity. |
| WP5d | Run one fresh Image Generation coverage case; depends on WP3 and original reference inputs. | New gallery assets, reference ordering, reconstruction and comparison/correction evidence. |
| WP5e | Execute character/library gap journeys; depends on WP5a and WP4b. | New output-backed keys/turnarounds/comparisons, Inventory and hub state captures. |
| WP5f | Execute Narrative production gap journeys; depends on WP5c and WP4c. | New assembly-backed crop/lettering, animation, Candidates and Zine evidence. |
| WP5g | Execute settings/shared-overlay journeys and finish cross-profile gaps; depends on WP4d and fresh outputs from relevant WP5 packets. | Required rows captured at desktop/tablet sizes or explicitly blocked; temporary settings restored. |

### WP6 - Verify and hand off the review package

- Dependencies: WP5a-g.
- Files/interfaces: evidence manifest/README/coverage and source map; `Zet_Tester/README.md`; [Dashboard UI](../../Docs/COMPONENTS/DASHBOARD_UI.md) capture section and [Testing](../../Docs/Testing.md) if their commands or boundaries change.
- Work: validate paths/schema/coordinates, release freshness and output provenance, totals and limits; publish a local review entry point and document selection/comparison, gaps and source ownership. Update Code Map only if significant entry points move; record a short ADR if the finalized cross-repository capture contract warrants a durable design record.
- Acceptance: a reviewer can start with one compact campaign manifest, select a workspace/state/profile, substantiate an observation and find the captured release's implementation without reading an entire run. No older generated result or mixed-release capture satisfies coverage. No review findings or UI fixes are required by this evidence-capture plan.
- Validation: changed module syntax and focused checks; run `npm.cmd run test:e2e` in Zet if Zet capture/fixture integration changed, preserving the 20-scenario baseline; run `git diff --check` and review diffs in both repositories. Do not run the separate live E2E spec unless requested.
- Status: complete.

## Risks and limits

- Tester's active-release checks and fast E2E's fixture server are different runtime contracts. Choose each journey's runtime explicitly; never weaken the release guard just to reuse fixture preparation.
- Exporting geometry is sampling a changing page. Record observation times and state mismatches; avoid presenting independently captured files as perfectly atomic.
- A source map can identify candidates for investigation but cannot always prove which CSS rule caused a layout. Preserve observed classes, ancestry and computed values alongside inferred ownership.
- Real pending/error states may be brief even during new runs. Capture them intentionally when possible; prepared responses remain supplementary and cannot substitute for new Test-release evidence. Do not fabricate captures or intentionally disrupt normal services.
- Fresh workflows require live model/render time and may expose functional blockers. Resume only new runs belonging to this release campaign; report blocked coverage rather than importing older successful results.
- Heavy capture can alter timing. Collect at named checkpoints, measure the pilot, bound work and preserve normal polling behavior. Retrying a capture must not retry the application action.
- Persisting case-specific text, images and prompts increases storage and may include private material. Keep bundles local and scoped to Test; review any later sharing separately.

## Review readiness

No unresolved scope questions remain. Desktop/tablet coverage and all-new runs are settled. The collector location, profiles, packet breakdown and bundle structure are proposed for whole-plan acceptance. The actual Test release, source availability and services will be checked before collection; these are execution preconditions rather than permission to reuse old results.

The plan is complete when its approach and packets are accepted. Implementation and evidence collection are complete only after the work and validation above have run, their results are recorded, and every required coverage row is captured or clearly blocked. A package with blocked rows is explicitly partial and must identify required follow-up.

## Decisions and planning progress

- Joe selected desktop and tablet coverage on 2026-11-24.
- Joe requires all new runs because earlier runs used different releases. This replaces the earlier proposal to reuse completed Test results first.
- Local repository planning convention selects this file as the canonical brief. Preserve one agent throughout research and implementation unless Joe later requests delegation.
- The user permits adapting/creating Tester cases for broader review coverage. This does not automatically expand Zet's maintained fast E2E baseline or authorize live model/render calls during planning.
- Current chat title observed as `Plan UI review evidence capture`; no title change was necessary.

### Implementation progress

- WP1: complete. Added a separate `tester.evidence.toml` preserving the malformed local config, confirmed Test library/release/boot identity, validated the selected new cases and inventoried canonical routes. Required surface profiles, inputs, fresh dependencies and downstream blockers are recorded in the campaign entry point.
- WP2a: complete. The collector writes viewport screenshots, browser/viewport metadata, ARIA structure, visible nodes, geometry, selected styles and bounded console/page/request diagnostics. Tester manifests carry release, boot, case and universe identity; the page sweep uses the same collector and refuses release/boot mismatches.
- WP2b: complete for this evidence scope. The bundles link node structure, geometry and styles by capture ID; a route-to-source candidate map and campaign source links support code lookup. Spot checks matched an 810x1080 PNG to the recorded tablet viewport and identified a clipped 83px character selector containing 94px of content. No crop transforms or region captures were needed; inner-scroll dimensions are retained in geometry metadata.
- WP3: implemented for current collection. Added `--evidence`, named capture, three viewport profiles, and bounded action records. The helper now accepts `--in <field label>` as well as article scopes, retaining an exact-one-visible-control guard; this was needed to set two Narrative model controls with duplicate displayed values. Verified with syntax and a live same-release resume: both model overrides persisted after save/reload.
- WP4a: complete. The structural sweep captured 63 page bundles against the pinned Test release. Direct navigation reached seven visible Character Development destinations at all three profiles. Internal activation failed for Compare, but visible navigation reached it. Evidence is under `Zet_Tester/runs/ui-review-2026-11-24/direct-page-sweep/` and `direct-nav-journeys/`. The route sweep is structural evidence; it does not establish workflow-output freshness.
- WP4b-d: complete for bounded review collection. Direct checks used fresh Character and Narrative outputs for Identity Keys, Turnarounds, Inventory, Compare, assembly review, text placement and animation. Settings/style overlays and all canonical routes were captured at desktop/tablet profiles. Rename/archive/delete preview interactions and physical-device behavior were not exercised; these are outside the captured review claims and are listed as limits.
- WP5a: complete on Test revision `d6143b9f4c7550e8b3ec3dd56cc86c3ebb5b60d1` / boot `193acab8a9a4468380ccbe3548b809e7`. Fresh Character `UI Review Luna 20261124` completed the Character Wizard, Body Reference, Head Image Edit, Assembly, Costume Wizard and Costume Dressing flows, with new ranked candidates and locks. Costume acceptance records two remaining visual differences. Full report: `Zet_Tester/runs/ui-review-2026-11-24/2026-11-24T22-26-16-196Z-3d860f4f/resume-2026-11-24T22-55-50-296Z-07ef981b/report.md`.
- WP5b: complete on the same release and boot. Fresh Minor Character `UI Review Minor 20261125` used the existing original Ang_full Inventory source (ID `d7a0ab63-88b3-4b27-b837-bab5ea3918dc`), completed Intake and Style with one focused refinement, then published new Front, Front Left 3/4 and Front Right 3/4 outputs. Tablet image cards remained visible; the character selector truncates at tablet widths. Full report: `Zet_Tester/runs/ui-review-2026-11-24/2026-11-25T00-55-58-771Z-e10062cb/report.md`.
- WP5c: complete on the same Test revision and boot. Fresh story `UI Review Tea Visit 20261125` uses the newly published WP5a Costume Dressing FRONT item and WP5b Minor Character FRONT item, with exact Inventory title/tag/status/provenance checks. The run created and authored the scene, rendered and ranked new conservatory backdrop and transparent tea subscene assets, and locked all three #1 outputs through final assembly. Model controls were explicitly set to and reloaded as `codex:gpt-6-luna`. Final stable states were captured at desktop and tablet landscape/portrait; tablet portrait composition was observed as cramped. Full report: `Zet_Tester/runs/ui-review-2026-11-24/2026-11-25T02-09-38-251Z-217738d2/resume-2026-11-25T02-20-40-427Z-fd91bfc6/report.md`.
- WP5d: complete on the same Test revision and boot. Fresh `UI Review Image Generation 20261125` exercised text-to-image, image-to-image with ordered original references, canonical and environmental style insertion, two-step Reconstruction, comparison and correction. The comparison baseline omitted the gown; the correction restored it, with the new corrected candidate selected. No candidate entered Inventory. Full report: `Zet_Tester/runs/ui-review-2026-11-24/2026-11-25T03-02-22-304Z-cae1334f/report.md`.
- WP5e: complete on the pinned revision and boot. Created and published a fresh Identity Key from the WP5a Costume Dressing FRONT output; verified its approved Inventory item, stable `LIB:REF` tag, identity-key prompt key and entity link. Captured Turnarounds and Compare with fresh Character data across desktop/tablet landscape/tablet portrait. Turnarounds reports 3/8 locked views and disables Generate/Promote for each task. Compare is reachable through visible navigation, but shows the same character, phase and pipeline on both sides by default. Direct captures: `Zet_Tester/runs/ui-review-2026-11-24/direct-character-library-journeys/browser-session/evidence/manifest.json`.
- WP5f: complete with explicit downstream blockers. Inspected the fresh locked Narrative assembly, review and text editor at desktop and both tablet profiles; animation accepts a fresh one-shot and its saved shot remains visible after navigation. The text editor accepts text, but its save action reports `Unlock the current image before selecting another candidate` while the fresh selected final remains locked; unsaved text was discarded. Candidates stayed on `Loading candidates...` with an empty Source selector. A fresh Zine form filled its front from the new story, but Page 1 had no available option and Create Zine reported `Page 1 is required`; the unsaved form was discarded. Capture bundles are in the WP5e browser-session manifest; the campaign entry point indexes the relevant states.
- WP5g: complete for the planned desktop and tablet evidence scope. Captured Universe Settings and the Scene Text Style dialog at desktop, tablet landscape and tablet portrait. No settings were changed. Fresh Identity Key detail, Compare, Turnarounds, Narrative assembly/text, animation, Candidates and Zine states were captured at the same profiles or recorded as blocked. The comparison selector fields and Inventory tag show truncation/inner horizontal scrolling at tablet portrait; no document-level horizontal overflow was seen in the page sweep. Tablet sizes are browser viewport emulation, not physical iPad validation.
- WP6: complete. Added a campaign review entry point and indexed fresh workflow reports, direct journey captures and unresolved gaps. All 55 direct-session state hashes and bundle artifacts verified, all direct states share the pinned revision/boot, the Test health endpoint still matches, and the page sweep contains 63 complete bundles. Four selected case validations, changed-module syntax checks and both repository `git diff --check` commands pass. See [review entry](../../Zet_Tester/runs/ui-review-2026-11-24/REVIEW.md).

### WP5 evidence outcomes

- Fresh production packets WP5a-d remain complete as recorded above. All new workflow outputs belong to revision `d6143b9f4c7550e8b3ec3dd56cc86c3ebb5b60d1`, boot `193acab8a9a4468380ccbe3548b809e7`, universe `ZetTester`.
- Direct browser session contains 55 complete evidence bundles. The generated run manifest records each capture's route, viewport, UI structure, geometry, styles, screenshot, release identity and SHA-256 state hash. A few exploratory checkpoints have labels that predate a failed navigation; use the actual URL and route in each bundle as the authority.
- The release-pinned page sweep produced 63 complete bundles for 22 canonical destinations across desktop, tablet landscape and tablet portrait. Three Compare entries failed only through internal route activation. Visible-control navigation reached Compare and produced an additional fresh-data capture at all three sizes.
- The campaign entry point is `Zet_Tester/runs/ui-review-2026-11-24/REVIEW.md`. It separates fresh workflow outputs from prior library context and identifies direct-browser evidence by state key.

## Runtime recovery follow-up (2026-11-24)

Scope: restore Tester's standalone Codex process launch so collection can resume. This follow-up does not execute the Character workflow or change the pinned Test release, global Codex settings, or sandbox permissions.

- Runtime WP1 - isolate the standalone launcher environment. Files: `Zet_Tester/run.mjs`, `Zet_Tester/README.md`. Remove inherited desktop registered-Core/package markers only from the child environment; retain Codex's configured sandbox. Make the Node executable running Tester available to its child commands. Acceptance: a sandboxed Codex child can start a PowerShell command and invoke the browser helper. Validation: module syntax, existing case validation, and a disposable runtime/browser handshake. Status: complete.
- Runtime WP2 - verify recovery and record the resume boundary. Depends on Runtime WP1. Files: disposable diagnostic artifacts and this plan. Verify the pinned release/boot, open and snapshot the Test dashboard through the helper, and retain a diagnostic capture without workflow actions. Record the exact resume command. Acceptance: the process launch blocker is cleared with observed evidence; workflow collection remains pending. Status: complete.

Diagnosis: the dashboard health matches revision `d6143b9f4c7550e8b3ec3dd56cc86c3ebb5b60d1` and boot `193acab8a9a4468380ccbe3548b809e7`. Tester resolves npm Codex CLI 0.157.0; the desktop bundles 0.171.0-alpha.13.2. Both failed a standalone process probe with the inherited desktop registration environment. The npm CLI successfully ran `Write-Output ZET_RUNTIME_PROBE_OK` with a read-only sandbox after removing `CODEX_WINDOWS_REGISTERED_CORE` and `CODEX_WINDOWS_SANDBOX_PACKAGE_FAMILY` from that child only. The parent command environment also lacks `node` on PATH.

Observed recovery: the actual modified runner launched a disposable diagnostic wrapper, which invoked the same npm CLI with the production model/reasoning arguments and replaced the workflow prompt with four read-only dashboard/runtime commands. `node --version`, browser `open`, `snapshot`, and `capture runtime-recovery` all exited 0. The persisted Codex turn context confirms `workspace-write` and `on-request` remained effective. One diagnostic capture completed and its manifest SHA-256 was verified. This captured the dashboard shell, not a completed workflow or Character Overview coverage state. Result: `Zet_Tester/runs/ui-review-2026-11-24/runtime-recovery-check/attempts/2026-11-24T22-47-34-611Z-ed5a0ce7/runtime-result.json`. The outer runner intentionally exited 1 because the diagnostic wrapper recorded the Character workflow as unexecuted/blocked; this is not a runtime failure. Exclude the diagnostic attempt from workflow coverage and do not resume it. The configured desktop computer-use fallback was not retested; Tester can continue through its browser helper.

`node --check run.mjs`, the prepared Character case's `--validate`, and `git diff --check` in both repositories passed. No permanent tests were added and no Zet application code changed. The pinned revision/boot was rechecked after the diagnostic. No Character workflow, authoring/render job, lock, reset, or publication was executed during recovery.

Resume the original campaign attempt from a Codex desktop PowerShell environment with the existing evidence config (the runner must reconcile current dashboard work first):

```powershell
& $env:CODEX_MCP_NODE_PATH 'C:/Users/Joe/Projects/Zet_Tester/run.mjs' --resume 'C:/Users/Joe/Projects/Zet_Tester/runs/ui-review-2026-11-24/2026-11-24T22-26-16-196Z-3d860f4f' --config 'C:/Users/Joe/Projects/Zet_Tester/tester.evidence.toml' --evidence
```

## Validation observed

Collection and handoff are complete for the bounded desktop/tablet scope. The Test `/api/health` endpoint matched revision `d6143b9f4c7550e8b3ec3dd56cc86c3ebb5b60d1` and boot `193acab8a9a4468380ccbe3548b809e7` at final verification. The direct browser manifest contains 55 complete bundles; every state hash and required artifact is present, and every state records the same release and boot. The page sweep contains 63 complete bundles; all 63 page captures are recorded, with three internal Compare activations documented as unavailable and the visible route covered separately. The four selected fresh cases passed `--validate`; module syntax and `git diff --check` passed in both repositories. No maintained Zet E2E suite or physical device check was run. Narrative text saving, Candidates and Zine Page 1 remain explicit UI blockers. `tester.toml` local changes were preserved. No Zet application code was changed during evidence collection.
