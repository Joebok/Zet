# Prompt Generator Dashboard Pilot
Status: superseded by [Guided Prompt Generator Pilot](../completed/guided-prompt-generator.md). Historical implementation/validation below describes the original pilot, not the current workflow or authorization policy.
Related specification: [Prompt Generator Pilot Overview](../../Docs-Joe/Prompt_Generator_Pilot_Overview.md)

## Goal

Provide an opt-in local-character dashboard workflow where Zet prepares immutable facts and ordered reference images, an LLM drafts the final render prose, and Joe reviews prompts, renders, and durable changes separately. Pilot one Tsaeytte Costume-Dressing rear-quarter view, one additional costume view, and one Head-Image Edit view. Each case allows four baseline renders, up to three four-seed trials (16 render submissions maximum), and 12 LLM calls; totals are 48 renders and 36 LLM calls. Local-model calibration remains a follow-up.

## Current behavior

- Local prompt compilation and frozen render requests belong to `CharacterRenderSlots.prepare_input` in `zet/services/render_slot_service.py`; existing prompt templates and dependency manifests establish ordered image roles.
- `LocalPostRenderPromptService` privately trials selected Character.md changes; `LocalCharacterRefinementService` refines a selected image. Neither provides a generated, editable render-prompt session.
- AI requests use `AIWorkflowService`/`FileProxyClient`, frozen Qwen guidance uses `llm_skill_service.py`, model discovery uses `AIModelCatalogService`, and Codex rate-limit checks use `CodexUsageService`.
- Character runs and universe-owned records use versioned JSON with `LibraryReferenceService` path handling. Selected/locked publication uses `LocalCharacterAssetPipelineService`, `LocalAssetStoreService`, and receipt-backed `EntityLibraryService` catalog publication.
- Approved checks are S1-S4 in `tests/e2e/fast.spec.mjs`; S2 protects a narrow front-only Assembly/Dressing chain. Disposable tests are permitted; permanent coverage additions require separate approval.

## Desired behavior

1. Templates can declare explicit generator-analysis and render references using inventory tags, selected/locked same-batch views, or named locked pipeline views. Resolve declarations at packet preparation, fail visibly if absent/ambiguous, snapshot mutable bytes once, and never re-resolve an existing packet after unlock or selection changes.
2. A versioned packet binds compiled facts, criteria, source identities/hashes, generator and render image lists, settings, guidance and target pipeline/view. Generator drafts are structured, editable, reference-validated, and approved against an exact packet and text revision.
3. A private, reloadable session supports a four-seed baseline and up to three four-seed trial rounds, image-edit trials, retries, image acceptance, explicit batch adoption, and separately reviewed durable source changes. Attempts preserve their exact manifests and do not silently consume selection/lock state.
4. Local via AI_Proxy is available when capability-valid, Codex Luna is default, and higher Codex escalation is explicit. A 10% configured Codex reserve gates submission; unknown/low usage pauses while preserving work. Per-case usage caps at 12 LLM calls/16 render submissions; pilot totals cap at 36/48.
5. Publication retains the accepted prompt and compact ordered input manifest transactionally with the authoritative catalog lock. Pilot images use captured provenance without ongoing guide-integrity requirements; ordinary pipeline behavior remains intact.

## Impact and invariants

Likely owners: `zet/models/`, new focused prompt-packet/session/policy services under `zet/services/`, `zet/services/llm_role_service.py`, `zet/services/llm_skill_service.py`, `zet/services/render_slot_service.py`, `zet/services/local_character_asset_pipeline_service.py`, `zet/services/local_asset_store_service.py`, `zet/services/entity_library_service.py`, local pipeline workflow/router, dedicated template/static page, and selected task templates/guidance.

Update the relevant owners among `Docs/COMPONENTS/PROMPTS.md`, `LOCAL_CHARACTERS.md`, `LLM_ROLES.md`, `AI_JOBS.md`, `Docs/DATA_MODEL.md`, `Docs/INVARIANTS.md`, `Docs/CODE_MAP.md`, `Docs/Testing.md`, and one ADR. Preserve universe isolation, queue ownership/attempt fencing, ordered image bindings, serializer versions, frozen retry inputs, explicit image selection/publication, entity catalog authority, and existing AI_Proxy-only local inference. Do not add dependencies, permanent scenarios, live inference, render submissions, normal-library writes, or production deployment in implementation validation. Joe must authorize a fresh live budget separately.

## Luna sized implementation steps

### WP1 — Contracts and storage
- Dependencies: none.
- Files/interfaces: new typed packet records/model; focused session record owner; this plan.
- Work: define versioned packet, draft, attempt/seed set, decision, and budget data; keep paths portable and records bound to the owning universe/run.
- Acceptance: disposable records round-trip; foreign universe and unsupported versions fail visibly.
- Validation: focused Python syntax and disposable serializer checks.
- Status: implemented; disposable packet round-trip and unsupported-version checks pass.

