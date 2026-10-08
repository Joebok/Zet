# Scene assembly comparison 13efb6d06b56cbe4

**Recommendation:** Corrected deterministic prompts show a useful Chapter 03 signal: their net criterion-pass-count change versus the original prompt across identity, pose, scale, native dialogue, and authored requirements is +9. Keep testing prompt/compiler corrections before considering a migration.

Native scenes were scored blind. Lettered variants inherit native ratings for all non-dialogue criteria; only the new or retained balloon is scored again.

## Chapter-01-Standing-in-Wonder

| Arm | Rendered | Mean seconds | Native dialogue pass | Native finished scenes | Lettered finished scenes |
|---|---:|---:|---:|---:|---:|
| A_original | 8/8 | 81.44 | 8/8 | 6/8 | 6/8 |
| B_corrected | 8/8 | 78.14 | 5/8 | 0/8 | 0/8 |
| C_layers | 8/8 | 94.27 | 8/8 | 0/8 | 0/8 |

### Native criterion ratings

Counts are shown as pass / fail / unassessable / unreviewed.

| Criterion | Original prompt | Corrected prompt | Layer composition |
|---|---:|---:|---:|
| cast_and_identity | 8 / 0 / 0 / 0 | 2 / 5 / 1 / 0 | 0 / 8 / 0 / 0 |
| pose_and_expression | 8 / 0 / 0 / 0 | 8 / 0 / 0 / 0 | 8 / 0 / 0 / 0 |
| props_and_source_retention | 8 / 0 / 0 / 0 | 7 / 0 / 1 / 0 | 7 / 0 / 1 / 0 |
| facing_and_gaze | 8 / 0 / 0 / 0 | 8 / 0 / 0 / 0 | 8 / 0 / 0 / 0 |
| scale_depth_and_grounding | 6 / 2 / 0 / 0 | 6 / 2 / 0 / 0 | 0 / 8 / 0 / 0 |
| background_continuity | 8 / 0 / 0 / 0 | 5 / 3 / 0 / 0 | 0 / 7 / 1 / 0 |
| native_dialogue | 8 / 0 / 0 / 0 | 5 / 3 / 0 / 0 | 8 / 0 / 0 / 0 |
| integration_quality | 8 / 0 / 0 / 0 | 5 / 3 / 0 / 0 | 1 / 7 / 0 / 0 |
| narrative_readability | 8 / 0 / 0 / 0 | 6 / 2 / 0 / 0 | 0 / 8 / 0 / 0 |
| authored_requirements | 8 / 0 / 0 / 0 | 6 / 2 / 0 / 0 | 4 / 4 / 0 / 0 |

### Lettered balloon review

Only the balloon and lettering were rescored; all other visual ratings carry forward from the native render. Counts are pass / fail / unassessable / unreviewed.

| Criterion | Original prompt | Corrected prompt | Layer composition |
|---|---:|---:|---:|
| Balloon and lettering | 8 / 0 / 0 / 0 | 7 / 1 / 0 / 0 | 8 / 0 / 0 / 0 |

### Paired disagreements

For each seed, this counts criteria where both arms were rated pass/fail and disagreed.

| Comparison | cast_and_identity | pose_and_expression | props_and_source_retention | facing_and_gaze | scale_depth_and_grounding | background_continuity | native_dialogue | integration_quality | narrative_readability | authored_requirements |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A_original vs B_corrected | 5 | 0 | 0 | 0 | 4 | 3 | 3 | 3 | 2 | 2 |
| B_corrected vs C_layers | 2 | 0 | 0 | 0 | 6 | 5 | 3 | 4 | 6 | 6 |
| A_original vs C_layers | 8 | 0 | 0 | 0 | 6 | 7 | 0 | 7 | 8 | 4 |

## Chapter-02-At-the-Arch

| Arm | Rendered | Mean seconds | Native dialogue pass | Native finished scenes | Lettered finished scenes |
|---|---:|---:|---:|---:|---:|
| A_original | 8/8 | 101.15 | 4/8 | 1/8 | 1/8 |
| B_corrected | 8/8 | 96.51 | 3/8 | 1/8 | 1/8 |
| C_layers | 8/8 | 114.05 | 4/8 | 0/8 | 0/8 |

### Native criterion ratings

Counts are shown as pass / fail / unassessable / unreviewed.

| Criterion | Original prompt | Corrected prompt | Layer composition |
|---|---:|---:|---:|
| cast_and_identity | 4 / 4 / 0 / 0 | 6 / 2 / 0 / 0 | 1 / 7 / 0 / 0 |
| pose_and_expression | 2 / 4 / 2 / 0 | 5 / 3 / 0 / 0 | 8 / 0 / 0 / 0 |
| props_and_source_retention | 6 / 0 / 2 / 0 | 6 / 2 / 0 / 0 | 8 / 0 / 0 / 0 |
| facing_and_gaze | 3 / 3 / 2 / 0 | 4 / 4 / 0 / 0 | 5 / 2 / 1 / 0 |
| scale_depth_and_grounding | 8 / 0 / 0 / 0 | 8 / 0 / 0 / 0 | 1 / 7 / 0 / 0 |
| background_continuity | 8 / 0 / 0 / 0 | 5 / 3 / 0 / 0 | 0 / 8 / 0 / 0 |
| native_dialogue | 4 / 4 / 0 / 0 | 3 / 5 / 0 / 0 | 4 / 4 / 0 / 0 |
| integration_quality | 5 / 3 / 0 / 0 | 4 / 4 / 0 / 0 | 0 / 8 / 0 / 0 |
| narrative_readability | 3 / 5 / 0 / 0 | 5 / 3 / 0 / 0 | 5 / 3 / 0 / 0 |
| authored_requirements | 3 / 5 / 0 / 0 | 5 / 3 / 0 / 0 | 3 / 5 / 0 / 0 |

