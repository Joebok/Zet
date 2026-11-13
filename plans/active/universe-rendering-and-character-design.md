# Separate universe rendering style from character design

Status: active
Related specification: approved implementation plan in the style management chat.

## Goal and current behavior

Keep the illustrated finish consistent while allowing each character, costume, and scene to define its own design. ZetTester currently combines manga technique with heroic physique, costume ornament, and staging. Moonsea and the local Head Image Construct recipe both include eye-size guidance that can compete with Tsaeytte's authored eyes.

## Work packets

1. Universe Settings guidance and proposed copy. Validate style save and reload in a disposable universe.
2. Local Body Reference, Head Image Construct, and text-only Head Image Edit. Use existing compiler inputs and validate neutral staging, authored proportions, and head visibility.
3. Wizard and authoring manual. Use existing sections and review flow. Validate create, legacy edit, and resumed interview turns.
4. Run the approved E2E suite and diff checks, record findings, and present the exact production edits for approval. Keep this plan active until rollout is resolved.

## Implementation and validation

- Packets 1-3 are implemented. Settings use the existing fields, local Body and Head prompts distinguish finish from authored features, and the Wizard drafts into existing sections.
- Disposable Chromium check passed. Both style fields saved and reloaded in an isolated universe. A Dressing candidate retried with its captured prompt after the canonical style changed, then selected and locked. A fresh candidate adopted the revised style.
- Disposable compiler checks passed for neutral Body Reference staging, new style resolution, and Tsaeytte Adult's visible FRONT eye instructions, BACK occlusion, and text-only Head Edit. The disposable Tsaeytte master omitted library reference tags to isolate prompt text from production image storage.
- Prepared Wizard responses passed for creation, an interview with a saved answer, and editing a legacy template without Head Edit sections.
- The final `npm run test:e2e` passed all four approved scenarios in 41.0 seconds. `git diff --check` passed.
- Production settings await approval. Live image quality remains to be assessed.

## Proposed settings

### ZetTester canonical

Mature manga illustration with clean, confident linework and varied line weights. Use crisp shadow shapes, softer tonal transitions where forms turn, and layered color with clear value separation. Keep contours and materials readable with selective detail and restrained highlights. Render with a distinctly illustrated finish.

### ZetTester environmental

Mature manga environment illustration with clean, varied linework, crisp shadow shapes, softer tonal transitions, and layered color. Distinguish materials through shape, value, and selective texture. Use atmospheric color shifts and reduced contrast to separate foreground, middle distance, and background where visible. Render with a distinctly illustrated finish.

### Moonsea canonical

Detailed naturalistic fantasy illustration with a restrained painterly finish. Model forms through gradual light and shadow, subtle warm and cool color variation, and controlled edges. Distinguish skin, hair, cloth, leather, metal, and gemstones through their texture and response to light. Keep detail legible at the intended image scale.

Retain Moonsea's existing environmental text.

## Original ZetTester style reference

### Canonical

Detailed heroic manga illustration with dynamic, idealized character anatomy, expressive faces, and refined, confident linework. Render characters with elongated proportions, long limbs, defined musculature, and striking silhouettes. Male characters feature broad shoulders, tapered torsos, powerful physiques, and strong facial structures. Female characters feature slender waists, graceful curves, long legs, and elegant yet athletic physiques. Emphasize idealized beauty and heroic physical presence without sacrificing anatomical coherence.

Faces feature large, expressive eyes, finely sculpted noses, defined jawlines, and distinctive, carefully shaped hairstyles. Convey personality through subtle facial expressions and purposeful body language.

Use clean, varied line weights, richly detailed costumes, dramatic lighting, and layered shading that combines crisp manga-style shadows with softer tonal transitions. Employ dynamic compositions, expressive gestures, and confident poses that communicate strength, determination, and individuality.

Maintain a sophisticated, mature manga aesthetic. Avoid chibi proportions, cartoonish exaggeration, overly simplified anatomy, photorealism, and excessively heavy outlines.

### Environmental

Detailed heroic manga environment illustration with dramatic compositions, refined linework, and a strong sense of scale and grandeur. Render landscapes, architecture, interiors, and objects as dimensional illustrated forms with deliberate shape design and subtly exaggerated proportions. Emphasize sweeping vistas, towering structures, distinctive silhouettes, and compelling perspectives that evoke adventure, wonder, and epic storytelling.

Use clean, varied line weights to define important forms, architectural details, and natural features. Combine crisp manga-style shadows with softer tonal transitions, layered colors, and selective texture detail. Render stone, wood, metal, vegetation, and water with recognizable material characteristics without reproducing photographic microtexture.

Employ dramatic but coherent lighting, atmospheric perspective, and rich, harmonious color palettes. Keep foreground elements clearly defined, middle-distance forms moderately detailed, and distant features softened through reduced contrast, simplified linework, and atmospheric color shifts.

Maintain a sophisticated, mature manga aesthetic with a balance of believable environmental structure and imaginative stylization. Avoid photorealism, photographic depth of field, excessively heavy outlines, flat cartoon rendering, and overly simplified scenery.
