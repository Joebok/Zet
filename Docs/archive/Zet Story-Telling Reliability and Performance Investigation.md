# Zet Story-Telling Reliability and Performance Investigation

## Summary

Perform a live, reversible walkthrough of every Story Telling page and every Tools page, stage all eight scenes in **First Day** for manual ChatGPT rendering, exercise AI jobs in controlled orders, profile the affected backend paths, and produce prioritized fixes across Zet, AI_Proxy, and ModelUpdater.

Known findings to carry into the investigation:

- Scene Builder navigation uses `state.scenes`, while direct entry can populate only the workspace-summary scene list. This explains disabled arrows unless Scenes was visited first.
- Project-wide Image Review currently takes about 24–33 seconds. Profiling found 36 million calls, 126 complete Image Inventory discoveries, 4,833 Scene Builder loads, and roughly 80,000 file reads while finding zero pending scene reviews.
- Production summary repeats scoped and project-wide scans and refreshes every 45 seconds without cancelling the backend work, allowing expensive scans to overlap normal navigation.
- Image Inventory stores override text, but its API returns only the effective inherited text. Switching modes can therefore hide and later overwrite the saved override.
- The legacy `general-purpose` and `structured-reasoning` references have been replaced by `general`, and Scene Builder now uses `general:latest`. Treat alias migration as resolved, but verify the effective runtime model during preflight.
- `image-analysis:latest` has been corrected to use the GPU. Treat CPU-only inference as resolved, but continue measuring CPU, RAM, GPU/VRAM, model residency, and UI latency during vision jobs to catch model-switching or context-allocation pressure.
- Zet’s Config page currently contains controls for all nine `[AIModels]` keys: Asset Workflow, Prompt Condense, Prompt Analysis, Image Description, Scene Builder, Prompt Evolution critic A, critic B, analysis/editor, and regression check. The investigation must verify that each control loads and saves the correct key and identify any implicit, fallback, repair, or task-specific model assignments that are not exposed there.
- The remaining model assignments have not received a task-specific review. In particular, Prompt Condense and Prompt Analysis are text-only jobs currently assigned to `image-analysis`, while both Prompt Evolution critics currently use `image-analysis-alt`; suitability and critic independence must be evaluated rather than assumed.
- Required tooling is available: Zet’s Python environment, pytest, Playwright 1.62, Chrome control, Ollama, and NVIDIA telemetry. No plugin or package installation is needed. ModelUpdater’s service must be started from its existing launcher before its live state can be reconciled.

## Live Walkthrough and Diagnostics

1. **Preserve the starting state**
   - Record Git status for Zet, Zet_Library, AI_Proxy, and ModelUpdater; do not reset the existing `config.toml` change or Zet_Library’s unpushed commit.
   - Record every existing Ask, Running, Answer, Manual Render, Harvested, and Superseded task so newly created work can be identified and reversed.
   - Verify Zet, AI_Proxy, auto-harvest, Ollama, ModelUpdater, and optionally ComfyUI through their existing launchers and health endpoints.
   - Capture idle CPU, RAM, GPU/VRAM, loaded Ollama models, browser console errors, and baseline response times for context, workspace summary, production summary, Image Review, Image Inventory, stories, and scenes.

2. **Walk every Story Telling surface without AI load**
   - Visit Overview, Scenes, Candidates, Scene Builder, Zines, Prompt/Analysis, Render Console, Local Variants, Image Review, and each scene-workflow destination.
   - Test Scene Builder first by direct entry after a reload, then from Overview and Scenes. Verify arrows, header selectors, browser navigation, unsaved-change guards, selected story/scene retention, and returns from Prompt/Analysis and Render Console.
   - On Image Review, compare the project-wide badge with the table after loading. Record loading duration, blank-table periods, errors, and whether all three existing asset reviews eventually appear.
   - Measure warm and cold page transitions and identify requests that continue after navigating elsewhere.

