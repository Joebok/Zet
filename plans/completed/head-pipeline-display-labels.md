# Head pipeline display labels
Status: complete

## Goal
Display Head-Image (Construct) and Head-Image (Edit), with Edit between Body-Reference and Construct in Assets, while preserving pipeline identifiers, storage and defaults.

## Completed work packets
- WP1: page-contract and batch labels share the local pipeline configuration. Machine-readable keys remain unchanged.
- WP2: Assets and compact navigation, headings, source selectors and summaries use the new labels; selector values and defaults are unchanged.
- WP3: browser display mapping covers assets, pipeline controls, comparison, Overview, queue workflows and human-readable historic status messages. Paths, raw identifiers and authored content remain unchanged. User-facing source and validation errors use pipeline-specific labels.
- WP4: Dashboard UI documentation updated and final diff reviewed.

## Validation
- `npm.cmd run test:e2e`: four approved scenarios passed (45.2s); the earlier launch was blocked by the disposable check server occupying port 8765 and succeeded after that server stopped.
- Disposable Chromium checks at widths 1400 and 390 verified menu order, both headings, source values/default and message mapping. Prepared queue responses verified both old workflow values, unrelated workflow passthrough, historical messages and unchanged submitted filter value.
- JavaScript syntax checks, Python AST checks, label assertions and `git diff --check` passed. Tests used isolated fixtures and no live model calls. No permanent tests were added.

Follow-up: Joe clarified the intended Assets order: Body-Reference, Head-Image (Edit), Head-Image (Construct). Desktop and compact navigation were updated accordingly.
