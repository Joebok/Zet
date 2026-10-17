# 0017 — Durable image harvest admits dependent analysis

Status: accepted
Local character batch advice availability superseded by [ADR 0021](0021-file-based-local-image-availability.md).
Date: 2026-10-16

## Context

Concurrent dashboard and standalone collection exposed stale in-memory request
discovery, interrupted application commits and continuation replay. Independent
Codex execution can begin immediately after publication, before unrelated local
renders finish. File existence alone cannot establish successful application.

## Decision

Zet owns the dependency barrier: validate both execution outcomes, save image bytes
and domain state, then commit the receipt before publishing image advice. Recheck
current ownership and hashes under the domain lock at publication. Reserve stable
gate/Minor review identities so restart can resume without duplicating execution.
AI_Proxy retains its single local slot and independent two-slot Codex lane.

## Rationale and tradeoffs

This preserves generic proxy scheduling and makes dependencies independent of
queue order. It adds compact local receipts/checkpoints and refuses automatic
analysis when evidence is incomplete. Old receipts remain readable, but domain
hashes must still match; historical records are not automatically reconstructed.
Moving dependencies into a proxy-wide graph would duplicate Zet's ownership rules.

## Consequences and validation

Caller wait duration is not a queued job's execution deadline. Collection failures
retain payloads and diagnostics, separately from terminal execution failure.
Prepared two-process/crash/mixed-workload checks and the four existing fast
scenarios passed. This does not establish live provider behavior or deployment.

Owners: [AI jobs](../COMPONENTS/AI_JOBS.md),
[image admission](../../zet/services/image_harvest_service.py),
[common jobs](../../zet/services/ai_job_service.py).

Image availability and recurring verification are superseded by
[ADR 0023](0023-streamlined-image-integrity.md); ownership and job fences remain.
