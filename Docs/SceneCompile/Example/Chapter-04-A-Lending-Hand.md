# The Scene

Write the scene prose here. This section is ignored by the compiler unless text is copied into a bounded compiler section below.

---

# Compiler Sections

Keep the marker lines intact. The Story pipeline will combine these scene sections with story-level sections from the story markdown file.

## Scene Name

<!-- ZET:BEGIN SCENE_NAME -->

Chapter 04 - A Lending Hand

<!-- ZET:END SCENE_NAME -->

## Scene Description

<!-- ZET:BEGIN SCENE_DESCRIPTION -->

Tsaeytte is on the right side of center of the image. She is kneeling, her right arm is holding two books, her left arm is reaching to pick up another book that is to the left. There is another book on the pathway, opened and upside down. Tsaeytte is looking up at Valindia who is standing nearby, holding out a book to Tsaeytte. Valinia is standing with her weight on her left leg, her right leg is bent at the knee, her right boot heel raised. Her right hand is on her hip, her left hand is holding the book. Her left arm is bent at the elbow. Her head is tipped down to face Tsaeytte fully. The book being held is not quite close enough for Tsaeytte to grab. They are staring at each other. Tsaeytte has a tear on her cheek. Valindia is empathetic.

[Use:
Dialogue panel:
- Speaker: Tsaeytte
- Text: "Potential is Nothing without Disciplene"
]

Character layout (left to right): Valinida → book on the pathway → Tsaeytte.

Motion: Valindia is standing still holding a book out to Tsaeytte. Tsaeytte is stationary but picking up the other books.

Gaze: Tsaeytte and Valindia are looking directly at each other.

<!-- ZET:END SCENE_DESCRIPTION -->

## Scene Image References

<!-- ZET:BEGIN SCENE_IMAGE_REFERENCES -->

{{ASSET:Tsaeytte:Youth:27:Costume | Left-Profile | Woodland outfit}}
{{AUX:person:valindia-vandemere-profile}}
{{AUX:place:the-spire-archway}}

<!-- ZET:END SCENE_IMAGE_REFERENCES -->

## Scene Rendering Notes

<!-- ZET:BEGIN SCENE_RENDERING_NOTES -->

* Camera/framing: Portrait 4:5 aspect ratio.
* Lighting: Mid-morning diffuse sunlight, shadows falling right to left.
* Environment:
* Character priority:
* Prop priority:
* Avoid:

<!-- ZET:END SCENE_RENDERING_NOTES -->

---

## Render Prompt

{{SECTION:STORY_TITLE}}

Scene: `[Chapter 04 - A Lending Hand]`

{{SECTION:CANONICAL_ART_STYLE}}

{{SECTION:STORY_PREMISE}}

{{SECTION:STORY_VISUAL_CONTINUITY}}

{{SECTION:SCENE_DESCRIPTION}}

{{SECTION:SCENE_IMAGE_REFERENCES}}

{{SECTION:SCENE_RENDERING_NOTES}}

Create one finished narrative scene image from this prompt. Do not stamp text, captions, labels, compiler markers, filenames, or reference tags into the image.

<!-- ZET:BEGIN LOCAL_IMAGE_GEN_OVERRIDES -->

prompt:
negative_prompt:denoising_strength:
steps:
cfg_scale:
seed:
s_noise:
sd_model_checkpoint:
sampler_name:
scheduler:
enable_hr: false
hr_upscaler:
hr_second_pass_steps:
hr_scale:
orientation: landscape
restore_faces:

<!-- ZET:END LOCAL_IMAGE_GEN_OVERRIDES -->
