# Per-universe Species catalog

Status: complete

- WP1. Added the Species seed and universe-scoped service with atomic, revision-checked edits. Disposable API checks passed for starter definitions, two-universe isolation, stale saves, name collisions, and rename aliases.
- WP2. Body Reference now resolves species and source provenance from one catalog read. Disposable checks compiled all 14 starter definitions for FRONT, verified Elf guidance for a three-quarter view, and checked custom rules and source provenance. A completed candidate was selected and locked after catalog changes with its saved prompt intact.
- WP3. Character Wizard proposes a constrained Species ID. Draft review and Manual Setup use catalog choices. A stubbed interview replay rejected the Luna-RZ prose value, and the corrected draft compiled.
- WP4. Universe Settings supports adding and editing Species. Disposable Playwright passed add, rename, Wizard picker review, and publication to Character.md.
- Updated the component docs, data model, code map, and ADR 0053.

Validation: all four approved fast scenarios passed with `npm run test:e2e`.
JavaScript syntax checks and `git diff --check` passed. Model replies were
stubbed for the Species checks. The original tester run and live rendering
were outside the disposable validation.