3. **Stage all eight First Day scenes**
   - Follow the saved scene order from Chapter 01 through Chapter 08.
   - For each scene: open Scene Builder, inspect readiness/references/sub-scenes, open Prompt/Analysis, stage the full scene, verify the corresponding Render Console task, return to Scene Builder, and advance using the arrows.
   - Do not submit any ChatGPT image generation, local rendering, promotion, discard, or approval action.
   - Leave all successfully staged scenes in Render Console. Record scenes blocked by validation or stale sub-scene dependencies without modifying their authored content merely to force staging.
   - Confirm task uniqueness, correct story/scene association, prompt/reference availability, and that staging one scene does not remove another scene’s task. Record any pre-existing task moved to Superseded.

4. **Exercise Tools pages**
   - **Image Inventory:** test search/filter refresh, item selection, reference-set loading, and one reversible imported-item metadata cycle. Snapshot the item first; verify identity and costume override text survives `override → inherit/not applicable → navigation/reload → override`; restore the original metadata afterward.
   - Queue one **Draft with AI**, follow it through AI Queue and harvesting, and verify its status and returned text survive filtering, page transitions, and reloads. Remove only the test draft after capturing the result.
   - **Template Editor:** load and switch templates without saving.
   - **AI Queue:** verify Ask/Running/Answer transitions, failure text, recent harvests, and status refresh under navigation.
   - **Config:** inspect service status and every model control; compare the displayed value with `config.toml`, the configuration API payload, the value saved back by the form, the manifest produced for a real job, and the effective Ollama alias. Inventory any model-bearing code path that lacks a corresponding control or is intentionally derived from another role. Defer assignment changes until the current behavior is recorded.
   - **Single Character Lab** and **Prompt Evolution:** verify loading, existing-run inspection, validation, and navigation only; do not start a new character-oriented production run during this Story Telling investigation.
   - **Pipeline Inspection** and **Pipeline Controls:** inspect current data and action availability without advancing, resetting, recovering, or deleting pipeline state.
   - Open Help/template manuals to confirm the references needed for interpreting prompts and templates remain available.

5. **AI-load ordering matrix**
   - Run each case from a stable idle baseline while monitoring CPU, RAM, GPU, loaded models, queue timestamps, endpoint latency, and UI responsiveness:
     - Image Inventory description alone, navigating through Image Review, Prompt/Analysis, and Render Console while it runs.
     - Scene prompt analysis followed by an image description.
     - Image description followed by scene prompt analysis.
     - Two same-model image-description jobs consecutively to test resource affinity and keep-alive reuse.
     - One Scene Builder interview using `general:latest`, verifying successful structured output and responsiveness while the GPU-backed model is resident.
     - General-model work followed by vision-model work and the reverse, verifying AI_Proxy unload/switch behavior.
   - Do not run jobs concurrently until their individual effects are known; finish with one controlled overlap only if sequential runs are stable.
   - Correlate every freeze or disappearing result with browser requests, Zet scans, queue transitions, Ollama load/unload, and host-resource pressure.

## Remediation and Interface Changes

