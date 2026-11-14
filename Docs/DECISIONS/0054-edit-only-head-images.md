# 0054 - Head Image Edit is the sole head pipeline

Status: accepted

Head Image Edit covers text-only FRONT generation, reference-based editing, phase changes, and all eight views. It owns head and hair authoring through the HEAD_EDIT sections.

Character Assembly resolves matching published Body Reference and Edit views automatically. A cross-phase Edit source saves the phase and uses its published Edit FRONT. Construct records retain their original identities and are excluded from active pipeline choices. This supersedes the parallel workflows and source selection in ADR 0028.
