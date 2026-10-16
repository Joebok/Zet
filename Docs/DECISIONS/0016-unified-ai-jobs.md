# 0016 — Unified AI execution and collection
Status: accepted
Date: 2026-10-16

## Context
Joe requested one AI Queue, provider-independent requesting/harvesting, immediate
cloud admission alongside local work, and a shared capability-aware model picker.
Inspection found direct Codex subprocesses, consumer-specific collection loops,
completion without receipts and a missing AI Queue activation loader.

## Decision
Zet owns frozen requests, durable continuation/application state and receipts.
AI_Proxy owns provider execution and trusted scheduling. Codex has an independent,
bounded cloud lane (default two); Ollama/ComfyUI retain one non-preemptive local
lane. Catalog metadata originates in AI_Proxy and is cached once by Zet.
See [shared jobs](../COMPONENTS/AI_JOBS.md) for primary interfaces and owners.

## Rationale and tradeoffs
Increasing priority cannot start cloud work while the local scheduler is awaiting
completion. Separate dispatch preserves local residency rules. Durable local
records/receipts prevent fast cleanup or index lag from hiding activity. Registered
resumable continuations avoid keeping a thread alive for every AI wait. Domain
application remains separate because interview proposals, image slots and immutable
locks have different invariants. Legacy worker registrations remain temporarily
available to settle already-published envelopes without rewriting them.

## Consequences
Both repositories must be upgraded together, proxy first. Ambiguous executions
are not replayed, application faults retain answers for explicit harvest retry,
and removed historical evidence is not invented. No production dependencies were
added. The newly approved isolated scenario in each repository checks the shared
boundary; live providers and deployment require separate authorization.
