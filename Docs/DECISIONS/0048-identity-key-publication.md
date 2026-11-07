# 0048 — Identity Key Inventory publication

Status: accepted  
Date: 2026-11-06

## Context

Identity Keys are editable crops with a saved ID in a character phase. A consumer that uses the published image needs a stable binding across label and crop changes.

## Decision

The catalog owns publication state. One asset ID and logical reference belong to each published character, phase and key ID. Unlock archives the item and deactivates its references. Relock restores the same item and its Identity Key reference.

A locked edit writes a fresh crop and Inventory blob before switching the catalog item to those bytes. A receipt in that catalog transaction tells Identity Key readers which JSON crop revision committed. Previous bytes remain available to readers that already resolved the previous revision.

Publication stores the crop's saved source identity and hash. When the source has an Inventory item, provenance links that item directly. Saved crops can be published after their upstream selection changes.