- **Scene navigation:** hydrate the canonical scene collection whenever Story Telling context loads, or make Scene Builder navigation consume the already-populated summary collection. Direct entry and return paths must behave identically.
- **Image Review and production summaries:** check cheap candidate-path existence before compiling freshness; never compile scenes without candidates. Reuse one request-scoped story/catalog index, avoid duplicate scoped/project scans, cache project counts briefly, and prevent overlapping background refreshes.
- **Image Inventory:** add raw `identity_override_text` and `costume_override_text` fields to catalog payloads alongside effective text. When a section is inherited or not applicable, disable editing but retain its raw override; mode-only saves must not replace it. Keep existing inventory JSON compatible—no destructive migration is required.
- **Async UI safety:** add request cancellation or generation guards to page-specific loaders so late Image Review, Inventory, summary, and AI-harvest responses cannot overwrite a newer selection. Preserve explicit loading/error states instead of showing an empty table.
- **AI_Proxy:** verify model-resource grouping, unload before cross-model transitions, same-model keep-alive reuse, timeout/failure reporting, and that the 31,538-file archive is never scanned on the hot polling/status path. Add retention/indexing recommendations only if measurements implicate it.
- **Model assignment exposure and configuration:**
  - Treat `general:latest` migration and GPU-backed `image-analysis:latest` as the corrected baseline, then confirm the checked-in Modelfiles, live Ollama aliases, ModelUpdater active revisions, Zet config values, and generated job manifests agree.
  - Build a complete role-to-call-site map covering the nine configured roles plus fallback generation, structured-response repair, directed refinement, and any direct Ollama calls. Every independently selectable production role must be exposed on Config; intentionally shared roles must be labeled with the jobs they govern.
  - Evaluate Asset Workflow, Prompt Condense, Prompt Analysis, Image Description, Scene Builder, both critics, regression check, and Prompt Evolution analysis/editor against representative Zet inputs before recommending reassignment. Do not change a role solely because its present alias name appears broader than the task.
  - Require critic A and critic B to resolve to independently validated model families. The current assignment of both critics to `image-analysis-alt` must be corrected if confirmed at runtime.
  - Assess whether Prompt Evolution’s mixed analysis/editor role should remain shared or be split: its reference bootstrap, diagnosis, and directed refinement need vision, while synthesis, minimal editing, and JSON repair are text-only.
- **ModelUpdater criteria review:** add Zet-specific structured Scene Builder, prompt-analysis, image-description, multi-image comparison, exact-ID/schema, and malformed-response-repair fixtures. Measure actual prompt sizes and resource use before changing context limits or gates; then recommend the smallest context with safe headroom, interactive latency/throughput thresholds, RAM/VRAM headroom, residency policy, and candidate ranking for each alias. Full-GPU execution remains the expected baseline for interactive aliases, with any CPU spill explicitly justified by measured quality benefit.

## Tests and Acceptance Criteria

- Add browser regressions for direct-entry Scene Builder arrows, all eight scene transitions, Builder ↔ Prompt/Analysis ↔ Render Console context retention, badge/table consistency, stale-response rejection, AI-draft persistence, identity/costume override preservation, and Config-page load/save coverage for every model role.
- Add service tests proving pending-review discovery does not compile scenes without candidates, catalog discovery is reused within a request, project summaries do not duplicate scans, and legacy catalog records remain readable.
- Add AI_Proxy tests for same-model reuse, cross-model unload, failure propagation, and hot-path independence from archives.
- Add ModelUpdater fixtures and gate tests covering GPU residency, CPU spill, insufficient RAM, excessive TTFT, schema failure, wrong multimodal behavior, critic-family independence, and each remaining Zet model assignment.
- Re-run focused unit tests, full Zet unit tests, the desktop Playwright suite, AI_Proxy tests, and ModelUpdater tests.
- Acceptance targets on the current library: ordinary warm navigation under 2 seconds, Image Review task listing under 3 seconds, no blank review table after its loading state ends, no overlapping production-summary scans, exact preservation of hidden override text, responsive navigation during AI work, and eight First Day tasks waiting in Render Console with no image-generation submission.

## Execution Results — 2026-09-09

### Outcome

The live walkthrough reproduced the reported failures and left all eight **First Day** scenes staged in the manual Render Console. No ChatGPT image generation, local render, candidate promotion, candidate discard, pipeline transition, or destructive cleanup was performed.

The investigation did make two intended, reversible catalog changes:

- The `Spire - Archway - Arch Back View` AI draft was corrected using the already-approved canonical description from the sibling `Spire Archway` record and approved. This was required to stage Chapters 06 and 07 without accepting the model's incorrect transcription of the arch inscription.
- A second AI draft was generated for `Spire - Archway - Arch Closeup` to test the `general → image-analysis` model transition. It remains in `ai_review_required` for later human review.

One orphaned, complete staging directory remains because the Dropbox-backed atomic rename failed during a duplicate Chapter 03 attempt:

