# Locked draft review comparisons
Status: complete

## Goal
Show matching locked Draft snapshots in all character candidate reviews. Preserve existing defaults and user changes.

## Work packets
- WP1: Project available, scoped locks in the shared workflow response; validate isolation and missing files.
- WP2: Add comparison chooser to shared review, preserving navigation and polling; validate in browser.
- WP3: Add current-view lock to Minor Character carousel; validate snapshots.
- WP4: Update knowledge, run approved E2E and diff checks, record results and archive.

## Constraints
No permanent tests, new dependencies, live AI, or production data changes. Existing local ranking edits are unrelated and must be preserved.

## Progress and validation
Implementation and documentation completed. The four approved fast E2E scenarios passed (45.7s); JavaScript and Python syntax, scoped mock projection, and git diff --check passed. Disposable Chromium checks passed on all five pipeline controllers, view changes, unsaved decision retention, missing-image fallback and Minor Character review/STYLE. A real temporary-store check verified costume and view isolation, cross-batch locks, unlocked records and unavailable snapshots. Browser checks used prepared responses and instrumented controller access. Fixed unsaved decision loss found during the checks.
