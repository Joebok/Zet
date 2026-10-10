# Kanban task forwarding and capture (packets 04–05)

Zet now exposes task forwarding through `ZetApp.create_task(payload)` and
`POST /api/tasks`. Kanban owns its board files, intake validation, and request-ID
receipts. Zet never reads or writes those files. Specialized workspace context
providers, attachments, and removal of To Do are later
packets. The main dashboard now has Create task and Open board toolbar actions.

## Dashboard capture (packet 05)

Create task opens a compact Bug, Improvement, or Feature report with a context
preview. Bug details are optional. The page, universe, timestamp, running revision,
and relevant character/phase IDs and labels come from an explicit dashboard
provider. Global tools exclude stale character selections. Local pipeline, story,
auxiliary page, and attachment providers arrive in packets 06–08; those specialized
selections are not captured yet. Arbitrary URL parameters, prompts, source
documents, and application state are not copied. Navigation links include the
recorded page and supported context parameters; fuller restoration is packet 06–08.

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
The existing markdown To Do editor remains until replacement coverage in packet 09.

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
expected_behavior, actual_behavior, reproduction_steps, and context. The producer
must supply a stable request ID and complete capture metadata before first delivery.
Zet adds the configured project ID if omitted; a supplied ID must match it.

Zet preserves the original request ID, timestamp, revision, selection IDs/labels,
and report contents. It does not regenerate metadata, resolve current selections
during retry, allocate new IDs, automatically register projects, or run agents.
Later context providers prepare the snapshot before submission.

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
400/404/409/422 statuses are preserved with a bounded validation message, without
echoing submitted values from validation errors.

After uncertain delivery, retain the draft and retry the same frozen body and ID.
Zet does not retry automatically. A changed project mapping or report can cause
409; use the original mapping/body for a retry, or a new ID for genuinely new work.

## Delivery

Packet 03 is merged in [Kanban PR #4](https://github.com/Joebok/Zet_Kanban/pull/4).
This packet targets Zet's active dashboard branch
`V5-Re-Alignment-to-Local-Image-Generation`, as selected by the user, rather than
including its unrelated development history in a PR against main. No live board
reset, task creation, agent execution, or library changes are part of validation.
