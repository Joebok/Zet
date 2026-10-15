# 0012 — Universe style and text-only reconstruction
Status: accepted
Date: 2026-10-14

## Context

Moonsea's assembled characters have different rendering treatments. Tsaeytte must remain bootstrapped from authored text, while outside images need a way to retain visible design without carrying their original art style into generation. Joe approved implementation in the existing pages and image-batch review without prompt approval gates.

## Decision

Keep `canonical_art_style` as the shared artistic-rule source. A focused style reader returns text, source and a content fingerprint; compilation retains editable source attribution. Narrative adds an explicit `use_universe_style` scene choice: true on new scenes, false when absent on legacy scenes, with existing target style overrides taking precedence. Jobs retain the effective style in their frozen context/provenance. Rendering does not rewrite saved prompts after settings change.

Reconstruction is a universe-owned image-to-text-to-image job. The selected Codex/Ollama vision model sees an immutable source snapshot and extracts visible content independently of art style. Successful analysis automatically submits Qwen text-to-image work, reserving existing Image Generation slots first. The source pixels never enter the render reference list. Source identity/hash, model, extracted content, destination style and final prompt remain traceable through replay and import.

## Rationale and tradeoffs

Text reconstruction gives the destination style room to govern rendering but cannot guarantee exact identity or hidden details. Optional description/prompt editing remains available; it does not gate the initial batch. Existing character source chains and review mechanisms remain intact. Prompt direction must be judged against rendered batches rather than fixture results.

Interrupted analysis is reported as failed rather than automatically repeated. The persisted render ID and slot reservations prevent status polling from producing duplicate batches; changed reservations reject a late handoff. Failed rendering retains ordinary retry behavior.

## Related code and validation

See [style service](../../zet/services/universe_style_service.py), [reconstruction service](../../zet/services/image_reconstruction_service.py), [Narrative](../COMPONENTS/NARRATIVE.md), [prompt contracts](../COMPONENTS/PROMPTS.md), and the [active implementation plan](../../plans/active/style-unification.md). S1–S3 protect existing workflows; disposable prepared-response/browser checks exercise the new contracts. Live batch quality remains a separate acceptance checkpoint.
