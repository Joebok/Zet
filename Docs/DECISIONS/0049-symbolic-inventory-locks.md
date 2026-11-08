# 0049 — Symbolic Inventory locks

Workflow records own locks and image bytes. The entity catalog enforces one
stable ID per owner slot and publishes a path to its current locked output.
An unlocked slot has no resolvable Inventory image. Candidate labels and image
checksums are metadata and do not determine identity. Saved references to
the symbolic ID follow the current lock. Existing frozen render inputs remain
bound to the paths and bytes submitted by their workflows.

Character boards, Minor Character views, Narrative targets and Identity Keys
publish through their lock actions. Minor Character views have one lock across
qualities. Narrative publishes confirmed lettering when available.

To preview reconciliation offline, run
`python3 -B -m zet.scripts.reconcile_inventory_locks <universe-root>` and save
the JSON output. Review moves, recorded references and lock changes. After
approval and stopping writers, pass that same manifest with
`--apply-reviewed <manifest> --writers-stopped`. The command checks for changes,
backs up the catalog and affected workflow records, and journals progress.
Resume an interruption with the same manifest before restarting writers.
Retired lock publications move to the universe's `OrphanedImages` folder.
