# 0050 Minor Character asset collections

Status: accepted locally

A named Minor Character collection owns six assets. Style Alignment consumes
one original image and the universe canonical style. Views use the current
locked Style image for new requests. Each asset uses the shared board
policies, render transport, and Inventory lock transaction. Interview and
Write Prompt remain separate authoring actions. A candidate attached to an
interview is evidence for field suggestions.

## Offline conversion

Generate the read-only manifest for the universe root with
`python3 -B -m zet.scripts.migrate_minor_character_collections <universe-root>`.
Review Final locks, source issues, alias deactivations, and blockers. Resolve
blockers and regenerate the manifest before approval. Save the approved
JSON, stop dashboard and library writers, then pass that exact manifest with
`--apply-reviewed <manifest> --writers-stopped`. The command backs up the
catalog and affected records, retains each legacy session and its image
files, and adopts verified Final locks. It archives Draft-only symbolic links.
Resume an interrupted migration using the same manifest before starting
writers. Existing candidate history stays in the archive.
