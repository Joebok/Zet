# Final assembly opacity
Status: complete

## Goal and constraints
Add saved group opacity to raw composition, placement preview and reference prompt guidance with legacy default 1. Preserve historical snapshots, source bytes and ordering. Reference guidance is approximate; no live rendering or permanent tests.

## Work packets
- WP1 — Repository and assembly service normalization, validation and alpha composition. Complete. Disposable checks verified defaults, rejection of invalid values, alpha multiplication and zero-opacity masks.
- WP2 — Narrative placement controls and preview. Complete. Existing S3 exercised the assembly dashboard; dedicated opacity browser interaction was not separately verified.
- WP3 — Frozen reference metadata and prompt guidance. Complete. Disposable checks verified half-opacity and zero-opacity prompt guidance. Reference bindings retain existing source copies and ordering.
- WP4 — Narrative/data documentation and validation. Complete. `npm run test:e2e`: four passed; `node --check zet/web/static/narrative.js`, Python compilation and `git diff --check` passed. Live rendering and artistic compliance were not tested.

## Results
Group opacity persists and defaults to 1. Composites multiply extracted alpha; reference-mode prompts request approximate transparency. Existing nested snapshots are not normalized or rewritten.
