# AI queues, harvesting, and recovery

Zet is a **producer/subscriber** of a separate AI Proxy system. Queue payloads may be shared across machines; consumer routes and completion state may be local. This document owns transport/recovery flow; per-workflow state semantics belong to [LOCAL_CHARACTERS](LOCAL_CHARACTERS.md), [SCENE_BUILDER](SCENE_BUILDER.md), or [NARRATIVE](NARRATIVE.md).

## Interfaces and storage boundaries

- [FileProxyClient](../../zet/services/file_proxy_client.py) fixes `subscriber_id=zet`, maps `ollama_generate` to `ollama` and `local_image_render` to `local_image`, and exposes `create_staging`, `publish`, `answer_is_ready`, `load_route` and queue scans.
- Shared layout: `<BaseAIQueuePath>/File_Proxy/{Ask,Running,Answer}/zet/<job-id>/`. `job.json` protocol version 1 records file inventory, producer ID, worker/resource key, route requirement and priority. `ask_manifest.json` carries workflow instructions; responses have answer/proxy-result/output artifacts.
- [AIProxyService](../../zet/services/ai_proxy_service.py) packages supported asks, including scene/local render tasks and prompt work. [AIProxyPathService](../../zet/services/ai_proxy_path_service.py) abstracts roots/task scans and manual queues. [AI_Manager](../../AI_Manager/) holds worker adapters; external AI Proxy owns the shared dispatcher.
- Structured Ollama inference shared by Image Prompt Generation, Reconstruction, Costume Wizard, and Quick Character workflows is staged by [OllamaModelService](../../zet/services/ollama_model_service.py) as an `ollama_generate` job. It snapshots ordered image inputs and schema into the ask, waits for the matching File Proxy answer, and reads model runtime evidence from its answer manifest. These asks use an external consumer marker so the generic Zet harvester leaves their answer for the waiting service; successful answers are then completed through queue lifecycle receipts. Model catalog discovery remains a metadata lookup and does not run inference.
- Manual final-render tasks use `<BaseAIQueuePath>/Manual_Render_Queue/{Ask,Answer}`. [ManualRenderPublicationService](../../zet/services/manual_render_publication_service.py), [ManualRenderSubmissionService](../../zet/services/manual_render_submission_service.py), and retained [RenderConsoleQueue](../../zet/render_console/queue.py) support that dashboard workflow.
- [AIQueueLifecycleService](../../zet/services/ai_queue_lifecycle_service.py) owns producer-local `Inbox`, `Receipts`, `Routes`, and optional `Debug`; [queue_local_state_root](../../zet/services/ai_queue_paths.py) keys these by queue path and hostname. Shared `Zet_File_Proxy_State` still holds some markers/archive state and legacy route compatibility; not all task state is local.

## Publication and answer lifecycle

File Proxy routes remain producer-local. Route destinations owned by a library are written relative to their declared universe and resolved by the matching producer before result application; shared asks, answers, bundles, producer identity, and attempt fences keep their existing ownership. The offline updater scans only current-producer routes and refuses to edit shared transport bundles. See [portable library references](../DECISIONS/0011-portable-library-references.md).

```mermaid
flowchart LR
    Snapshot[Freeze prompt and reference bytes] --> Hidden[Hidden staging bundle]
    Hidden --> Ready[Atomic publish to Ask]
    Ready --> Running[External worker: Running]
    Running --> Answer[Answer with inventory and output]
    Answer --> Local[Verify and drain to local Inbox]
    Local --> Apply[Owner/attempt check and apply result]
    Apply --> Receipt[Durable receipt and cleanup/debug retention]
```

`publish` copies/localizes absolute input paths and ordered references, externalizes absolute output routes, writes a file inventory, and renames staging to ready. Local routing is required for jobs that need it; portable bundles do not carry arbitrary machine output paths. Readiness checks reject incomplete or hash/size-invalid payloads rather than assuming any Answer folder is complete.

`drain_answer` verifies direct-child location, symlink restrictions, matching producer, readiness, and equal copied contents before removing the shared source. Copy failure leaves the source available. Receipts handle a leftover shared duplicate; debug retention preserves selected local payload when enabled.