### WP2 — Template image resolution
- Dependencies: WP1.
- Files/interfaces: prompt-packet service; existing auxiliary/reference resolver owners; opt-in task-template metadata.
- Work: parse versioned `ZET:PROMPT_PACKET` declarations, remove metadata from render prose, resolve explicit sources and audiences, and freeze mutable image bytes once per packet.
- Acceptance: inventory, selected/locked batch, and locked-pipeline sources resolve in declared order; missing/ambiguous sources fail before inference; old templates compile unchanged; later source unlock does not rewrite packet inputs.
- Validation: disposable resolver/compiler checks.
- Status: implemented; nested source-selector metadata parse/strip check passes; resolver ordering and missing/ambiguous-source checks remain to be run.

### WP3 — Costume packet adapter
- Dependencies: WP2.
- Files/interfaces: Costume-Dressing compiler adapter and shared packet contract.
- Work: expose conditioned source facts, constraints, view, sources/hashes, reference manifest, preset and deterministic compiled baseline; retain pipeline-owned criteria.
- Acceptance: isolated packet matches legacy deterministic compilation and image order.
- Validation: disposable Tsaeytte-compatible compile without rendering.
- Status: implemented; isolated compiler-parity check remains to be run.

### WP4 — Guidance and spending policy
- Dependencies: WP1.
- Files/interfaces: LLM role/skill composition; AI_Proxy model catalog; `CodexUsageService`; focused pilot policy.
- Work: register a prompt-authoring role, add repo-owned Costume and Head-Image Edit guidance, freeze module hashes, implement local/Luna/explicit-higher tiers, reserve/cap LLM submissions and guard Codex calls by quota reserve.
- Acceptance: model capability restrictions, usage unknown/low gate, escalation, deduplicated reservation, and 12-call case/36-call pilot limits are covered without inference.
- Validation: prepared-request and disposable budget checks.
- Status: implemented; disposable pilot aggregate 36-call/48-render caps pass; provider-preflight behavior remains to be exercised with prepared catalog/quota responses.

### WP5 — Draft/review session
- Dependencies: WP3-WP4.
- Files/interfaces: focused prompt-generator service and local workflow action boundary.
- Work: create immutable packet revisions; submit structured draft; expose prompt editing, reference/constraint validation, exact-text approval, feedback and resume/cancel. Draft citation IDs resolve only to renderer attachments.
- Acceptance: edits revoke approval; unknown/analysis-only references, stale packet hashes, missing required clauses, placeholders and unsupported modes block render; AI jobs remain attempt-fenced.
- Validation: mocked/prepared AI answers and disposable session lifecycle checks.
- Status: implemented; full prepared-answer lifecycle and late-result fencing checks remain to be run.

### WP6 — Private four-seed render trials
- Dependencies: WP5.
- Files/interfaces: focused trial service using frozen input and existing AI continuation/render collection.
- Work: run four baseline seeds, up to three four-seed prompt rounds, explicit image-edit attempts and retries; reserve budget before dispatch; keep outcomes outside batch slots.
- Acceptance: each complete round has four outputs with fixed seed set; 16 render maximum per case/48 pilot; collection replay is idempotent; manifest/settings/prompt survive reload and replay.
- Validation: prepared render responses, no live model/render execution.
- Status: implemented; retry dispatch matching was corrected in final review; prepared-render replay checks remain to be run.

### WP7 — Dashboard review page
- Dependencies: WP6.
- Files/interfaces: new focused local-character pilot template/JS/styles and existing local pipeline router/navigation.
- Work: display packet facts and both image lists, criteria, prompt edit/approval, model/usage state, four-seed baseline/trial comparisons, feedback, budget and clear separate actions.
- Acceptance: user can resume, see partial/failed rounds, accept an image, adopt separately, or save a reviewed durable proposal; responsive layout and clear failure states.
- Validation: isolated browser with prepared responses at desktop/narrow widths.
- Status: implemented; no dedicated browser check of the new page has been run.

### WP8 — Adoption and publication provenance
- Dependencies: WP6-WP7.
- Files/interfaces: local candidate/promotion, asset store, catalog lock transaction, source review integration.
- Work: adopt to an empty managed slot without touching protected images; persist exact prompt and compact manifest in existing catalog prompt/provenance within lock transaction; make pilot publication rely on captured provenance without current guide checks; keep source proposals separate and reviewed.
- Acceptance: selected/locked flow remains explicit; catalog record survives session cleanup/recovery and retains ordered identities/hashes; old candidate guide rules remain unchanged.
- Validation: isolated catalog transaction/recovery, universe, unlock, selection and lock checks.
- Status: implemented with a review-proposal boundary; isolated catalog recovery checks remain to be run. Reusable decisions are persisted as `READY_FOR_REVIEW` proposals but do not launch a separate source/template editor workflow.