### Lettered balloon review

Only the balloon and lettering were rescored; all other visual ratings carry forward from the native render. Counts are pass / fail / unassessable / unreviewed.

| Criterion | Original prompt | Corrected prompt | Layer composition |
|---|---:|---:|---:|
| Balloon and lettering | 4 / 4 / 0 / 0 | 4 / 3 / 1 / 0 | 2 / 6 / 0 / 0 |

### Paired disagreements

For each seed, this counts criteria where both arms were rated pass/fail and disagreed.

| Comparison | cast_and_identity | pose_and_expression | props_and_source_retention | facing_and_gaze | scale_depth_and_grounding | background_continuity | native_dialogue | integration_quality | narrative_readability | authored_requirements |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A_original vs B_corrected | 2 | 2 | 1 | 4 | 0 | 3 | 5 | 3 | 2 | 4 |
| B_corrected vs C_layers | 5 | 3 | 2 | 1 | 7 | 5 | 1 | 4 | 0 | 2 |
| A_original vs C_layers | 3 | 4 | 0 | 3 | 7 | 8 | 4 | 5 | 2 | 2 |

## Chapter-03-Collision

| Arm | Rendered | Mean seconds | Native dialogue pass | Native finished scenes | Lettered finished scenes |
|---|---:|---:|---:|---:|---:|
| A_original | 8/8 | 80.91 | 2/8 | 0/8 | 0/8 |
| B_corrected | 8/8 | 80.76 | 8/8 | 1/8 | 1/8 |
| C_layers | 8/8 | 98.56 | 8/8 | 0/8 | 0/8 |

### Native criterion ratings

Counts are shown as pass / fail / unassessable / unreviewed.

| Criterion | Original prompt | Corrected prompt | Layer composition |
|---|---:|---:|---:|
| cast_and_identity | 8 / 0 / 0 / 0 | 8 / 0 / 0 / 0 | 7 / 1 / 0 / 0 |
| pose_and_expression | 6 / 2 / 0 / 0 | 8 / 0 / 0 / 0 | 8 / 0 / 0 / 0 |
| props_and_source_retention | 4 / 4 / 0 / 0 | 8 / 0 / 0 / 0 | 8 / 0 / 0 / 0 |
| facing_and_gaze | 7 / 1 / 0 / 0 | 8 / 0 / 0 / 0 | 8 / 0 / 0 / 0 |
| scale_depth_and_grounding | 2 / 6 / 0 / 0 | 1 / 7 / 0 / 0 | 8 / 0 / 0 / 0 |
| background_continuity | 8 / 0 / 0 / 0 | 8 / 0 / 0 / 0 | 8 / 0 / 0 / 0 |
| native_dialogue | 2 / 6 / 0 / 0 | 8 / 0 / 0 / 0 | 8 / 0 / 0 / 0 |
| integration_quality | 8 / 0 / 0 / 0 | 8 / 0 / 0 / 0 | 0 / 8 / 0 / 0 |
| narrative_readability | 6 / 2 / 0 / 0 | 8 / 0 / 0 / 0 | 8 / 0 / 0 / 0 |
| authored_requirements | 2 / 6 / 0 / 0 | 4 / 4 / 0 / 0 | 8 / 0 / 0 / 0 |

### Lettered balloon review

Only the balloon and lettering were rescored; all other visual ratings carry forward from the native render. Counts are pass / fail / unassessable / unreviewed.

| Criterion | Original prompt | Corrected prompt | Layer composition |
|---|---:|---:|---:|
| Balloon and lettering | 8 / 0 / 0 / 0 | 8 / 0 / 0 / 0 | 8 / 0 / 0 / 0 |

### Paired disagreements

For each seed, this counts criteria where both arms were rated pass/fail and disagreed.

| Comparison | cast_and_identity | pose_and_expression | props_and_source_retention | facing_and_gaze | scale_depth_and_grounding | background_continuity | native_dialogue | integration_quality | narrative_readability | authored_requirements |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A_original vs B_corrected | 0 | 2 | 4 | 1 | 3 | 0 | 6 | 0 | 2 | 6 |
| B_corrected vs C_layers | 1 | 0 | 0 | 0 | 7 | 0 | 0 | 8 | 0 | 4 |
| A_original vs C_layers | 1 | 2 | 4 | 1 | 6 | 0 | 6 | 8 | 2 | 6 |
