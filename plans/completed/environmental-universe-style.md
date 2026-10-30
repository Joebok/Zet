# Environmental universe style
Status: complete
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
- WP1-WP8 implemented. Moonsea initialized only because environmental_art_style was absent.
- Follow-up: existing targets with missing/empty choices explicitly normalize to canonical; inheritance uses the distinct value `inherit`. This fixes the reported existing-subscene load failure without rewriting saved records.
- Character batch snapshots use batch-owned Universe_Style.json, read by compiler adapters from declared output directories. Stage handoffs retain snapshot metadata and prompts.
- Documentation updated in component/data/code-map owners and ADR environmental-universe-style.md.

## Final validation
- Four approved E2E scenarios passed on disposable port 8875: 37.6 seconds and final compatibility rerun 41.3 seconds. Standard npm command could not bind port 8765 because the existing open-library inspection server owns it; that server was preserved.
- Final rerun emitted a Windows connection-reset warning while all four scenarios passed.
- Disposable service checks passed: reported Moonsea target loads with canonical; empty variant defaults canonical; frozen environmental batch snapshot survives changed descriptor text; source pointer remains /environmental_art_style.
- Changed Python AST checks, JavaScript syntax checks and git diff --check passed. Final provenance/staging additions received syntax/diff inspection after the E2E rerun.
- No new permanent tests/scenarios/dependencies or live AI requests. Full browser journeys for every new selector and live image quality remain unverified. Local implementation requires the serving runtime to load this revision before the remote dashboard reflects it.
