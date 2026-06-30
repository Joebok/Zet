# Final Image Prompt - Body Reference

Create a clean technical body-reference image for {{CHARACTER_PHASE}} {{CHARACTER_NAME}}.

Task: body-reference.

Required view: {{VIEW_LABEL}}.

View token: {{VIEW_TOKEN}}.

View instruction: {{VIEW_INSTRUCTION}}

Use a neutral technical fitment presentation. The output must be a body-reference render only, not a narrative scene, not a costume render, not a head-fitment image, and not an expression sheet.

## Character Facts

{{SECTION:GENERAL_DESCRIPTION_FACTS}}

## Body Facts

{{SECTION:BODY_DESCRIPTION_FACTS}}

## View-Specific Body Requirements

{{SECTION:BODY_DESCRIPTION_VIEW_{{VIEW_TOKEN}}}}

## Identity Preservation

{{SECTION:IDENTITY_PRESERVATION_CORE}}

{{SECTION:IDENTITY_PRESERVATION_BODY}}

## Fitment Rendering

{{SECTION:FITMENT_RENDERING_RULES}}

## Technical Modesty Layer

{{SECTION:TECHNICAL_MODESTY_LAYER}}

## Negative Guidance

{{SECTION:NEGATIVE_GUIDANCE_GENERAL}}

{{SECTION:NEGATIVE_GUIDANCE_JOB_SPECIFIC}}

## Output Requirements

Render a single full-body technical reference image in the requested view.

Use no external source images, cached images, discovered images, or implicit image resources unless a future job explicitly overrides the configured resource policy.

Do not include costume, equipment, jewelry, narrative props, scene staging, dramatic lighting, emotional acting, or unrelated views.
