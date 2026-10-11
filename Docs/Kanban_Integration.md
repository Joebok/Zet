# Kanban task forwarding and capture (packets 04–09)

Zet now exposes task forwarding through `ZetApp.create_task(payload)` and
`POST /api/tasks`. Kanban owns its board files, intake validation, and request-ID
receipts. Zet never reads or writes those files. Auxiliary-page context and
screenshots are available in packet 08. Packet 09 retires the markdown To Do editor. The main dashboard now has Create task and Open board toolbar actions.

## Dashboard capture (packet 05)

Create task opens a compact Bug, Improvement, or Feature report with a context
preview. Bug details are optional. The page, universe, timestamp, running revision,
and relevant character/phase IDs and labels come from an explicit dashboard
provider. Global tools exclude stale character selections. Local pipeline capture
and story restoration are described below, alongside auxiliary-page capture and
optional screenshot attachments. Arbitrary URL parameters, prompts, source
documents, and application state are not copied. Navigation links include the
recorded page and supported context parameters.

Context freezes when the form opens, including while configuration is loading.
Refresh context replaces it explicitly before delivery. Closing the form keeps the
draft. One draft per browser origin is saved in localStorage and survives reloads.
This includes the user-entered brief; use this feature in a trusted browser profile.
If browser storage fails, the form reports that only the open tab retains the draft.

The first delivery attempt locks the entire report and project mapping. Retry
submission sends the identical body and request ID, even after reload or changes
elsewhere on the dashboard. Failure or an invalid receipt retains the draft. Success
clears it and provides Open task. Discard draft explicitly starts a new request;
after uncertain delivery it warns that the original ticket may already exist.
Only one submission can run at a time. The form remains available while Kanban is
offline or unconfigured; configure the registered project ID before submitting.
The markdown To Do editor is retired. Use Create task and Open board in the toolbar.

## Local context and Return to Zet (packet 06)

The four local asset pipelines capture character, phase, pipeline, batch/run, and
costume when applicable. Batch names and costume labels come from existing backend
responses. Loading and failed lookups retain requested identifiers with explicit
loading/unavailable states instead of treating stale details as selected. Global
tools and the unselected Batches page omit unrelated header selections.

Create task inside a local candidate review also records its candidate and the
matching backend local-asset key when available. Candidate details, file paths,
prompts, gate responses, and source documents are not copied. The Return to Zet
link restores the pipeline and batch; candidate review reopening is not included.

Each local Batches card has Create task. It reports that row's character, phase,
costume, and run, rather than the header context. Return to Zet opens Batches and
marks the recorded card when still present. Scene cards capture their story and
scene instead of an unrelated header character.

Task links carry `task_context=1` and `task_universe` plus supported selections.
They restore the recorded universe in this tab without writing the saved global
default. Local JSON requests and image URLs follow that universe. A missing
universe, character, phase, costume, or batch produces a visible restoration notice
while opening the recorded page with an available fallback. These links do not
start jobs or edit data. The original ticket snapshot and retry body remain intact.

## Story and Narrative Scenes (packet 07)

Both story interfaces use the same capture dialog and retry behavior. The main
dashboard records relevant story/scene IDs and labels, Scene Builder subscene/render
target and selected editor element, selected Zine document, candidate source and candidate, and Scene
Renders batch/review candidate. Character/phase/costume references on a selected
builder element are diagnostic context. Source documents, candidate prompts, and
image contents are excluded.

Narrative Scenes has Create task and Open board in its header, plus Create task in
image review. Reports record that interface's own story, scene, target, and candidate
IDs with resolved titles. Subscene, backdrop, and final assembly remain distinct;
only a subscene creates a subscene selection. Narrative IDs and dashboard story
slugs are not translated or merged.

Return to Zet uses each interface's own navigation parameters. It restores candidate
source/filter selection on the dashboard, or opens a Narrative/render-batch review
for an available recorded image. Missing references produce a notice and an
available fallback or a readable unavailable workspace. Loading snapshots retain
requested identifiers. The shared form does not save Narrative editor content.
Scene-batch task links use GET requests and never initialize a missing batch,
including when a missing scene causes a fallback. Existing explicit workflow
actions retain their behavior.

## Auxiliary pages and screenshots (packet 08)

Local Character Overview, Gate Test Rig, and Gate Test Data have Create task and
Open board in their headers. Overview slot buttons capture their own character,
phase, costume, pipeline, and autogeneration job. Gate case/result buttons capture
pipeline, gate, test case, and the displayed run when applicable. Supported editor
fields identify the selected control without copying its contents. Labels and
availability come from the existing backend overview/catalog/case/run responses.
Return links restore and mark a slot or case, and reopen saved tests or recorded
runs through read requests. Missing references produce a visible notice. Recorded
universes bind API requests and image links without changing the global default.
Return links never start a run, save a test, or generate an image.

Image Generation review also has Create task, capturing its job and result IDs
without prompts or pixels. Its return link opens Image Generation; job/result IDs
are diagnostic context and do not restore another browser's local slot layout.
The existing local pipeline, scene-batch, and Narrative review actions use the same
screenshot form.

Upload or paste up to four PNG, JPEG, or WebP screenshots (5 MiB each). Remove
unwanted screenshots before the first submission. Images remain optional and are
included only when the user selects or pastes them. The draft stores their bytes
locally alongside the report. Browser quotas may be smaller than the combined
image limit: a storage failure explicitly warns that only the open tab retains the
latest draft. Keep that tab open to retry, or reduce screenshots before submission.
Screenshots are never resized or silently substituted.

