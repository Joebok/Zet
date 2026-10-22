# Zet Code Review

## Architecture Summary

- **Request path:** FastAPI `create_app` builds a `ZetApp` composition root and a per-universe application cache keyed by the `X-Zet-Universe` header/`universe_id` query parameter. Routes delegate to `ZetApp` and focused services; there is no authentication layer, so the browser and any LAN/Tailscale client are equally trusted.
- **Durable state:** authored data is split between universe-owned JSON records and `catalog.sqlite3` (authoritative image library), with a derived machine-local index. AI work uses filesystem queues and attempt/receipt files, protected by `file_lock`, atomic replacement, and a storage-health journal that is intentionally outside the monitored volumes.
- **Runtime shape:** background reconciliation (library index, AI job coordinator, workflow continuations) runs alongside a large browser client (`zet.js`, ~654 KB) and a ~3.8k-line `zet/web/app.py`. The hot paths are inventory listing, prompt analysis polling, per-request universe binding, and uploads.

## Correctness & Edge Cases

### C1. `/api/file` serves arbitrary files outside the universe

**Location:** `zet/web/app.py:2579-2588` (`local_file`); `zet/services/path_service.py:126-138` (`resolve_path`), `81-108` (`resolve_library_path`)

**Severity:** Critical

**Why it matters:** `resolve_path` is not a confinement check. A relative path falls through to `project_root.joinpath(*parts)` with no `..` rejection, and an absolute path that is not under a library root is returned as-is by `resolve_library_path`. Therefore `GET /api/file?path=..\\..\\Windows\\win.ini` or `?path=C:\\Users\\...\\secret` returns the file. Combined with the missing authentication layer, any LAN/Tailscale client can read arbitrary readable files, including configuration and other users' data. This contradicts the documented rule that library readers reject traversal and foreign-universe paths.

**Proposed fix:** Resolve first, then enforce an allowlist of served roots and reject anything else. Do not rely on `PathService` callers to validate:

```python
requested = zet_app.path_service.resolve_path(path).resolve()
roots = [
    Path(zet_app.config.base_library_path).resolve(),
    (PROJECT_ROOT / "Shared_Library").resolve(),
    # add explicit read-only render/queue roots only if the UI needs them
]
if not any(requested.is_relative_to(root) for root in roots):
    raise HTTPException(status_code=404, detail=f"File not found: {path}")
```

Also harden `resolve_path` for relative inputs (`candidate = self.project_root.joinpath(*parts).resolve(); if not candidate.is_relative_to(self.project_root): raise ValueError(...)`) and add a `GET /api/file` regression check for `..` and absolute paths.

### C2. Prompt-generation routes use the startup universe's service

**Location:** `zet/web/app.py:1015-1019` (singleton creation), `1754-1773` (routes); `zet/services/image_prompt_generation_service.py:65-86` (`start`), `88-107` (`status`)

**Severity:** Major

**Why it matters:** `app.state.image_prompt_generation_service` is constructed once with the initial `app.state.zet_app`. The routes never call `_app(...)`, so after the user switches universes, or after `_reload_app` replaces `app.state.zet_app`, prompt/identity jobs still read the asset from the startup universe (`self.zet_app.entity_library_asset`). For a non-startup universe this normally fails with "image not found"; if IDs ever collide, it would analyze the wrong universe's asset, and job status validates the checksum against the wrong library. Job status has the same ownership problem.

**Proposed fix:** Resolve the service from the request's universe, and persist the owning universe in the job record:

```python
zet_app = _app(app.state.config_path)
prompt = image_services(zet_app)[1]
return prompt.start(asset_id)
```

For status, include `"universe_id": self.zet_app.universe_id` in the job JSON and load that universe before reading the job. Update `_reload_app` to replace the singleton if it remains.

### C3. `promote_chain` publishes images with numeric labels

**Location:** `zet/services/local_asset_store_service.py:30-43` (`_publish`), `272-303` (`promote_chain`); caller `zet/services/local_character_asset_pipeline_service.py:1367-1372, 1393-1400`

**Severity:** Major

**Why it matters:** `promote_chain` copies each candidate to a staging file named `"{index}{suffix}"` (line 293), and `_publish` then uses `label=image.stem` (line 41). Every non-costume library asset published through this path is therefore labeled `"0"`, `"1"`, etc., instead of the batch/candidate name. The caller already computes `batch_name` (line 1371) but does not pass it. This breaks library search, duplicate recognition, and user-facing identification of locked images.

**Proposed fix:** Make the label explicit through the publication boundary:

