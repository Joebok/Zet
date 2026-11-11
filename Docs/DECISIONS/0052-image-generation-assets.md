# 0052 - Image Generation assets and candidate boards
Status: accepted
Date: 2026-11-11

## Decision

The universe library owns Image Generation assets, including editable settings and reference images. Each asset owns eight mixed-quality slots and one selection. Render jobs retain their independent request IDs, frozen inputs and child indices. The dashboard mounts the shared Candidate Board for the active asset.

Legacy boards migrate under the workspace lock. Migration merges Draft and Final when one board can preserve all candidates and the selection. Otherwise it creates two assets. Browser-input recovery explicitly creates a separate asset.

Inventory publication copies the candidate through the existing Inventory service without changing its selection. Reconstruction analysis saves a draft without reserving render capacity. A subsequent explicit render captures the operator's reviewed prompt.

## Consequences

Selecting a candidate changes which image represents its asset in the gallery. Publishing does not protect or lock a slot. Deleting a board leaves Inventory copies independent. Character staging and Inventory Modify create prefilled assets through the same library storage.
