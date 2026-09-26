The plan:

# Luna-sized implementation packets: local character overview

## Summary

Implement the feature in the ordered packets below. Each packet has a narrow behavior change and its own relevant tests. Keep existing manual pipeline behavior available until the event-driven path is ready for all four pipelines.

## Work packets

1. **Deterministic FRONT resolver.** Add a service that reads verified locks and batch selections. Prefer a finished FRONT batch, then the newest rendered selected image; break remaining ties by batch creation time, run ID, and candidate ID. With no selection, choose the newest batch. Test ties, missing images, and stale records.

2. **Preserve Luna’s original #1.** Store the original ranking order separately from later manual reordering in all four pipelines. For older rankings where the original order cannot be established, rerank before autoselection. Test that a manual reorder does not change autogenerate’s choice.

3. **Autogenerate approval.** Add an internal approval record distinct from human Pass. Allow it to select only a current, gate-surviving #1 FRONT candidate; never override a human rejection. Reuse existing select and lock artifact handling. Test both allowed and rejected candidates.

4. **FRONT-only downstream batches.** Allow Character-Assembly and Costume-Dressing to create a batch with only locked FRONT inputs available. Keep the normal candidate manifest; snapshot other-view inputs if those views are started manually later. Test creation and later manual progression.

5. **Durable local work engine.** Add file-backed work state, an idempotent harvest tick, per-run locking, and a background tick loop. A tick stages eligible work or consumes completed answers, then returns without waiting for proxy jobs. Run ranking work in a separate bounded worker slot. Test duplicate ticks and restart recovery.

6. **Body-Reference events.** Adapt FRONT render, face gate, analyses, review gates, and ranking to the work engine. Remove the global runner bottleneck for this path. Test that each completed answer stages the next eligible step and that all failed candidates yield a specific error.

7. **Head-Image events.** Adapt its FRONT render, gates, and ranking. Reuse the optional reference saved in an existing batch; create a new batch without one. Test both reference cases and failed answers.

8. **Assembly and Dressing events.** Adapt both pipelines’ FRONT render, gates, and ranking to the same tick contract. Test source snapshots, per-costume isolation, and terminal ranking errors.

9. **Manual start cutover.** Change the four local pipeline start routes to enqueue work and return immediately. Their results continue through harvest ticks. Keep existing page status polling and manual review actions. Test the start, stop, and rank routes.

10. **Autogeneration coordinator.** Persist one active job per character, phase, and costume. On each tick, resolve Body-Reference → Head-Image → Character-Assembly → Costume-Dressing, locking each chosen FRONT image before advancing. Share active upstream work across costumes while allowing unrelated jobs to progress independently. Test reuse, concurrency, and a later manual lock taking precedence.

11. **Stop and failure handling.** Make Stop and errors terminal for an autogeneration attempt. Withdraw its queued tasks, ignore late answers, preserve completed artifacts, and leave shared or manual work active. Recover nonterminal jobs after restart. Test cancellation at each pipeline boundary and with two costumes sharing upstream work.

12. **Overview API and page.** Add `/local-character-overview`, an overview read endpoint, a validated locked-image endpoint, and start/status/stop endpoints. Render every character-phase row and its costume slots; poll for progress and later lock changes. Test placeholders, statuses, errors, image refresh, and endpoint idempotency.

13. **End-to-end acceptance.** Exercise an empty workspace through a locked Costume-Dressing FRONT image using stubbed proxy and Luna results. Repeat with existing locks, selected images, an unfinished latest Head-Image batch, all candidates rejected, simultaneous costumes, and Stop. Run the relevant existing local pipeline and web tests and review the final diff.

## Interface and selection rules

The overview endpoints expose slot state (`IDLE`, `RUNNING`, `COMPLETE`, `ERROR`, `CANCELLED`), current pipeline, message, job ID, and verified locked image hash. Starting an active slot returns its existing job. A new attempt starts its decisions at Body-Reference and may reuse preserved artifacts.

A “finished FRONT batch” has completed FRONT rendering, gates, and ranking; its other views need not be complete. When no selection exists, use the newest batch by creation time and run ID, render FRONT if needed, and select its original #1 ranking result. An existing single-survivor ranking counts as #1.


The difference is where the waiting happens.
Currently, clicking Autogenerate returns quickly, so the web page stays responsive. A background worker then runs a pipeline and waits for that pipeline’s proxy jobs to finish. It periodically checks for results; once the pipeline is done, it moves on to the next one. That worker remains occupied while it waits.
The planned harvest-tick design would work differently: a short background tick checks for completed proxy jobs, processes any answers it finds, and queues the next work. It then returns. Later ticks pick up more answers and advance more jobs. No worker needs to stay occupied just waiting.
For example, while a Body-Reference image is rendering, the current design has a worker waiting for that run. With harvest ticks, that worker would be free after queuing or checking the work, and a later tick would notice the render is ready and continue.
This matters mainly if many jobs are running: the current worker pool has a fixed number of slots, so enough long waits could delay other local pipeline tasks. The page remains asynchronous, and active jobs are recovered after restart, but recovery is at the coordinator level rather than through a durable, independently harvested task queue.