```python
def _publish(self, image: Path, *, label: str, ...):
    return self._entity_library.register_locked_pipeline_image(
        image, label=label, ...)

# promote_chain
published = self._publish(
    staging_image,
    label=str(item.get("batch_name") or image.stem),
    ...)
```

Use the same constructed label in `lock()` rather than a staging/hash filename.

### C4. `promote_chain` is not atomic and `lock()` publishes before persisting state

**Location:** `zet/services/local_asset_store_service.py:241-270` (`lock`), `272-332` (`promote_chain`)

**Severity:** Major

**Why it matters:** The docstring on `promote_chain` says "Atomically publish a preflighted set", but each `_publish` performs its own image copy and SQLite transaction. If item N fails, items 1..N-1 are already approved, visible, and not rolled back; the local record write at line 331 never happens, so the UI reports failure while the library contains partial results. `lock()` has the same ordering hazard: it publishes at line 254, then writes the local record at line 269. A failure between those points leaves a published asset that the local store does not know is locked. Retrying is idempotent only because `origin_key` deduplicates; the visible partial state is still wrong.

**Proposed fix:** Add a batch publication method that stages all files, inserts all catalog rows in one `repository.transaction()`, and only then writes the local state. If a cross-store (SQLite + JSON) transaction is not practical, compensate on failure by archiving/deleting every asset published in this call before re-raising, and document that the operation is recoverable rather than atomic. At minimum, add a `try/except` around the publication loop that records the already-published `asset_id`s and archives them.

### C5. Prompt-job status polling blocks for the entire model call

**Location:** `zet/services/image_prompt_generation_service.py:88-111` (`status`, `_run`), `113-149` (`_execute_analysis`); model default timeout `zet/services/ai_job_service.py:338` (`timeout=1800`)

**Severity:** Major

**Why it matters:** `_run` holds both `self._lock` (an RLock) and the per-job `file_lock` while calling `_execute_analysis`, which performs the blocking model request. `status()` acquires the same RLock and the same file lock, so every status poll waits until the model returns, up to 30 minutes. Because the status route is a synchronous `def`, blocked polls consume FastAPI's default threadpool; a handful of jobs can stall all synchronous routes.

**Proposed fix:** Keep the file lock for short state transitions only:

```python
def _run(self, job_id, asset):
    with self._lock:
        self._jobs[job_id]["status"] = "RUNNING"
    draft = self._execute_model(asset)          # no lock held
    with self._lock, file_lock(self._job_lock(job_id)):
        self._jobs[job_id].update(status="COMPLETE", draft=draft)
        write_json_atomic(self._record_path(job_id), self._jobs[job_id])
```

If `_run` must be exclusive, use a separate execution lock and let `status()` read the atomically written job JSON without taking it.

### C6. Path-token sanitizers disagree across pipelines

**Location:** `zet/services/local_body_reference_service.py:247-249` (`_safe`); `zet/services/local_head_image_service.py:111-115`; `zet/services/local_character_asset_pipeline_service.py:116-120`; `zet/services/local_asset_store_service.py:52-57`

**Severity:** Minor

**Why it matters:** Body-Reference allows dots and silently maps invalid/empty values to `"unknown"`; the other services replace dots with underscores and raise on empty. A character such as `A.B` or a name containing spaces can therefore be stored under different directories by different pipelines, splitting the same character's assets between `A.B` and `A_B`. The `"unknown"` fallback can also collide distinct invalid inputs.

**Proposed fix:** Extract one `safe_path_token(value, field)` helper under `zet/services` and use it in all four services. Reject invalid values at the API boundary instead of rewriting them, and add a one-time consistency check/migration for existing directories if dotted names exist.

### C7. Universe selection is written non-atomically

**Location:** `zet/services/universe_service.py:83-87` (`select`)

**Severity:** Minor

**Why it matters:** `selection_path.write_text(...)` truncates the file before writing. A crash, disk-full condition, or removable-drive removal can leave an empty/truncated `selection` file. On next startup, `selection()` raises on `json.JSONDecodeError`, preventing the dashboard from opening until the file is repaired manually.

**Proposed fix:** Use the existing atomic writer:

```python
from zet.services.atomic_file_service import write_json_atomic
write_json_atomic(self.selection_path, {"universe_id": universe["universe_id"]})
```

Treat a malformed selection as recoverable (log and fall back to the first universe) rather than a hard startup failure.

### C8. Coordinator keeps the pre-reload `ZetApp`

**Location:** `zet/services/ai_job_coordinator.py:31-37`; `zet/web/app.py:1116-1131` (`_reload_app`)

**Severity:** Minor

**Why it matters:** `_reload_app` creates a replacement `ZetApp` and swaps `app.state.zet_app`, but the already-running `AIJobCoordinator` retains `self.app` and `self.repository`. After saving automation settings or replacing a universe app, the coordinator continues sweeping with the old app's services/settings and lifecycle root. The per-universe `_apps` cache has the same staleness for other universes.

