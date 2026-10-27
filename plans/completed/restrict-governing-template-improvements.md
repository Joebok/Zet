# Restrict governing-template improvements
Status: complete

## Goal and current behavior
Limit offered edits to Character.md for Body/Head/Head-Image Edit and Character.md plus the selected costume for Dressing. Assembly remains unavailable. LocalTemplateRevisionService currently offers project instructions and global sections too; local_template_improvement.js exposes every source. Preserve frozen compilation context and historical records.

## Impact and constraints
The revision service owns authorization; the dashboard consumes an additive editable_source_ids response field. No persisted schema migration, production-library writes during validation, new dependencies or permanent tests. Preserve Head-Image Edit section restrictions, baseline fencing and explicit promotion. Affected knowledge: local-character workflow, prompts and data-model documentation.

## Luna-sized work packets
### WP1 — Backend source ownership
- Dependencies: none. File: zet/services/local_template_revision_service.py.
- Separate editable IDs from compilation snapshots. Restrict requests, model edits, decisions, acceptance and promotion; preserve historical context.
- Acceptance: only current character/selected costume edits can be introduced or promoted.
- Validation: disposable isolated service checks and Python syntax.
- Status: complete.

### WP2 — Dashboard controls
- Dependencies: WP1. File: zet/web/static/local_template_improvement.js.
- Restrict source choices, selectable findings, editors and promotion previews; retain read-only historical diffs.
- Acceptance: every update control targets an allowed source.
- Validation: disposable prepared-response browser check and node --check.
- Status: complete.

### WP3 — Validation and documentation
- Dependencies: WP1/WP2. Files: affected Docs component/data-model owners and this plan.
- Run isolated service/browser checks, npm.cmd run test:e2e and git diff --check. Update affected knowledge and archive completed plan.
- Acceptance: approved baseline passes without new maintained scenarios or live AI calls.
- Status: complete.

## Progress and results
Repository initially clean. Backend and dashboard restrictions implemented; affected local-character, prompt and data-model documentation synchronized. No code-map responsibility moved and no durable design change required an ADR.

Removed the proposal-time Body task-template wording migration: automatically rewriting a read-only project source would violate the approved source restriction. Existing frozen project wording remains unchanged. Accepted historical children retain frozen compilation context, while child source_ids are narrowed to allowed governing sources. Historical project-only diffs cannot be promoted; mixed revisions promote governing changes only.

Disposable service checks use temporary character/costume/project sources and prepared compilation, without live inference. They passed all four editable pipelines plus Assembly rejection; explicit project requests/manual replacements; both costume targets; Head-Image Edit section ownership; current allowed model findings; legacy decisions/acceptance; legacy project overlay preservation in children; mixed and project-only promotion; and rejection of forbidden answers through both worker versions. An initial disposable harness run lacked a mocked storage-health error hook; corrected the harness and reran successfully.

Disposable Chromium checks passed all four pipelines' choices/edit controls, historical read-only context, exact promotion confirmation targets, allowed correction submission, exclusion of legacy saved project selections, Assembly hiding and absence of page errors. An initial check asserted before asynchronous refresh completed; added a readiness wait and reran successfully. Evidence scripts remain ignored under test-results/check_governing_source_policy.py and .mjs; no permanent scenarios were added.

Observed validation: npm.cmd run test:e2e passed all four approved scenarios initially (41.3s) and after accepted-child source_ids narrowing (40.9s). Python AST parsing, node --check zet/web/static/local_template_improvement.js and git diff --check passed. Final diff review found only the intended service/UI, affected documentation and this plan.

## Final results
All three work packets complete. The panel and server authorize only canonical Character.md/selected costume edits, retain historical compilation context and prevent project master writes through promotion. No permanent tests, dependencies, normal-library data, submitted render inputs or live AI services were changed. Prepared checks establish software behavior; live image quality was not tested or required.
