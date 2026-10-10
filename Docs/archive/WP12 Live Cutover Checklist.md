# WP12 live cutover checklist

Live conversion is not authorized by WP12. Run this checklist only after explicit approval, and replace each placeholder with an absolute path on the cutover host.

1. Stop Zet and all queue workers. Record the maintenance-window start and confirm no render, candidate approval, or catalog edit is active.
2. Create a dated backup outside the authored library: `robocopy <library-root> <backup-root> /MIR /COPY:DAT /DCOPY:DAT /R:2 /W:2`. Record `<backup-root>` in the validation report.
3. Rehearse against a second copy whose `config.toml` points only to copied library, pipeline, asset, character, and queue roots.
4. Run the write-free catalog preflight: `.venv\Scripts\python.exe -m zet.scripts.migrate_image_catalog --config <copied-config.toml> --dry-run`.
5. Run the copied-library migration: `.venv\Scripts\python.exe -m zet.scripts.migrate_image_catalog --config <copied-config.toml>`.
6. Rebuild a disposable index outside the copied library: `.venv\Scripts\python.exe -m zet.scripts.rebuild_library_index --config <copied-config.toml> --index-root <machine-local-index-root>`.
7. Attach `Docs/WP12 Scale Report.json` and verify entity counts, references, prompt hashes, raw overrides, image hashes, all eight First Day scene/task associations, latency limits, page bounds, and zero archive traversals.
8. After approval, repeat steps 4–6 with the live config. Do not copy the SQLite database between machines.
9. Start Zet, verify index freshness, and smoke-test read-only navigation and review lists. Do not submit renders or approve candidates as part of cutover validation.
10. Restore on failure: stop Zet and workers; move the failed library aside; restore `<backup-root>` to `<library-root>` with `robocopy <backup-root> <library-root> /MIR /COPY:DAT /DCOPY:DAT /R:2 /W:2`; delete only the exact machine-local SQLite file reported by the rebuild command; start Zet on the restored config and rebuild the disposable index.

The catalog migration’s own pre-v3 backup is `<library-root>\ImageCatalog\_backup\ImageCatalog.pre-v3.json`; it supplements but does not replace the full-library backup.
