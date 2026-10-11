# 0003 — Local candidates are the active character production path

Status: current implemented policy; retrospective.
Record date: 2026-10-11. Historical retirement/policy decision dates are unknown.

## Context

Traditional numbered assets, configured pipeline stages, worker modules, Stable Matrix adapters, and older prompt profiles remain in the repository. Active local character workflows instead manage candidate batches, evaluation, selection and approved-source publication.

## Decision

Keep traditional character generation guarded as retired. Reuse existing compilation functions in local Body/Head/Assembly/Dressing workflows without restoring old stage execution. Production local rendering accepts registered ComfyUI Qwen Image 2.1 profiles/models via `require_qwen_profile`; normal operation is through AI Proxy per AGENTS.

## Rationale

[V5 Realignment](../../Docs-Joe/Zet%20V5%20Realignment.md) states the intent to prioritize local generation and distinguish candidate work from reusable approved images. Code explicitly enforces retirement and profile validation. The full historical rationale for selecting only Qwen Image 2.1 or retaining each old adapter is unknown; this record does not infer model-quality results.

## Alternatives and tradeoffs

Older manual/Stable Matrix/traditional paths provide evidence of prior mechanisms, not current production support. A broad backend policy or removal of retained code would change compatibility and consumers and requires a separate approved task. The current boundary narrows supported rendering while leaving compiler and inspection compatibility concerns visible.

## Consequences

Make new local character changes in local services/shared compilers, not traditional stage transitions or retired dashboards. Preserve selection-versus-lock semantics, source integrity, logical references, human review and queue attempts. Historical adapter tests do not establish supported production execution.

## Related code and documentation

[pipeline_retirement.py](../../zet/services/pipeline_retirement.py), [WorkerService](../../zet/services/worker_service.py), [local character service](../../zet/services/local_character_asset_pipeline_service.py), [local render policy](../../zet/services/local_render_policy.py), [presets](../../Config/Local_Render_Presets.json), [local asset store](../../zet/services/local_asset_store_service.py), [local character component](../COMPONENTS/LOCAL_CHARACTERS.md), [AGENTS](../../AGENTS.md).

Verification update after V5 recovery: use [Testing](../Testing.md) for approved scenarios and explicit coverage gaps. The original dedicated Python tests were retired; their evidence is available with `git show 2d0e1a9:tests/<filename>.py`, not as current runnable checks.
