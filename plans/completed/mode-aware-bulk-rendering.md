# Mode-aware bulk rendering and batch status
Status: complete

## Goal
Provide mode-aware bulk rendering and independent Draft/Final batch status for all five local character pipelines, using the saved candidate counts and requiring Final pipeline references for Final renders.

## Implementation packets
- WP1: Replace shared-stage readiness with per-mode prerequisite checks. Preserve Draft fallback and frozen retries; require Final selections and locks for newly prepared Final pipeline inputs. Validate with isolated service checks. Status: complete.
- WP2: Add a run-available action that reuses pending placeholders, fills candidate deficits, fences duplicate requests, and uses the durable slot collector. Validate queue ownership and restart recovery. Depends on WP1. Status: complete.
- WP3: Project per-mode status, counts, eligibility, and blockers for details and lightweight summaries. Validate active slot work and independent completion. Depends on WP1–WP2. Status: complete.
- WP4: Connect Run front and Run available, mode-specific progress, and mode-labelled actionable batch links. Validate with isolated browser journeys. Depends on WP2–WP3. Status: complete.
- WP5: Update affected knowledge and ADR, run the approved fast suite, syntax checks, and diff review, record results, and archive this plan. Depends on WP1–WP4. Status: complete.

## Constraints
Human selection and locking remain explicit. Existing images, historical submissions, and unrelated pipelines remain untouched. No permanent tests or live AI calls without separate approval.

## Progress
Inspection identified shared Draft-oriented stage projection, separate mode slots and selections, and an independent slot collector. Both reported batches have a Final FRONT selection and empty Final non-front slots. Implementation and validation remain outstanding.

Further inspection: Assembly applies the legacy stage guard again in `queue_render_candidate` and `prepare_candidate`, after slot input preparation. Mode-aware eligibility must be applied consistently at both points; otherwise slots can appear runnable but fail when collected. Assembly and Dressing source resolution can select an explicit source batch as well as a lock, so enforcing Final source policy must account for both paths. No application changes have been retained until these paths can be changed together.

Partial WP3/WP4: `local_mode_progress_service.py` projects separate detail-page image and selection counts and basic statuses; the pipeline summary uses this projection on initial render and polling. This does not yet project readiness, lock counts, or summary-list status and does not complete either packet. Disposable checks cover independent completion and active slot IDs; existing fast-suite results must be recorded after completion.

Further implementation adds mode-specific prerequisite checks, strict Final
source gates, the `run-available` slot action, mode-labelled batch entries, and
mode-aware detail/picker controls. The four approved fast E2E scenarios passed
(`npm.cmd run test:e2e`, 41.6s). Disposable checks passed an isolated Assembly
FRONT endpoint submission and duplicate request, Final/Draft status separation,
four pipeline predecessor guards, and a Final-versus-Draft upstream source gate.
These checks do not establish end-to-end generation across all five pipelines.

Slot-only work now uses a persisted pause marker; submitted proxy work remains
non-preemptive, and its results are collected after resume. Startup recovery
respects the pause marker and reattaches unpaused slot work even when the shared
Draft status is Complete. Disposable isolated checks passed pause/resume via
the API and browser, configured candidate counts, duplicate submissions, FRONT
dispatch in all five pipelines, Body Final's eligible view set, Head-Image Edit's
seven Final views, Final source fencing, separate mode badges and deep links, and
real server restart with an existing ask. The first restart probe contacted an
already occupied port and produced a 404; using an available port passed. The
approved fast suite passed all four scenarios (42.0s); syntax and diff checks
passed. A Final-only rear-reference selection check passed. No permanent scenarios,
production renders, or new dependencies were added. Live image quality remains
unverified.
