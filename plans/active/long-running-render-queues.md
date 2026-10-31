# Long-running render queues and recovery
Status: active

## Goal
Preserve queued renders without a queue-age deadline, recover historical timeout failures, report proxy health and queue progress efficiently, and retain existing execution limits.

## Work packets
- WP1: Correct render collector and legacy wait paths; validate long waits and terminal errors.
- WP2: Recover current timeout-affected candidates with ownership and attempt fencing; validate idempotence.
- WP3: Publish proxy heartbeat and distinguish an active guard from a blocked backend; validate existing proxy scenarios.
- WP4: Reduce image reconciliation to 30-second intervals without slowing text work; validate concurrency and polling.
- WP5: Display queue state and proxy health on shared pipeline pages; validate prepared browser scenarios.
- WP6: Run approved suites, update affected documentation, and reconcile the reported batch after deployment is separately authorized.

## Constraints
Do not deploy, restart the proxy, submit renders, add permanent tests, or alter existing execution deadlines. Preserve queue ownership and candidate fencing. Historical front-right jobs were queued and left-profile images harvested at inspection on 2026-10-31.

## Progress
- Queue-age failure checks removed from the shared slot collector and three legacy render waits. Collection errors retain pending slots; the slot collector sleeps 30 seconds between passes.
- Added startup/periodic discovery and identity-fenced timeout recovery. Isolated checks covered queued and retained answers, harvested images, missing evidence, repeated recovery, cancellation, detached slots, deletion and replacement attempts. Cross-process crash/race behavior remains bounded by existing locks and was not separately stress-tested.
- Added AI_Proxy execution heartbeat and Zet health/queue projection. Three existing proxy scenarios passed; disposable checks covered heartbeat transitions and stale status. Prepared Chromium checks covered queue labels and hidden/visible polling. Queue position is unavailable from the existing cached projection and is omitted.
- Image-generation coordinator status polling is deduplicated per request at 30 seconds; slot submission wakes its collector immediately within the same process. Existing text sweeps retain their cadence.
- Approved Zet E2E passed (four scenarios, 43.2 seconds); Python/JavaScript syntax and diff checks passed. No production deployment, repair or submission has been performed. The code map was updated while preserving its existing non-UTF-8 bytes.
- Outstanding: after separately authorized coordinated Zet and AI_Proxy updates, reconcile the affected batch and record actual per-candidate outcomes. Until then the deployed release still shows the old failure labels.
