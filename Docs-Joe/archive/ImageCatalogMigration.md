# Image catalog schema-v3 migration

Use the repository's verified Python 3 interpreter and the configuration for the library copy being migrated:

```powershell
.venv\Scripts\python.exe -m zet.scripts.migrate_image_catalog --config <path-to-config.toml> --dry-run
.venv\Scripts\python.exe -m zet.scripts.migrate_image_catalog --config <path-to-config.toml>
```

The dry run validates IDs, source keys, reference-set links, JSON structure, and every managed image location and hash without writing. The real run stages the complete representation under `ImageCatalog/.migration-v3`, checkpoints progress after every record, verifies staging, retains the legacy monolith at `ImageCatalog/_backup/ImageCatalog.pre-v3.json`, installs the record set, and switches `ImageCatalog/ImageCatalog.json` last. Re-running after success reports `no-op`. Re-running after interruption resumes from the durable staging checkpoints.

The resulting authored layout is:

```text
ImageCatalog/
  ImageCatalog.json                 # schema-v3 complete manifest; no item data
  Organization.json                 # schema-v1 collections and keywords
  Records/
    <catalog-id>.json               # source key, metadata overlay, managed-image data
  ReferenceSets/
    ref_<sha256-prefix>.json        # one record containing its reference_set_id
  Images/                            # existing managed image bytes; not rewritten
  Drafts/                            # existing AI drafts; unchanged
  _backup/
    ImageCatalog.pre-v3.json        # retained legacy monolith
    Records/                         # per-record backups created by later edits
    ReferenceSets/                   # per-reference-set backups created by later edits
    Organization/                    # organization-only backups
  .migration-v3/                    # resumable staged representation and progress
```

Library-owned managed images use POSIX-style paths relative to the library root and carry `image_path_kind: "library"`. References outside the library remain absolute and carry `image_path_kind: "external"`. Runtime readers accept only a complete schema-v3 manifest; legacy or incomplete storage returns the migration command as the recovery action.