[AIAnswerHarvester](../../zet/services/ai_answer_harvester.py) dispatches supported task results, reconstructs routes, checks ownership/attempts, writes harvest status and delegates scene review where required. Local pipeline and Narrative services also reconcile their own jobs; do not assume the generic harvester owns every consumer. [workflow_storage.py](../../zet/services/workflow_storage.py) supplies image validation, locks, immutable manual snapshots and supersession markers. Stopping/withdrawing queued work must fence late answers even when a running worker cannot be removed immediately.

## Background execution and failure investigation

[auto_harvest_ai_answers.py](../../zet/scripts/auto_harvest_ai_answers.py) and platform launchers provide separate harvester execution. [ProcessService](../../zet/services/process_service.py) manages dashboard/harvester process discovery and [PipelineControlService](../../zet/services/pipeline_control_service.py) exposes controls. FastAPI lifespan additionally starts index reconciliation, ad hoc image work, Narrative polling, and local workflow recovery; it is not the external queue dispatcher.

Both dashboard restart paths manage the harvester lifecycle. ProcessService recognizes release configs under the same `Runtime.Root/releases` directory, so workers left by an earlier release remain visible and manageable. A current-version self-restart stops matching harvesters before scheduling Zet shutdown; the detached restart helper starts Zet and then the harvester with the active config. Update promotion captures managed Zet and harvester PIDs before staging, stops those exact processes after validation, then starts the promoted dashboard and harvester.

The AI Queue dashboard reads current Ask/Running/Answer folders directly and combines recent indexed history with producer-local receipts. Receipts are available before the background library-index scan catches up, so the first recent-history page must use [ZetApp.recent_ai_harvests](../../zet/app.py); later cursor pages come from the derived index.

Failures include mismatched queue roots, absent workers, incomplete Dropbox sync, missing local routes, foreign producers/universes, superseded attempts, invalid output bytes, blocked Windows replacement, and failed archive/copy operations. Inspect `job.json`, ask/answer manifests, `proxy_result.json`, receipts, superseded markers, and owning workflow errors. Prefer service recovery/retry logic over moving/deleting folders manually. [INVARIANTS](../INVARIANTS.md) owns ordering, ownership, locking and stale-result contracts.

When adding a task type, define producer manifest, input snapshots, worker/response contract, routing, owner/attempt checks, result application, restart/duplicate semantics, and cleanup together. A new router alone is insufficient. Live queue mutations and real rendering are separate operations from fixture-based tests.

## Tests and related decisions

[fast.spec.mjs](../../tests/e2e/fast.spec.mjs) S2/S3 publish real private asks and consume prepared answers through local/Narrative workflow services; the fast suite does not run the external dispatcher or generic harvester. The separately requested [live check](../../tests/e2e/live.spec.mjs) starts a private AI Proxy for Narrative final synthesis/rendering. No dedicated maintained scenario covers every readiness, producer/universe ownership, stale answer, receipt, copy-failure or manual-upload branch. See [Testing](../Testing.md). [ADR 0001](../DECISIONS/0001-library-authority-and-derived-index.md) distinguishes authored and local state; production policy is [ADR 0003](../DECISIONS/0003-local-character-production-boundary.md).

## Retired scene ownership

Scene Builder producers, batch services and recovery wiring no longer dispatch work.
Owned late legacy scene/prompt-analysis answers are marked superseded without publishing
into either source or Narrative records; answer bytes and attribution remain preserved.
Foreign universe/consumer results still fail or skip ownership checks. Existing shared
queue files are not automatically cancelled/deleted during migration. Narrative jobs
retain independent consumer IDs and attempt fencing. Manual scene publication recovery
is fenced; supported character/manual transports remain available.

## Supplemental render-slot work (2026-10-12)
Character slot allocation saves new candidate identities and target IDs before dispatch. An independent slot collector resumes persisted `slot_render_ids` after restart; existing batch runners exclude these additions and empty slots are not queued work. New slot actions can publish while other renders run, with state transactions fencing cleared candidates. Clearing/replacing a candidate detaches its active membership and changes the advisory evaluation fence, retaining old artifacts so late answers cannot populate replacement slots. Prompt/reference snapshots persist per candidate and remain ordered. Image Generation saves its board reservation before staging jobs and persists child seeds/status/errors; new result arrays are indexed by submission child rather than arrival order. Queue publication/readiness/ownership protocols are unchanged. See [ADR 0007](../DECISIONS/0007-stable-render-slots.md).
