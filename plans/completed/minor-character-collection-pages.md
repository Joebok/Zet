# Minor Character collection pages

Status: complete

## Work packets

1. Service and router: project all six assets in the list and collection responses. Serve bounded locked previews and collection-level Intake status. Verified lock gating, missing images, and universe-scoped requests.
2. Dashboard markup and controller: share the asset grid between overview and container. Move Intake to Template Improvement. Verified locked Draft and Final images, placeholders, links, and settings visibility.
3. Dashboard routes and Candidate Board: preserve character-only URLs and add the view parameter. Keep authoring scoped to the asset and write accepted changes to the shared template. Verified reload, history, outgoing settings saves, Inventory handoff, and refresh after lock changes.
4. Updated Dashboard UI, Local Characters, code map, and ADR 0050. The existing template, board, and publication records support the new layout.

## Validation

- npm.cmd run test:e2e passed all four approved scenarios in 41.0 seconds.
- Disposable isolated browser and service checks passed for the two-collection grid, unavailable preview fallback, unlocked selection, lock and unlock, missing routes, scoped preview requests, Inventory ownership handoff, blank-field Intake, and fresh Style interviews using accepted template changes.
- JavaScript syntax checks for both controllers, Python AST checks for the service and router, and git diff --check passed.
- Verification used isolated storage and prepared AI responses.
