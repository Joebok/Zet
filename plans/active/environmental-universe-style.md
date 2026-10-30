# Environmental universe style
Status: active
Related issue/specification: User-approved implementation request, 2026-10-30.

## Goal
Add a separately editable environmental art style and allow explicit canonical/environmental selection wherever active workflows use universe style. New Narrative backdrops default to environmental; style choices are frozen into prepared jobs and character batches. Character Assembly remains image-driven.

## Implementation packets
1. **Universe setting and resolver** — extend descriptors/API and shared style snapshots. Acceptance: both fields round-trip; old calls remain canonical. Validate with temporary descriptors and Python syntax.
2. **Universe settings UI** — create/load/save/cache both values with dirty navigation protection. Validate a disposable browser journey and JS syntax.
3. **Narrative** — scene variant plus target inheritance/canonical/environmental choices, environmental new-backdrop default, prompt/provenance freezing. Validate service/browser contracts and approved Narrative regressions.
4. **Image Generation/reconstruction** — persisted selection, managed prompt insertion, frozen destination style in reconstruction lineage. Validate prepared-response checks.
5. **Minor Characters** — add independent universe variant alongside source-style mode; preserve fencing and candidate snapshots. Validate disposable lifecycle/browser checks.
6. **Character compilers** — freeze variant/text per Body Reference, Head Image, Head Image Edit, Costume Dressing batch; retain legacy canonical behavior. Validate both variants with disposable compiler checks.
7. **Pipeline UI/staging/reuse** — batch creation selector, display snapshots, preserve handoffs, fence overview reuse by style identity. Validate disposable API/browser checks and approved S2.
8. **Moonsea/docs/integration** — seed only a missing Moonsea setting; update owned documentation/ADR; run approved four E2E scenarios and final diff review; archive plan on completion.

## Constraints and decisions
- Descriptor field: `environmental_art_style`; selection field: `universe_style_variant` (`canonical` or `environmental`). Missing selection means canonical for legacy requests.
- Empty explicitly selected styles fail before AI submission; no fallback to the other style.
- Backdrops default environmental; other new work preserves existing defaults. Character pipeline selection is per batch.
- Do not add permanent tests/scenarios/dependencies or run live AI checks without separate approval. Keep universe data isolated and locked images unchanged.
- Moonsea receives the supplied style text only if its descriptor lacks the field; do not hard-code it into runtime defaults.

## Progress
- Planning complete; implementation not started.