**Proposed fix:** In `sweep()`, resolve the current app for the coordinator's universe (`app = self.resolve_app(self.app.universe_id)`) and rebuild `self.repository` if its lifecycle root changes. Alternatively, stop and recreate the coordinator inside `_reload_app`.

## Architecture & Modality

### A1. Three services reimplement the same character-run state machine

**Location:** `zet/services/local_body_reference_service.py` (~2.4k lines), `zet/services/local_head_image_service.py` (~1.2k lines), `zet/services/local_character_asset_pipeline_service.py` (~1.6k lines); shared method groups at body `1856-2130`, head `521-1000`, character `806-1403`

**Severity:** Minor

**Why it matters:** All three expose `select_view`, `lock_selected_view`, `unlock_view`, `execute_run`, retry/rerun/resume, and render polling. The implementations have already drifted: body `_wait_for_render` updates candidate status and harvests with different timing than head `_wait_render`; body wraps lock operations with `pause_on_storage_error`, while head relies on raw exceptions; body has `_execute_run_locked`, head does not. A fix in one pipeline routinely misses the other two, and the duplicate APIs make it unclear which service owns a new workflow rule.

**Proposed fix:** Extract the common lifecycle (run record, candidate polling, selection/lock fencing, storage-pause handling) into a `LocalViewRunService` parameterized by pipeline name, prompt blueprint, and permanent-publication strategy. Keep body/head/character services as thin adapters. Migrate one pipeline at a time behind the existing HTTP/service contract; do not change stored schemas during the extraction.

### A2. Request and browser code are concentrated in very large modules

**Location:** `zet/web/app.py` (~3.8k lines, 188 KB), `zet/web/static/zet.js` (~13.7k lines, 654 KB)

**Severity:** Nit

**Why it matters:** `app.py` mixes middleware, lifespan/recovery, per-universe cache management, route handlers, and payload builders. `zet.js` is a single global script loaded by every workspace, including Narrative and the local asset pipelines, with a large amount of mutable module state. This makes ownership and test isolation difficult and increases the chance of unrelated features breaking through shared globals.

**Proposed fix:** Split routes by domain into the existing router modules and move payload builders next to their service. Convert `zet.js` to ES modules, starting with the largest independent areas (`local asset pipeline`, `narrative`, `image library`), and lazy-load each workspace. This is a staged refactor; no behavior change is required in the first phase.

## Performance & Hot Paths

### P1. `list_assets` scans the entire catalog and all relations for a 10-row page

**Location:** `zet/services/entity_library_service.py:186-288` (`list_assets`), `1459-1460` (`search_picker`); route `zet/web/app.py:1683-1697`

**Severity:** Major

**Why it matters:** `list_assets` does `SELECT * FROM assets` with no filters, builds an `IN (?,...)` list from every asset ID, runs six relation queries with that list, then `Path.is_file()` for every asset, and filters/paginates in Python. The HTTP route defaults to `limit=10`, and the picker (`search_picker`) returns the whole approved library. Large libraries therefore pay full-table reads, multi-thousand-parameter SQL, and one stat call per asset for every page load. Older SQLite builds can hit the host-parameter limit outright; newer builds still pay the full I/O and memory cost.

**Proposed fix:** Push filters and pagination into SQL (`WHERE`, `ORDER BY`, `LIMIT/OFFSET`), use `EXISTS` for descriptor readiness, and fetch relations only for the current page's IDs. If the full ID list is still needed, chunk it (e.g. 500 IDs per query). Avoid a per-asset `is_file()` in the listing path; validate availability when the image is actually requested, or batch it with a targeted check.

### P2. `list_entities` and `list_variants` perform N+1 queries and connection churn

**Location:** `zet/services/entity_library_service.py:990-999` (`list_entities`), `1034-1042` (`list_variants`); repository `zet/repositories/entity_library_repository.py:196-209`

**Severity:** Major

**Why it matters:** Each entity costs three separate queries (`image_count`, `variant_count`, descriptors), and each variant costs two. Every `fetchone`/`fetchall` opens a new SQLite connection and calls `protect_catalog`, so 500 entities means ~1,500 connections plus marker checks for one inventory page. The endpoint is used by the entity library organizer, where this cost is paid on every refresh.

**Proposed fix:** Use aggregate joins:

```sql
SELECT e.*,
       (SELECT count(DISTINCT ae.asset_id) FROM asset_entities ae WHERE ae.entity_id=e.entity_id) AS image_count,
       (SELECT count(*) FROM variants v WHERE v.entity_id=e.entity_id) AS variant_count
FROM entities e
ORDER BY e.name COLLATE NOCASE
```

