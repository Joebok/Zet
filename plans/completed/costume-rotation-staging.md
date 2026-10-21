# Costume rotation staging
Status: complete (implementation and staging verification; live artistic acceptance unverified)
Related specification: Joe's rotation-alternative goal, back-left Tsaeytte Adult / Canonical Adventure Gear batch ac89a150ae8b4132972a0a9a4b57de42.

## Goal and current behavior
Add Stage Rotation to Costume Dressing views. Rotate an available selected dressed view into the matching Assembly orientation, staging the complete prompt and ordered labeled references in Image Generation. The existing ImageGeneratorStagingService stages ordinary dressing through CharacterRenderSlots; it has no rotation mode. Joe's current manual prompt contains duplicated, contradictory edit-base contracts. Its source recipe is LEFT_PROFILE for BACK_LEFT_3_4.

## Acceptance and constraints
- A separate rotation template has one dressed edit base, one matching Assembly orientation reference, and view-filtered costume resources in citation order.
- Preserve garment topology, rear hem length and continuous shape; never fill an open front with an invented panel. Match target orientation without importing Assembly fitment clothes.
- Honor explicit selected-view recipes; default to the nearest available different selected view. Reject missing/rejected/foreign sources and unsupported pipelines before replacing the generator board.
- Stage only: no pipeline renders, selections, locks or prompt artifacts are changed. Existing Image Generator handoff/reload/render configuration behavior is reused.
- No dependencies or permanent tests; no live Narrative check. Inspect the existing live example read-only; model quality requires human assessment of actual renders.

## Impact analysis
Compiler: Scripts/Run_Costume_Dressing_Jobs.py and a dedicated Config/Prompt_Templates rotation template. Services: focused costume rotation preparation plus image_generator_staging_service.py and render_slot_service.py projection. Web: local router and shared character actions. Documentation owners: PROMPTS, LOCAL_CHARACTERS, CODE_MAP and Testing; no serialized schema or invariant change.

## Work packets
### WP1 — Rotation compilation and input preparation
- Dependencies: none.
- Files/interfaces: costume compiler/template and focused rotation service.
- Work: select and validate the dressed source, assign ordered roles, compile fresh temporary artifacts with accepted batch template overlays, freeze references.
- Acceptance: back-left uses selected LEFT_PROFILE and matching Assembly; supplemental embroidery/rear jewelry remain numbered correctly; no dressing contract survives.
- Validation: disposable compiler/service checks using isolated fixture data and read-only production source observations.
- Status: complete.

### WP2 — Dashboard handoff
- Dependencies: WP1.
- Files/interfaces: staging service, slot projection, local router, local_asset_pipeline.js.
- Work: add Stage Rotation with a useful prerequisite reason and reuse the existing guarded Image Generator handoff.
- Acceptance: only Dressing exposes the action; staging replaces inputs with labels/settings and survives reload; failures preserve the board.
- Validation: disposable isolated API/browser checks and JavaScript syntax.
- Status: complete.

### WP3 — Verification and documentation
- Dependencies: WP1/WP2.
- Files/interfaces: affected component docs, code map, this plan.
- Acceptance: approved regressions pass, final diff is scoped, observed limits are recorded.
- Validation: npm.cmd run test:e2e; Python AST; node --check; git diff --check; visual inspection of source and staged output.
- Status: complete.

## Progress and decisions
2026-10-21: inspected current production prompt/read-only batch detail, shared compiler/section conditioning, selected-reference ownership guard, staging handoff and approved S2 boundaries. Existing generator has running work; preserve it during development and use isolated validation.

Implemented the compiler's local `rotation=True` alternative, dedicated template,
focused source/preparation service and shared stage action. Explicit recipes win;
default source choice is the nearest available selected view. All eight isolated
view preparations/API checks passed, including source-batch byte immutability,
no inference, invalid/rejected/missing/foreign/self sources and unchanged generator
board on failure. Four approved fast scenarios passed in 41.5s. Real source
compilation resolves LEFT_PROFILE + BACK_LEFT Assembly + embroidery + rear jewelry.
The source image's rear hem is shorter than the authored ankle-length requirement;
the prompt makes authored geometry authoritative instead of preserving that error.

An initial disposable probe correctly hit the issue-worker production-config fence;
the probe then used the existing development config with explicit read-only source
paths. It exposed the normal revision wrapper's requirement that provenance outputs
live below PipelineCandidates. Rotation now uses the same accepted source overlay
directly with temporary compilation, avoiding any source-batch provenance writes.
Browser validation clicked BACK_LEFT Stage Rotation successfully and observed the
generator mode, dimensions, labels, clean prompt and empty board. Reload and final
checks subsequently passed, including the approximate 45-degree turn note.
No production restart/deployment or new live render was performed.

## Final results
Stage Rotation is implemented on Dressing views through the existing guarded
generator handoff. The separate prompt uses one dressed edit base, matching
Assembly orientation and view-filtered design resources with preserved ordering,
labels, dimensions and rendering configuration. Software validation passed:
four approved E2E scenarios (41.5s), eight-view disposable service/API checks,
accepted-source overlay preservation, mounted Chrome click and reload, five
Python AST checks, two JavaScript syntax checks and final diff review/check.
Source example artifacts and an inspected browser capture are ignored beneath
`test-results/rotation/`. No maintained tests, dependencies, production data writes,
live inference, restart or deployment were added. The production prompt/session
is retained while its jobs run; the new action requires the updated server code
to be deployed: port 8081 runs the separate installed Zet_Runtime release
`a1d6916be75c0826838531a63f2663591fab4f87`, not this checkout. Actual
hem/shape/open-front fidelity remains a live operator trial;
this plan does not claim that generated images meet artistic acceptance.
