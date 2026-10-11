# 0004 — Maintain representative local task tests

Status: current explicitly documented policy; retrospective.
Record date: 2026-10-11. Source decisions were recovered with V5 history in `fda6aac`.

## Context

The initial knowledge-base audit saw the former broad Python/browser test suites. Recovered commits `b3d695a` (Testing Strategy Re-Alignment), `3f6acbe` (E2E simplification), and `257fdeb` (delivery gate) intentionally replace those suites and remove Actions test gates. Keeping old runnable-test links would misdirect future agents.

## Decision

Maintain exactly three fast local Playwright tasks: library/Narrative authoring, front Character-Assembly to Costume-Dressing, and Narrative jobs through final assembly. Keep one live final-assembly synthesis/render check separate and run it only when Joe requests it. New tests/scenarios or material expansion require explicit approval; repair existing scenarios to preserve their approved purpose. Scene/story validation uses Narrative, not retiring Scene Builder/local scene-batch workflows.

## Rationale

[AGENTS](../../AGENTS.md) explicitly describes Zet as a personal application on one machine and prefers a few representative tasks over extensive unit coverage. [Testing](../Testing.md) and the [delivery workflow](../../.github/CODEX_WORKFLOW.md) document the approved scope. This record reports that policy rather than inferring additional historical motives or measured coverage.

## Alternatives and tradeoffs

The former broad unit/browser suites and CI gates are the prior approach, intentionally retired in the cited commits. The chosen baseline reduces routine validation scope and uses prepared responses for speed/isolation. It leaves many concurrency, migration, protection and error contracts without dedicated checks; passing three tasks does not prove those contracts or model quality. Adding more tests automatically would violate the approved scope.

## Consequences

Use `npm run test:e2e` for current local delivery and explicit scenario-to-capability mappings. Do not restore deleted tests/CI as incidental cleanup. Plans must name uncovered acceptance criteria and keep live execution separate; skipped live checks are unverified. Test fixture endpoints and prepared response paths stay in the harness, not production routes. Historical audit results remain in Git/completed plans rather than being presented as current failures.

## Related code and documentation

[fast.spec.mjs](../../tests/e2e/fast.spec.mjs), [live.spec.mjs](../../tests/e2e/live.spec.mjs), [server.py](../../tests/e2e/server.py), [test seed](../../tests/library/README.md), [package scripts](../../package.json), [fast config](../../playwright.config.mjs), [live config](../../playwright.live.config.mjs), [development/results](../DEVELOPMENT.md), [code map](../CODE_MAP.md), [recovery plan](../../plans/completed/recover-v5-history.md), [plan convention](../../plans/README.md).
