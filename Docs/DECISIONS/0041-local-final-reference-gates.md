# 0041 — Local Final reference gates

Date: 2026-10-31
Status: accepted

Local character Final render inputs use Final same-batch selections and locked
Final upstream pipeline images. Bulk generation queues currently eligible views
and pauses at missing human selections. Draft mode retains mode preference and
fallback. Explicit external images and previously frozen requests remain valid.

This keeps Final work independent from Draft completion while retaining the
existing queue ownership and immutable-input contracts. See
[Local Characters](../COMPONENTS/LOCAL_CHARACTERS.md#mode-aware-batch-rendering-2026-10-31).
