# Restoration Notes

This archive is reference material, not a supported runtime switch.

A future restoration requires a separately designed migration that reintroduces configuration, pipeline definitions, workers, proxy handling, web APIs, and tests as active code. Do not import files directly from this directory and do not remove the reserved asset IDs from active phase manifests.

Use the archived source, tests, documents, `legacy_config.json`, phase `RetiredAssets.json` files, and retirement backups to reconstruct behavior. Restore into normal package paths only after adapting the archived contracts to the then-current `Assets.json`, prompt compiler, worker, and dashboard APIs.
