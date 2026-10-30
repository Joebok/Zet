# 0038: Compatible animation zoom targets

Status: accepted

Story animation version 1 already stores camera keyframes whose coordinates are
frame centers. Reinterpreting those coordinates would change existing exports.
An optional `camera_mode: "target"` marks keyframes whose coordinates identify a
point on the pinned image. The player clamps the center to the fitted image while
zooming; absent mode preserves the previous framing. Text opacity remains in the
existing keyframe format, so no stored animation migration is required.
