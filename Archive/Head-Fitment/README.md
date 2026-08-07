# Retired Head-Fitment

Head-Fitment was retired in August 2026. Zet now assembles matching locked Body-Reference and Head-Image assets directly.

This directory is an inert restoration package. Files under `source/` and `tests/` are deliberately renamed or located outside active package and pytest discovery. They must not be imported, routed, or exposed through configuration without a separately approved restoration change.

The archive preserves both former implementations:

- the generative prompt runner, template, workers, and prompt contract;
- the masked-local edit, mask generation, inpaint render services, tests, and operating notes.

Active phase artifacts and asset records are archived separately under each character phase at `_archive/Head-Fitment/`. Their former asset IDs remain reserved in active `Assets.json` files.

`legacy_config.json` records the retired bundle and local-render preset. Historical per-view instructions remain recoverable from the retirement commit and the archived generated prompts.
