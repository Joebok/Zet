# 0045 — Current inputs for new asks, retained finished images
Status: accepted
Date: 2026-11-02

## Context
Character batches previously treated an accepted batch overlay and historical
source lineage as continuing requirements for generation and publication. This
made template editing and new image creation require extra activation steps, and
could block a finished image when its old source changed. The intended product
keeps strict queue transport and harvest placement, while allowing finished images
to stand on their captured prompt and inputs. See
[Pipeline Guards Reimagined](../../Docs-Joe/Pipeline%20Guards%20Reimagined.md).

## Decision
Accepting a reviewed template improvement saves the governing master as part of
the acceptance operation. A conflicting master edit prevents acceptance. Every new
character ask compiles current masters and resolves current eligible same-mode
references before freezing its prompt, ordered input bytes, identities and seed.
Queued asks and retries keep their frozen inputs. Explicit source-batch choices
remain in force; Final requires its current same-mode lock.

After harvest, selection and publication require ownership, slot membership,
available image bytes, lock protection, and atomic Inventory publication. They do
not require old references, template versions or selected image bytes to retain
their former hashes. A lock copies the exact generation prompt independently of
the batch slot. A saved source difference observed on an opened view may set a
permanent `source_change_fyi`; it is never an error or action gate. Bulk destructive
actions require explicit approval for each affected selection or lock against a
state-bound server preview.

Queue ownership, attempt fencing, universe isolation, ordered bindings and harvest
receipts remain strict. Narrative retains its authored prompt and source-layer
choices for new requests; its saved prompt-change FYI follows the same advisory
rule.

## Supersession
This decision supersedes the batch-overlay activation and historical-lineage
publication requirements in [ADR 0041](0041-local-final-reference-gates.md),
[ADR 0044](0044-character-batch-review-freshness.md), and older character component
sections where they conflict. Their transport and transaction rules still apply.