First submission freezes the brief, project mapping, and screenshot list. Each
image goes to `POST /api/tasks/attachments`, which forwards JSON to Kanban's
`POST /api/v1/attachments`. Requests are bounded to 7 MiB and include the original
project/request IDs, plain filename, fixed image MIME type, and `content_base64`.
The service verifies the returned identifier, size, SHA-256, metadata, and creation
status. Kanban performs image signature recognition and owns local storage.
Only attachment IDs go in the intake report; raw images are not report context.

Upload receipts are saved with the locked draft. Retry skips acknowledged uploads,
replays uncertain uploads with identical bytes/binding, and retries intake with the
same report and attachment references. Upload failure prevents intake submission.
Nothing is discarded automatically on error. Success clears the local draft.
This requires Kanban packet 08A, merged in
[PR #5](https://github.com/Joebok/Zet_Kanban/pull/5).

## Markdown To Do retirement (packet 09)

Create task and Open board replace the old Tools → To Do action. The markdown
dialog, its autosave/submit handlers, GET/POST `/api/todo` routes, and ZetApp
markdown editing methods have been removed. Calls to the retired routes return
404. `Docs/ToDo.md` remains untouched; reports are not automatically migrated
from that historical document. The unrelated asset **To Do Only** filter retains
its existing behavior of hiding locked assets.

The Help page explains task capture, frozen context, optional screenshots, draft
retention, retries, and Return to Zet. Existing template manual navigation remains.

## Configuration

Register the `Zet_v5` project in the Kanban board's Projects dialog. Copy its
`project-xxxxxxxx` ID into Zet's configuration and restart Zet:

```toml
[Kanban]
BaseURL = "http://127.0.0.1:8000"
ProjectID = "project-aaaaaaaa"
TimeoutSeconds = 5.0
```

The example ID is illustrative; use the actual registered ID. BaseURL is an
HTTP(S) origin without a path, credentials, query, or fragment. The default is
loopback. Timeout must be finite, positive, and at most 60 seconds. An empty
ProjectID leaves task creation unconfigured without contacting Kanban or preventing
ordinary dashboard startup. Other universes retain this shared project mapping.

`GET /api/tasks/config` returns local metadata:

```json
{
  "configured": true,
  "board_url": "http://127.0.0.1:8000/",
  "project_id": "project-aaaaaaaa",
  "report_context_version": 1,
  "zet_revision": null
}
```

`configured` indicates a project mapping, not server reachability. Revision is
captured when the service starts and is null if Git metadata is unavailable.
Reading configuration performs no Kanban request.

## Forwarding and retries

Submit a complete frozen context-v1 report compatible with Kanban's
[intake contract](https://github.com/Joebok/Zet_Kanban/blob/main/docs/intake-contract.md).
Supported top-level fields are request_id, project_id, type, title, description,
expected_behavior, actual_behavior, reproduction_steps, context, and optional
attachment_ids (up to four unique registered screenshot identifiers). The producer
must supply a stable request ID and complete capture metadata before first delivery.
Zet adds the configured project ID if omitted; a supplied ID must match it.

Zet preserves the original request ID, timestamp, revision, selection IDs/labels,
and report contents. It does not regenerate metadata, resolve current selections
during retry, allocate new IDs, automatically register projects, or run agents.
Explicit page providers prepare the snapshot before submission.

The service sends one JSON POST to the configured `/api/v1/intake` with its timeout.
Ambient HTTP proxies and redirects are disabled. It verifies the returned task ID,
relative task link, and creation/replay status before returning success:

```json
{
  "task_id": "task-aaaaaaaa",
  "board_url": "http://127.0.0.1:8000/?task_id=task-aaaaaaaa",
  "created": true
}
```

First creation returns HTTP 201; identical retries return 200 with `created:false`
and the same ticket. The absolute board link uses the configured Kanban origin.
An unconfigured mapping or failed connection returns 503; timeout returns 504;
invalid receipts, redirects, or unexpected upstream responses return 502. Upstream
400/404/409/413/415/422 statuses are preserved with a bounded validation message, without
echoing submitted values from validation errors.

After uncertain delivery, retain the draft and retry the same frozen body and ID.
Zet does not retry automatically. A changed project mapping or report can cause
409; use the original mapping/body for a retry, or a new ID for genuinely new work.

## Delivery

Packet 03 is merged in [Kanban PR #4](https://github.com/Joebok/Zet_Kanban/pull/4).
Packet 04 is merged in [Zet PR #31](https://github.com/Joebok/Zet/pull/31).
Packet 05 is merged in [Zet PR #33](https://github.com/Joebok/Zet/pull/33).
Packet 06 is merged in [Zet PR #35](https://github.com/Joebok/Zet/pull/35).
Packet 07 is merged in [Zet PR #36](https://github.com/Joebok/Zet/pull/36).
Packet 08B is merged in [Zet PR #37](https://github.com/Joebok/Zet/pull/37).
Packets 04–09 target Zet's active dashboard branch
`V5-Re-Alignment-to-Local-Image-Generation`, as selected by the user, rather than
including its unrelated development history in a PR against main. No live board
reset, task creation, agent execution, or library changes are part of validation.