`C:\Users\Joe\Dropbox\AI_Queue\Manual_Render_Queue\Ask\.Ask_Story_FirstDay_Chapter-03-Collision_RENDER_20260909_193100_412784_42e8b37ded604c0fbe81dfb3e75c8fd0.staging`

It was deliberately not deleted. The valid Chapter 03 task is already present in Render Console.

### Validation and baseline

- Zet `/api/context`, AI Proxy `/api/tags`, Ollama `/api/tags`, and ModelUpdater `/api/overview` responded successfully. ComfyUI on port 8188 was offline, which did not affect manual staging.
- Focused service tests passed: `25 passed in 4.43s` for `test_image_catalog_service.py`, `test_scene_image_review_service.py`, and `test_web_app.py`.
- The focused browser test for queued Image Inventory descriptions passed: `1 passed in 3.8s`.
- Initial GPU state was idle with 0 MiB reported as used by compute processes. The `image-analysis:latest` jobs loaded entirely into VRAM at approximately 7.8 GB; the Scene Builder `general:latest` interview loaded approximately 8.9 GB into VRAM.
- The eight scene tasks were verified through `/api/render-console/tasks?story_slug=FirstDay`; each chapter appears exactly once.

### First Day scene staging

| Scene | Result | Material observation |
| --- | --- | --- |
| Chapter 01 — Standing in Wonder | Already staged; verified | Existing task and prompt were readable in Prompt/Analysis and Render Console. |
| Chapter 02 — At the Arch | Staged | Header selection initially left Chapter 01 form data visible. Correct loading required returning through Scenes. A stale locked background required the explicit `Use locked image anyway` action. |
| Chapter 03 — Collision | Staged | Scenes-page `Builder` action did nothing; Workflow → Builder worked. Dropbox blocked two atomic staging renames with `WinError 32`; one complete bundle was promoted after the handle released. |
| Chapter 04 — A Lending Hand | Staged | Normal successful staging path. |
| Chapter 05 | Staged | Dropbox returned `WinError 32`; the complete bundle was promoted after the handle released. |
| Chapter 06 | Staged | Initially blocked because `Arch Back View` lacked identity text. Staged normally after corrected AI metadata approval. |
| Chapter 07 — Nice Hair | Staged | Builder load took more than 40 seconds. Initially blocked by the same missing identity text. Final staging hit `WinError 5`; the complete bundle was promoted after the handle released. |
| Chapter 08 — Nightmare Version | Staged | Builder load took approximately 40 seconds. Staging hit `WinError 32`; the complete bundle was promoted after the handle released. |

The manual queue now contains these eight First Day tasks and six unrelated pre-existing tasks. Render Console correctly filters the orphaned dot-prefixed staging folder.

### Reproduced reliability and performance defects

1. **Scene Builder direct-entry navigation is broken.** Direct entry showed both scene arrows disabled even though the header contained all eight scenes. Visiting Scenes first enabled the arrows. This confirms the split `state.scenes` versus workspace-summary state identified during planning.

2. **Scene selection can present contradictory state.** Selecting `At the Arch` updated the header and `FirstDay / Chapter-02-At-the-Arch` status while the editable form still contained Chapter 01. Clicking Render in that state attempted to stage against stale client data and remained on `Staging full-scene render...` until reload.

3. **Long loaders serialize navigation.** Image Review remained at `Loading render reviews...` for roughly 60–105 seconds in repeated runs. During the pending request, Overview, Candidates, and Zines clicks did not activate; the last queued click took effect only after the review request completed. Scene Candidates similarly remained at `Loading candidates...` for more than two minutes, discarded workflow selections, and trapped both Config navigation and the in-app Restart request behind the loader.

