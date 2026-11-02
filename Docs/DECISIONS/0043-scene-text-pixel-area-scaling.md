# 0043 - Scene text scales with pixel area
Status: accepted (2026-11-02)

## Decision
Use the packaged 896x1184 draft backdrop as the scene-text style reference. Scale font, padding, outline and tail dimensions by the square root of actual image pixel count divided by the backdrop pixel count. Keep placements normalized to the image, and keep draft/final mode metadata out of the scale calculation.

The shared style dialog previews editable sample text over this backdrop. Candidate Shrink box uses the same font metrics and wrapping as preview and confirmation, minimizes the box while retaining line breaks, and preserves its center and tail geometry.

## Consequences
Equal-area images use equal pixel sizing across aspect ratios. A roughly four-megapixel image scales linear dimensions about two times from the draft reference. Existing style values need no migration; new confirmations use the new interpretation while already confirmed PNGs remain unchanged.
