# 0043 — Local character preparation operations

Date: 2026-11-01
Status: accepted for Run available, slot/view regeneration, Re-evaluate, batch Start/Resume and candidate-review retry.

Run available and slot/view regeneration accept a durable fixed-local operation before compiling prompts or
copying references. The batch reserves candidate identities and checkpoints
individual commits; the existing slot collector and AI_Proxy retain ownership of
render execution. An operation's handoff status does not claim image completion.

An operation ID deduplicates retries and supports status reconciliation after a
lost browser response. Input fingerprints and reservation checks fence changes,
while Stop holds the batch handoff lock through the stop or pause transition. Ambiguous outcomes retain
recovery-required status rather than silently creating another render.
The handoff fence is scoped to the universe and batch, so a slow handoff does
not hold the repository-wide admission lock for unrelated operations. A durable
batch Stop generation also invalidates a request formed before Stop but admitted
after it.

Candidate-review retry reserves its target and moves only that candidate's
generated output to an operation-owned directory. The candidate reset and
checkpoint commit in one batch-state write. A pre-commit Stop restores the old
output; a committed reset can be replayed without another destructive change.

See the [completed plan](../../plans/completed/character-pipeline-operations.md) for
the scope, disposable checks and validation limits.
