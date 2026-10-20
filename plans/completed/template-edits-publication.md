# Publish accepted template edits from the update dialog
Status: complete — local implementation and isolated validation; production handoff not performed.
Related specification: Joe's approved plan, 2026-10-20.

## Goal and current behavior
Master promotion writes tracked global/character pipeline templates. The deployment
controller rejects every tracked production diff. Add explicit snapshot → isolated
branch/validated PR → operator merge → verified deployment, without changing live
templates, index, branch, library or rollback contents.

## Work packets
- WP1 — Complete. `template_publication_service` and stdlib
  `template_publication_core` own version-1 snapshots, allowlist/diffs, production
  root identity and stale-preview fencing. Acceptance: exact snapshot without live
  HEAD/index/template changes. Validation: disposable `check_service.py`.
- WP2 — Complete; depends WP1. Publication service owns fresh private attempts,
  three-way patch/commit, fixed-port E2E validation, no-force push, existing
  GitHubClient PR delivery and checkpoint retries. Acceptance: one branch/PR after
  an uncertain response; completed same-revision validation is reused. Validation:
  disposable Git/GitHub checks and existing baseline.
- WP3 — Complete; depends WP1/2. DeploymentService/controller consume merged
  receipts; core guards compare raw capture and normalized target blobs/ancestry.
  LocalTemplateRevisionService shares the final stop/start fence. Acceptance:
  changed/unrelated edits block before process stop, rollback preserves old bytes.
  Validation: disposable merge/rollback/copied-controller/cross-process checks.
- WP4 — Complete; depends WP1–3. Deployment routes, restart dialog, task attention,
  scoped task CSS and main-template cache versions expose preview/publish/refresh/
  retry. Acceptance: remote recovery from one dialog with retained state, unrelated
  blockers and mobile bounds. Validation: disposable route and Chromium checks.
- WP5 — Complete; depends all. Workflow/component, architecture/data/invariant,
  code-map/Testing documentation and ADR 0026 identify ownership, receipts and
  first-install handoff. Validation: syntax checks, existing E2E, final diff review.
  No new maintained tests or dependencies. Production handoff is separately gated.

## Constraints and acceptance
Only global sections and four active character templates are eligible. All other
tracked edits block. Existing old edits are supported. Publication requires an
explicit dashboard action; merge and deployment remain operator actions. Captured
and published contents may differ after clean three-way application onto main.
Reconciliation requires unchanged capture, merged PR and exact published target.
No production deployment or actual external writes are authorized for validation.
First installation requires separately authorized preservation/merge/reconciliation
because the installed old controller cannot consume new receipts.

## Progress and decisions
- A receipt applies only to its original source root/revision; subsequent releases
  ignore it. A new snapshot archives old receipts rather than discarding them.
- Before a commit checkpoint, retry creates a fresh private attempt and retains
  the interrupted/conflicted attempt. After that checkpoint it verifies HEAD and
  tracked cleanliness and reuses successful validation for that exact commit.
- Private checkouts disable autocrlf, preserve the baseline's Git newline form and
  normalize captured Windows checkout text for LF blobs. CR-at-EOL is permitted
  during committed-diff whitespace checks; raw source hashes remain strict.
- Empty PR diffs remain explicit conservative blockers; already-ready identical
  snapshots return the existing receipt instead of replacing it with an empty PR.
- No live credentials, external writes, production cleanup or deployment used.

## Validation and final results
- `npm.cmd run test:e2e`: four approved scenarios passed in 51.2s and 47.9s. Final
  run had a nonfatal fixture Windows sharing warning; scenario/runner exit passed.
- Ignored `test-results/template-publication/check_service.py`: disposable Git
  snapshots, three-way application/conflicts, uncertain delivery/retry, checkpoint
  reuse, merge proofs, stale content, receipt lifecycle, pre-stop and rollback.
- `check_routes.py`: actual extracted route definitions in a disposable FastAPI
  app; body/status/error handling, standalone copied helper and OS process lock.
- `check_browser.cjs`: prepared-source UI at 1280/800/390px. `check_mounted.cjs`:
  actual mounted dashboard at 1280/390px with prepared deployment responses; actual
  development-fixture APIs reject publication. Screenshots inspected.
- Python AST, JavaScript syntax and final `git diff --check`: passed.
- Source checks found/fixed pre-checkout state checking, mobile width, CRLF
  handling and obsolete receipt interference. Disposable harness URL/checkbox
  assumptions were corrected before passing checks.
- External GitHub delivery, physical iPad acceptance and production handoff remain
  unverified rollout actions, not completed deployment claims.
