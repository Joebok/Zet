# Refresh knowledge after V5 history recovery
Status: complete
Related specification: user's request to update recent-commit documentation, especially E2E testing.

## Goal
Make the knowledge base reflect recovered testing and Kanban commits without changing application code, tests, dependencies, or test policy.

## Current behavior
`fda6aac` restores V5 history, including `b3d695a` (test strategy), `3f6acbe` (three-scenario simplification), and `257fdeb` (local delivery gate). AGENTS and Testing already identify the local baseline, but component/invariant/ADR links and the code map still name deleted Python/browser tests. Earlier audit results remain historical evidence in completed plans.

## Desired behavior
Agents find exact approved scenarios, commands, fixtures, preparation boundaries, current coverage gaps and live-check prerequisites. No deleted test file is presented as a runnable check. Recent Kanban configuration/forwarding is reachable from architecture/data navigation.

## Impact analysis
Documentation owners: Testing, Development, Index, Code Map, Invariants, component verification sections, relevant retrospective ADR citations, Architecture, Data Model and plans convention. Original completed plans remain intact. Add a retrospective testing-policy ADR because this is a significant durable decision explicitly documented in the recovered commits.

## Invariants and constraints
Single agent; no new/expanded tests, live model runs, installation, external writes, code fixes, or historical plan rewrites. Preserve existing operating/testing approval rules. A prepared answer is not evidence of live service or exhaustive contract coverage.

## Implementation steps
### WP1 — Verify recent commit evidence
- Dependencies: none.
- Files/interfaces: recovered commits, package scripts, Playwright configs, existing fast/live specs and fixture server, task forwarding source.
- Acceptance: distinguish intended policy, actual fixture behavior, and observed validation.
- Validation: targeted source/history reads.
- Status: complete.

### WP2 — Update affected knowledge
- Dependencies: WP1.
- Files/interfaces: affected Markdown owners named above.
- Acceptance: three scenario mappings; accurate reset/isolation/response boundaries; no deleted-test links or instructions to add coverage without approval; source-backed Kanban navigation.
- Validation: local references and manual consistency review.
- Status: complete.

### WP3 — Verify and archive
- Dependencies: WP2.
- Files/interfaces: existing fast E2E baseline, updated Markdown, this plan.
- Acceptance: existing baseline status reported, docs-only diff, links resolve, plan archived with results.
- Validation: `npm.cmd run test:e2e`; reference/scope checks; `git diff --check`.
- Status: complete.

## Risks and alternatives
Scenario-level coverage is deliberately narrow; avoid replacing retired test links with blanket coverage claims. Existing design notes and completed audit plans are historical and should not be rewritten as current results. Fast tests reset selected workflow state in a shared per-run Test universe rather than rebuilding every catalog per scenario.

## Progress and decisions
Repository initially clean at `676e048`. Python 3.14.6 and Node v24.18.1 available; approved fast baseline invoked without installation or live execution. Source inspection confirmed three fast scenarios, one guarded live scenario, and the changed delivery policy.

Updated Testing with exact scenario titles/assertions, mixed UI/API coverage, scoped reset behavior, seed ownership, fixed ports/timeouts, prepared response boundaries, retained artifacts and opt-in live prerequisites. Replaced deleted-test links across the code map, six components, invariant verification and retrospective ADR citations. Preserved original decision context and completed audit/recovery plans; historical results now point to their Git snapshot. Added current Kanban architecture/config navigation and a source-backed testing-policy ADR. Review also clarified that the shared gate parser and Assembly/Dressing parser accept different verdict syntax.

## Validation
- `npm.cmd run test:e2e`: the existing three scenarios passed. Playwright's `.last-run.json` reported `passed` with an empty `failedTests` list. No live check, installation, new scenario or test repair performed.
- Standard-library documentation checker: 26 Markdown files, 527 local links, two heading links and 108 linked Python symbols passed. Checked path casing, whitespace/final newlines, exact three fast-spec titles, historical Git references and documentation-only scope.
- `git diff --check`: passed. Final diff reviewed for unintended changes and claims of broader test coverage. Retiring Scene Builder/local scene-batch workflows and other uncovered capabilities are explicitly labeled.

## Final results
Refreshed 18 existing Markdown files and added ADR 0004 plus this completed plan. Current validation navigation uses the approved E2E scenarios instead of deleted Python/browser paths. Application code, test files, dependencies, configuration, operating instructions and original completed plans were preserved. The separately requested live check remains unverified. Documentation refresh completed and plan archived.