Fetch all descriptors for the returned IDs in one query and group them in Python. The same pattern applies to `list_variants`. Consider a single connection per request/transaction rather than per query.

### P3. Universe validation performs a directory scan on the event loop for every request

**Location:** `zet/web/app.py:1102-1114` (`bind_universe`); `zet/services/universe_service.py:51-68` (`list_universes`, `get_universe`)

**Severity:** Major

**Why it matters:** Every request carrying `X-Zet-Universe` (which the browser sends for all API calls) calls the synchronous `get_universe`, which re-scans the universe container and reads every `universe.json`, while running as `async def` on the event loop. On a removable/slow library volume this blocks all concurrent requests for the duration of the scan, and a transient I/O error turns an unrelated request into HTTP 400. Raw IDs are also used as cache keys: `"Moonsea "` passes `_safe_id` lookup but creates a second `ZetApp` (and reconciler) for the same universe.

**Proposed fix:** Cache universe descriptors in `UniverseService` (invalidate by directory mtime or explicit reload), or validate against the already-loaded `app.state.universe_apps` map. Normalize first:

```python
descriptor = app.state.zet_app.universe_service.get_universe(universe_id)
universe_id = descriptor["universe_id"]
```

If a cache miss requires disk access, run it via `run_in_threadpool` before continuing the middleware chain.

### P4. Async upload routes perform hashing, SQLite, and file writes on the event loop

**Location:** `zet/web/app.py:1716-1729` (`entity_library_import`), `1731-1739` (`entity_library_import_generated`), `1794-1799` (`entity_library_asset_replace`), `2043-2057` (`image_catalog_import`), `2139-2147` (`image_catalog_replace_content`), `2309-2324` (`costume_wizard_create`), `3154-3159` (`head_image_manifest_upload_source`)

**Severity:** Major

**Why it matters:** Each route is `async def` but after `await request.body()` it synchronously computes SHA-256, parses image dimensions, writes bytes, runs SQLite transactions, and sometimes updates thumbnails/catalog files. During that work the event loop cannot serve health checks, status polls, or other requests. A single large image upload can freeze the whole dashboard for seconds.

**Proposed fix:** Keep the body read asynchronous, then offload the blocking work:

```python
body = await request.body()
asset = await run_in_threadpool(
    _app(app.state.config_path).entity_library_import,
    label, request.headers.get("content-type", ""), body,
    entity_ids=..., set_ids=...)
```

Alternatively declare these routes as synchronous `def` with a `bytes` body parameter so FastAPI runs them in its threadpool. Apply the same treatment to the other upload routes listed above.

### P5. Workflow `resume()` re-enqueues every non-complete task every two seconds

**Location:** `zet/services/ai_workflow_service.py:19` (`_POOL`), `146-155` (`resume`); `zet/services/ai_job_coordinator.py:96-101, 318`

**Severity:** Minor

**Why it matters:** The coordinator calls `AIWorkflowService(app).resume()` on every two-second sweep for every universe. `resume` globs all workflow records and submits every `WAITING`, `RUNNING`, `PAUSED_STORAGE`, and `RECOVERING` record, relying on a 0.05-second file-lock timeout inside `run` to discard duplicates. Long model/render tasks are therefore resubmitted continuously, growing the executor's unbounded work queue and delaying newly submitted continuations; the executor has only four workers shared by all universes and services.

**Proposed fix:** Track active task IDs per process and skip already-enqueued IDs, or only call `resume` at startup and after a storage recovery transition. Use a bounded queue / per-service executor, and separate long model continuations from short reconciliation work.

### P6. Prompt-job state grows without bound

**Location:** `zet/services/image_prompt_generation_service.py:54-61` (startup load), `81-84` (`start`), `88-96` (`status`)

**Severity:** Nit

**Why it matters:** `self._jobs` is an in-memory dictionary populated on startup and on every `start`, with no eviction. Job JSON files under `records_root` are also never cleaned by this service. Over a long-running session with many prompt/identity generations, memory and directory scans grow, and `status` reads the job file on every poll.

**Proposed fix:** Add a TTL/cap to `_jobs` and a small cleanup routine for completed/failed job records (aligned with the existing job-cleanup retention rules). Keep the current job's state in memory but evict terminal entries after a bounded period.

## Validation

- Review was static. The `/api/file` traversal was reproduced with `PathService` using `../../Windows/win.ini` and `C:/Windows/win.ini`; both resolved outside the configured library root.
- No application code or tests were changed. No live services, AI Proxy, ComfyUI, or end-to-end scenarios were run.