4. **The underlying hot paths are scale-sensitive.** Measured HTTP timings on the current library were:

   - Filtered Image Inventory (`q=arch`, excluding base images): **0.21 s** for 7 results.
   - Scene candidate source discovery: **0.01 s**; Moonsea candidate listing: **0.05 s** for 9 candidates.
   - First Day-only Image Review task listing: **5.46 s** for zero story review tasks after restart/warmup; earlier cold measurements were approximately 14.8 seconds, and the unfiltered service call was approximately 23.8–32.6 seconds.
   - First Day production-work summary: **54.46 s**.

   Profiling the unfiltered review service produced 36,167,441 calls, 126 full Image Inventory discoveries, 4,833 Scene Builder loads, about 80,000 file reads, 45 status calls, and 42 render compiles while finding no pending scene reviews. Candidate/source APIs themselves are fast, so the multi-minute Candidates UI lock is client orchestration or unrelated overlapping summary/review work rather than parsing nine candidate records.

5. **Manual queue publication races Dropbox.** Four scene attempts failed only at the final staging-directory rename with `WinError 32` or `WinError 5`. The eight expected bundle files were already complete. Retrying the same rename after a short delay succeeded. Zet currently lacks the retry/backoff behavior already used by AI_Proxy queue transitions, surfaces the raw filesystem exception, and leaves orphaned staging directories.

6. **Identity override text is lost from the UI after a saved mode change.** A controlled test used the approved 534-character `Spire Archway` override. Switching to Inherit retained the text before save; after Save Metadata/reload, the textbox was blank, and switching back to Override did not recover it. The exact original override and `ai_reviewed` provenance were restored through the API and verified. This confirms that materializing only effective text makes the retained raw override inaccessible and vulnerable to a later blank save.

7. **AI draft persistence works, but status messaging can be stale.** The first arch draft survived page changes, restart, and API reload as `ai_review_required`. After approval, the backend correctly reported `approved` with an empty AI draft, while the page still displayed the old `AI answer harvested. Review and approve...` status alongside `AI draft approved.`

8. **AI Harvest scans far too much for an empty active queue.** With Running and Answer both empty, toolbar AI Harvest remained `Working...` for approximately 100 seconds before reporting `No AI answer folders found.` The archive baseline contained roughly 31,524 files in 4,603 directories, strongly implicating full archive/history discovery on the hot action path.

9. **Some menu actions appear inert.** The Tools `To Do` action and Help `Template Instruction Manuals` item closed their menus but did not change the active page or present feedback. Local Variants and Locked Image selections were reset while Scene Candidates was still loading. These require isolated regression tests after long-request cancellation is fixed.

### AI and model results

- `image-analysis:latest` successfully completed two Image Inventory description jobs and one scene prompt-analysis job on the GPU. The Chapter 1 prompt-analysis output harvested to `AI_Prompt_Analysis.md` with a matching prompt hash and no stale flag.
- The first image description incorrectly read the arch inscription as `INSURANCE IS NOTHING WITHOUT TRUST` and invented a second slogan. The second close-up draft was more accurate but added several robed figures. The vision alias is operational and responsive enough, but exact visible-text transcription and unsupported-detail penalties need to be part of its evaluation fixtures.
- A non-saving Scene Builder interview limited to the story phase completed in **24.03 s** using `general:latest`. It returned valid structured data but asked about lighting and architectural style during a story-beat-only phase, despite those concerns belonging to later phases. Add phase-boundary and question-relevance scoring to the Scene Builder fixture.
- The model order `image-analysis → general → image-analysis` worked. Ollama evicted the previous model at each transition because both models cannot remain comfortably resident together on the 16 GB GPU. No controlled concurrent run was attempted because sequential browser navigation was already unstable.
- The running Config page initially showed stale `general-purpose:latest` until Zet restarted. After restart, all nine controls matched `config.toml`; no independently selectable configured role was missing from the page.
- Zet's direct `OllamaModelService.generate_json()` overrides managed Modelfile settings with hardcoded `num_ctx: 8192` and `num_predict: 4096`. The live `general:latest` interview therefore ran at an 8,192-token context even though ModelUpdater configured 65,536/2,048. File-proxy vision jobs used the managed 65,536-token context. This split makes ModelUpdater's selected configuration non-authoritative and complicates resource predictions.

