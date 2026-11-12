# Recent Renders
Status: complete

## Goal

List recent harvested images by Candidate Board in the selected universe. Keep the
latest eight plus harvests under 24 hours old as of the latest harvest. Keep the
snapshot between harvests.

## Luna work packets

1. Implement the shared recent-render store and Candidate Board harvest interface.
   Verify deduplication, retention, persistence, and concurrent writers.
2. Connect Character and Minor Character after board commits. Verify view and
   costume links and failed-upscale handling.
3. Connect Narrative after target commits. Verify subscene, backdrop, assembly,
   and retry behavior.
4. Connect Image Generation after child commit using its trusted board reservation.
   Verify per-child success and exclusion of standalone work.
5. Connect the dashboard header, snapshot stream, and page. Verify idle updates,
   universe isolation, responsive placement, and history. Run the fast E2E baseline.

Packets 2 through 5 depend on packet 1. Final browser validation uses all producers.
The dashboard uses server-sent events because the declared Uvicorn installation
does not require a WebSocket protocol package. The stream waits for harvests.

## Progress and decisions

All five packets are implemented. The shared snapshot lives under workflow state
in `RecentRenders/<universe>/renders.json`. New installations start recording on
the first successful harvest. The dashboard opens a server-sent event stream
scoped to its selected universe. The CLI caps graceful shutdown at 30 seconds so
an open stream cannot hold it indefinitely.

The existing template-upload test could read the fixture before the successful
upload restored it. Its polling assertion now treats a missing file as pending.

## Observed validation

- Disposable store checks passed for the eight-image floor, the exclusive
  24-hour cutoff, duplicate events, concurrent writers, persistence, and universe
  isolation.
- Disposable browser checks using the prepared Character and Narrative scenarios
  passed for background arrivals, board counts, narrow layout, links, Back,
  reload, and switching to an empty universe.
- Disposable service checks passed for separate Minor Character views, a failed
  upscale preserving the previous image, and Image Generation child completion,
  receipt replay, retry, standalone exclusion, and an existing board reservation.
- `npm.cmd run test:e2e` passed all four approved scenarios (44.2 seconds).
- Python syntax, JavaScript syntax, and `git diff --check` passed.
