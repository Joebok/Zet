# Symbolic Image Inventory
Status: complete

1. Catalog binding and reads. Add one stable alias per owner slot; validate resolution and selective backup.
2. Character, Minor Character and Identity Keys. Connect locks, unlocks and confirmed removal; validate on disposable data.
3. Narrative. Connect locked artwork and lettering, removal and Inventory navigation; validate with the approved fast suite.
4. Reconcile Moonsea. Preview ownership, references and moves; apply only the reviewed manifest offline, then verify and record results.

The entity catalog owns the alias, while workflow records own the locked output. Follow the Library, Local Characters and Narrative component docs and update their contracts after validation.

## Validation and rollout
- Fast suite passed 4/4 after the initial lock integrations.
- Disposable catalog checks passed for stable IDs, identical labels, unlock, rollback,
  orphan reconciliation and selective backup.
- Moonsea read-only preview: 76 bindings, 428 existing orphan files, 52 orphan entries
  with recorded references and zero Minor Character Draft unlocks. Both reported
  Tsaeytte duplicates appear in the move list. 
- Final fast suite passed 4/4 (42.1 seconds). An intervening run timed out
  waiting for the seeded costume row. A clean rerun passed that scenario.
- Disposable Narrative check passed for confirmed lettering, Inventory lookup,
  confirmation and binding removal on target deletion.
- Moonsea was unchanged during preview. Existing current publications can retain their
  verified managed file as the lock's backing image during cutover.

## Moonsea cutover
- Joe approved the manifest. Stopped the production dashboard and harvester,
  then applied the exact approved preview offline.
- Applied 76 bindings and moved all 428 approved files. Verified each destination
  checksum, both stale Tsaeytte IDs, and the single active Woodland Front binding.
  SQLite integrity passed. The second preview reported no pending work.
- Catalog and affected records are backed up under
  Moonsea/backups/inventory-reconciliation-20261108-033140-409854.
- Production remains stopped. Its installed release supports catalog v4 and
  needs a compatible build before it can open the migrated v5 catalog.