### ModelUpdater assessment

The current aliases are materially better than the retired configuration:

- `general` → `qwen3.5:9b-q8_0` and `general-alt` → `lfm2.5:8b` are distinct families and both fit in GPU memory.
- `image-analysis` → `gemma4:12b` and `image-analysis-alt` → `qwen3-vl:8b-instruct-q8_0` are distinct families and GPU-backed.
- `code` → `gpt-oss:20b` and `code-alt` → `granite4.2:8b` are distinct. The current estimates put `code` at 15,239 MiB, leaving little practical VRAM headroom.
- `code-epic` and `code-epic-alt` are predicted at 20,788 MiB and 17,141 MiB respectively, so both intentionally spill despite a nominal `prefer_full_gpu` baseline elsewhere.

The remaining selection policy is too aggressive for an interactive desktop shared with Zet:

- Every alias permits `minimum_free_ram_gib: 0.5`, CPU spill, a 32 GiB weight, and up to a 65,536-token context. A 0.5 GiB reserve is insufficient to prevent paging or desktop stalls when a 17–21 GiB estimate spills into system RAM.
- All `*-alt` aliases currently declare `diversity.minimum: none`. They happen to be different families today, but ModelUpdater is allowed to select the same family later. Require at least upstream-family diversity for `general-alt`, `code-alt`, `code-epic-alt`, and `image-analysis-alt`.
- Both Prompt Evolution critics are assigned to `image-analysis-alt`, defeating independent criticism even though the primary and alternate vision aliases are now diverse. Assign critic A to `image-analysis` and critic B to `image-analysis-alt`, subject to paired critic fixtures.
- Keep `general` and `image-analysis` as the current interactive choices while adding task-specific quality gates. Raise interactive free-RAM headroom to at least 4 GiB, disallow CPU spill for interactive aliases unless a measured exception wins by a meaningful quality margin, and evaluate 16K/32K contexts before defaulting every task to 65K. Keep spill-tolerant, long-running candidates confined to the `*-epic` roles.
- Split or explicitly label Prompt Evolution's text-only synthesis/repair work versus vision-required comparison work before changing aliases. Prompt Condense and Prompt Analysis should move away from a vision alias only after representative prompt fixtures show that a text alias preserves quality and schema adherence.

### Prioritized remediation

1. **P0 — Make page loads cancellable and navigation independent of pending loaders.** Attach navigation handlers before awaited startup loads, abort obsolete fetches, and prevent production-summary refreshes from joining the active page-transition chain.
2. **P0 — Remove repeated catalog/scene compilation from review and summary scans.** Test candidate existence first, build one request-scoped index, cache project-wide counts, and never compute both scoped and project totals by repeating the same discovery.
3. **P0 — Add retry/backoff and cleanup semantics to manual queue publication.** Reuse AI_Proxy's replace-with-retry approach, distinguish transient sharing violations, and expose a safe recovery action for complete `.staging` bundles.
4. **P1 — Preserve raw metadata overrides separately from effective inherited text.** Return raw and effective fields, disable inherited textboxes without clearing them, and make mode-only saves leave approved override text untouched.
5. **P1 — Unify Scene Builder selection state and navigation.** Hydrate one canonical scene list, wait for the selected scene document before enabling render, and make Scenes-page Builder and header Workflow routes share the same implementation.
6. **P1 — Make managed model runtime settings authoritative.** Remove Zet's hardcoded direct-Ollama context/prediction overrides or expose per-role runtime options with clear precedence on Config.
7. **P1 — Index AI harvest history.** When Answer is empty, return immediately; do not traverse the multi-thousand-directory archive to prove there is nothing to harvest.
8. **P2 — Tighten ModelUpdater safety and diversity gates.** Increase host headroom, constrain spill to epic profiles, enforce alternate-family diversity, and add the observed Zet phase-boundary and OCR/hallucination fixtures.