### WP9 — Head-Image Edit adapter
- Dependencies: WP8.
- Files/interfaces: Head-Image Edit compiler adapter and prompt guidance.
- Work: supply own facts, edit-base/guide roles, constraints, criteria, render preset, and acceptance semantics to shared session API.
- Acceptance: full four-seed prepared-response flow works without Costume-specific assumptions.
- Validation: isolated Head-Image Edit compile/session/browser checks.
- Status: implemented; Head-Image Edit prepared-response checks remain to be run.

### WP10 — Integration and knowledge
- Dependencies: WP9.
- Files/interfaces: affected component/data/invariant/code-map/testing docs and focused ADR if durable decisions warrant one.
- Work: update only verified owners, record boundaries, schema additions, usage and live-call limits, known coverage gaps and actual validation. Review diff and preserve unrelated checkout changes.
- Acceptance: documents agree with implementation and no live check is implied by prepared verification.
- Validation: approved focused S2, `npm.cmd run test:e2e`, changed-file syntax and `git diff --check`.
- Status: in progress; documentation and regression validation are recorded below.

### WP11 — separately authorized live evaluation
- Dependencies: WP10 and fresh explicit live budget authorization.
- Files/interfaces: three dashboard pilot sessions and private evidence report.
- Work: Tsaeytte BACK_LEFT_3_4; one Joe-selected second costume view; one Joe-selected Head-Image Edit task. Use four fixed seeds for each baseline/trial round. Case max is 16 render submissions and 12 LLM calls; pilot max is 48/36.
- Acceptance: report Joe-scored criteria per image, accepted count out of four, repeated/seed-specific variance, time/edit effort, usage, and recommendation. One accepted result is usable evidence but report the four-seed acceptance count; no claim of broad generality.
- Validation: human visual review and evidence audit. No live action during software implementation.
- Status: pending and unbudgeted.

## Risks and decisions

- Final prompt completeness has a structural floor (required-clause and citation validation), but visual quality and subtle contradictions require Joe's review.
- Four seeds improve variance evidence but do not prove generality beyond tested settings/reference strategies. Seed-aligned comparisons make regressions visible.
- Retries/escalations consume allowance; paused quota and exhausted caps preserve session state and require explicit resumption/budget increase.
- Prompt/manifest persistence must fit existing prompt/provenance storage and publication transaction; no new reference-byte duplication.
- Official Codex app-server rate-limit reading and model discovery are available through current local services; reported token activity is not per-call price.
- Second costume and Head-Image Edit task are selected at pilot setup. Local calibration and Narrative/general Image Generation integrations are outside this pilot.

## Progress and decisions

- 2026-10-24: verified overview, architecture owners and approved scenarios. Checkout contains an unrelated untracked `Docs-Joe/Prompt_Generator_Pilot_Overview.md`; preserve it. No live inference/render budget or permanent tests are authorized.
- 2026-10-24: implemented packet/session contracts, template image declarations and snapshots, Costume and Head-Image Edit adapters, guidance/model policy, draft/review actions, private four-seed trials, dashboard, adoption/publication provenance, and affected knowledge owners. No live inference/render calls or permanent tests were added.
- 2026-10-24: final review fixed retry result matching, made the structured draft require both packet ID and hash, and replaced nested-JSON regex parsing with a JSON-aware declaration parser. Explicit remaining checks: resolver/compiler parity, prepared AI/render lifecycle and recovery, new-page browser behavior, and publication recovery transaction. Source/template decisions currently persist as separate review proposals and do not launch the destination-specific editor workflow.

## Validation and final results

Planned: targeted disposable checks at service boundaries; focused S2 after publication integration; approved `npm.cmd run test:e2e`; syntax and `git diff --check`. No live model/render check is planned under this software authorization.

Observed: `py -3 -m py_compile` passed for all changed Python modules; `node --check` passed for both changed JavaScript files. Disposable checks passed packet round-trip/version rejection, packet ID/hash and citation/constraint validation, nested declaration parsing, and the 36-call/48-render pilot ledger boundaries. `npm.cmd run test:e2e` passed all four approved scenarios (39.5s); `git diff --check` passed with existing LF-to-CRLF working-copy warnings. The new dashboard has not received a dedicated browser check; prepared provider/render replay and isolated catalog recovery checks remain outstanding. Live evaluation remains pending fresh authorization.
