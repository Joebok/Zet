# Backdrop linking and independent cropping
Status: complete

## Goal
Implement the approved link → mode → optional crop → operation flow. No dependencies, permanent tests, live calls or delegation.

## Work packets
- WP1: Narrative model/repository/scene/reference service: persist modes and legacy defaults; explicit seed actions. Dependency: none. Validate disposable service checks.
- WP2: Reference service: integer pixel crops shared by preview/local/render preparation. Dependency: WP1. Validate known pixel regions.
- WP3: Narrative generation/prompt/proxy: effective source binding, frozen retries and stale response fencing. Dependency: WP1–2. Validate prepared requests.
- WP4: Narrative controller: conditional linking modes, authoring controls and actions. Dependency: WP1–3. Validate isolated browser.
- WP5: Narrative controller/CSS: independent numeric and pointer crop controls. Dependency: WP2/4. Validate browser and syntax.
- WP6: Approved E2E, disposable checks, affected documentation and final diff. Dependency: all.

## Constraints
Preserve existing proxy edit, ordered references, immutable job snapshots, universe isolation and locked images. Imported subscenes unchanged. Crop output uses native pixels; generation dimensions are independent.

## Documentation owners
Narrative, Data Model, Invariants, Dashboard UI and Code Map.

## Validation
Pending. Run npm.cmd run test:e2e, node syntax, Python compile and git diff --check. No live AI or normal library writes.

## Final results
WP1�WP6 complete. Added explicit linking modes, read-compatible legacy normalization, independent integer crop rectangles, shared exact crop bytes, mode-aware prompt/reference/proxy behavior, frozen retries and stale review protection. Source controls precede authoring; irrelevant controls are hidden. Source-copy visual overrides remain explicit. Preserved the pre-existing proxy transparency correction.

Validation: npm.cmd run test:e2e passed four scenarios twice (40.0s, final 41.9s). One intermediate invocation was blocked by the disposable fixture still occupying port 8765; stopped that verified fixture and reran successfully. JavaScript syntax, Python AST/import checks and git diff --check passed. Disposable service/browser checks in ignored test-results/backdrop passed known crop pixels, dimension independence, invalid modes, legacy conversion, conditional controls, local crop candidates, input copying, pointer movement, prepared reference dimensions, regenerate isolation, stale-mode comparison and frozen retry bytes after crop changes. Desktop and narrow screenshots inspected; no browser page errors. No permanent tests, live services, production-library writes or new dependencies.

Updated Narrative, Data Model, Invariants, Dashboard UI and Code Map. Generated image quality remains unverified without live inference. Numeric crop editing and lower-right resize complement pointer movement; existing render prompt text remains user controlled.
