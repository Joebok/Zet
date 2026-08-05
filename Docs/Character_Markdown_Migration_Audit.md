# Character Markdown Migration Audit

## Scope

This audit covers the canonical character contract, Tsaeytte Adult and Youth history, active costume and expression definitions, and live phase-level JSON references. Generated files under `Pipelines/` are historical provenance and were not rewritten.

## History findings

| Phase | Revisions reviewed | Recovery decision |
| --- | --- | --- |
| Adult | `b0b3b5b`, `8e6b65d`, `f90f7aa`, `214a0b7` | `f90f7aa` is the last character-rich revision and matches the recovered `Character.md`. The `214a0b7` section bodies match the shared placeholder template and were rejected as character content. |
| Youth | `b0b3b5b`, `8e6b65d`, `f90f7aa`, `9320bfd`, `6873e75` | The recovered `Character.md` matches the latest legacy file. The explicit `6873e75` scene-identity wording remains authoritative. |

## Applied contract

- Phase character files are named `Character.md`; `Character_Image_Template.md` is retired.
- Character files contain the complete shared marker set, including expression facts, eye preservation, stance/modesty variants, scene identity, and local image overrides.
- Character-specific prose is preserved from the latest explicit revision. Shared compiler rules supply newly introduced reusable sections.
- Costume files contain the complete `Costume_Template.md` marker set and matching character/phase metadata.
- Expression definitions use matching character/phase metadata, library-relative definition paths, and local image override markers.
- Adult `Identity.md` and the original expanded costume source were retained under `_archive` after their active facts were represented in canonical resources.

## Runtime migration

- Active code, onboarding, workers, compilers, story sourcing, source editing links, dashboard text, examples, docs, and tests use `Character.md`.
- Expression compilation obtains phase-wide expression rules from `Character.md` and costume preservation from the selected costume when present.
- Live `Assets.json` source paths use library-relative `Characters/...` paths.
- Existing generated prompts, source maps, render IR, and other pipeline artifacts retain their original paths as historical records.
