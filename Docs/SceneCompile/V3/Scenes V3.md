# CODEX Implementation Plan: Zet Scene Builder V3

Implement a clean V3 Scene Builder reset.

Do not implement migration from V1 or V2. Remove any existing migration coding. This is still prototype-stage work. Prefer clean V3 code and clean V3 file formats over compatibility clutter.

## Core Direction

Use these source-of-truth rules:

```text
Story markdown = human writing, story notes, zine outline, workshop space.
Story settings JSON = story-wide compiler settings.
Scene JSON = canonical structured scene definition.
Generated markdown/render files = compiler outputs, not source files.
PNG = rendered image output.
```

Do not make the scene compiler depend on parsing the story `.md` file.

Instead, create a companion story settings file:

```text
Stories/FirstDay/FirstDay.md              ← human story notes
Stories/FirstDay/FirstDay.story.json      ← story-wide compiler settings
Stories/FirstDay/Scenes/Chapter-04-A-Lending-Hand.scene.json
Stories/FirstDay/Scenes/Chapter-04-A-Lending-Hand.png
```

The old scene `.md` file should become optional generated output only:

```text
Stories/FirstDay/Scenes/Chapter-04-A-Lending-Hand.render.md
```

Do not treat the scene `.md` file as canonical anymore.

---

# V3 File Ownership

## Story Markdown Owns

The story `.md` file is for the human author.

It may contain:

* story outline
* zine/page plan
* freeform notes
* draft dialogue
* sequence ideas
* prose sketches
* TODOs
* scene list for the author

The compiler should not need to read it.

## Story Settings JSON Owns

The story settings JSON owns reusable story-wide compiler values:

* story title
* canonical art style
* dialogue panel styles
* story premise summary
* visual continuity rules
* default avoid rules
* compiler profile defaults
* output folder conventions
* optional scene index

This replaces compiler-owned markdown sections.

## Scene JSON Owns

The scene JSON owns everything specific to a scene image:

* canvas
* composition
* camera
* environment
* lighting
* mood
* scene elements
* placements
* pose details
* hand/arm details
* props
* interactions
* dialogue content
* reference image assignments
* scene-specific avoid rules
* render settings
* output artifact paths

## Compiler Outputs Own

Generated compiler artifacts should be written from source data, not manually edited.

Recommended generated files:

```text
Final_Image_Prompt.md
Local_Render_Brief.json
Local_Render_Prompt.md
Scene_Render_IR.json
```

These may live in a scene output/build folder, for example:

```text
Stories/FirstDay/Scenes/Chapter-04-A-Lending-Hand.build/
```

Do not store generated prompt text inside the source scene JSON.

---

# New Files

Add support for:

```text
*.story.json
*.scene.json
```

Recommended naming:

```text
FirstDay.story.json
Chapter-04-A-Lending-Hand.scene.json
```

This prevents ambiguity between story-level JSON and scene-level JSON.

---

# Story Settings JSON Data Model

Create a new story settings model.

Use this exact conceptual structure unless the repository already has naming conventions that require light adjustment.

```json
{
  "schema_version": 1,
  "file_kind": "story_settings",
  "story": {
    "id": "first_day",
    "title": "First Day at the Spire",
    "slug": "FirstDay",
    "human_markdown_path": "Stories/FirstDay/FirstDay.md",
    "premise": "Tsaeytte's first day attending the Spire of Celestial Wisdom to study magic. She starts out optimistic and joyful but quickly realizes that the world is bigger and meaner than her childhood in Elvenwood prepared her for.",
    "notes": ""
  },
  "style_defaults": {
    "canonical_art_style": {
      "id": "default_story_style",
      "short_label": "Painterly semi-realistic fantasy illustration with anime-influenced facial proportions",
      "full_prompt_text": "Painterly semi-realistic fantasy illustration with anime-influenced facial proportions, large expressive eyes, refined linework, and warm storybook-fantasy color handling.",
      "negative_style_notes": ""
    },
    "visual_continuity": {
      "rules": [
        "Preserve the story's canonical art style across all scene images.",
        "Preserve recurring characters, costumes, props, and locations when referenced by scene tags.",
        "Keep scene images consistent with the story premise unless a scene explicitly calls for contrast."
      ],
      "notes": ""
    },
    "default_avoid": [
      "inconsistent character identity",
      "wrong costume",
      "wrong location design",
      "modern objects",
      "unreadable faces",
      "merged characters",
      "extra limbs",
      "malformed hands"
    ]
  },
  "dialogue_styles": [
    {
      "id": "compact_parchment",
      "display_name": "Compact parchment dialogue panel",
      "enabled_by_default": true,
      "panel_prompt": "Compact rectangular parchment dialogue panel with softly rounded corners, warm ivory parchment background, subtle paper texture, and a thin dark bronze border.",
      "pointer_prompt": "Short unobtrusive triangular pointer aimed toward the speaker's mouth.",
      "lettering_prompt": "Clean modern comic-style sans-serif lettering, medium weight, crisp edges, high legibility, sentence case, normal capitalization.",
      "layout_rules": [
        "Panel should be only slightly larger than the text.",
        "Leave small even margins on all sides.",
        "Wrap naturally into two or three balanced lines when practical.",
        "Avoid long single-line dialogue.",
        "Avoid awkward one-word final lines.",
        "Do not obscure important faces, hands, props, or focal areas."
      ],
      "avoid": [
        "oversized speech panel",
        "excessive empty padding",
        "pure white panel",
        "hard-to-read text",
        "panel covering faces",
        "panel covering important hands or props"
      ],
      "notes": ""
    }
  ],
  "compiler_profiles": {
    "final_image_prompt": {
      "include_story_premise": false,
      "include_visual_continuity": true,
      "include_dialogue_when_scene_has_dialogue": true,
      "include_reference_assignments": true,
      "include_final_verification": true,
      "notes": ""
    },
    "local_render": {
      "purpose": "composition preview only",
      "include_dialogue": false,
      "include_reference_tags": false,
      "negative_text_terms": [
        "text",
        "letters",
        "caption",
        "speech bubble",
        "watermark"
      ],
      "notes": ""
    }
  },
  "scene_index": [
    {
      "scene_id": "chapter_04_a_lending_hand",
      "scene_json_path": "Stories/FirstDay/Scenes/Chapter-04-A-Lending-Hand.scene.json",
      "title": "Chapter 04 - A Lending Hand",
      "sequence": 4,
      "notes": ""
    }
  ],
  "metadata": {
    "created_at": "",
    "updated_at": "",
    "created_by": "Zet Story Settings"
  }
}
```

---

# Story Settings Helper Text

Implement helper text for the Story Settings editor.

Use this mapping or an equivalent internal structure.

```json
{
  "story.id": "Stable internal ID for this story. Use a short lowercase identifier. Do not change casually after scenes reference it.",
  "story.title": "Human-readable story title used in exports and optional prompt context.",
  "story.slug": "Filesystem-friendly story identifier used in paths and generated filenames.",
  "story.human_markdown_path": "Path to the human-authored story markdown file. The compiler does not parse this during scene rendering.",
  "story.premise": "Short story-level context. Keep this concise. The final image prompt usually should not include the full premise unless a scene needs it.",
  "story.notes": "Private author notes about the story settings file.",
  "style_defaults.canonical_art_style.id": "Stable ID for this art style preset.",
  "style_defaults.canonical_art_style.short_label": "Short visible label for the style. Useful in dropdowns and summaries.",
  "style_defaults.canonical_art_style.full_prompt_text": "Full reusable art style text inserted into scene compiler output.",
  "style_defaults.canonical_art_style.negative_style_notes": "Optional style-specific things to avoid.",
  "style_defaults.visual_continuity.rules": "Story-wide visual continuity rules. Keep these short and reusable.",
  "style_defaults.visual_continuity.notes": "Notes about how visual continuity should be interpreted.",
  "style_defaults.default_avoid": "Story-wide negative prompt terms or avoid rules that apply to most scenes.",
  "dialogue_styles[].id": "Stable ID for this dialogue style. Scene dialogue entries reference this value.",
  "dialogue_styles[].display_name": "Human-readable name for this dialogue panel style.",
  "dialogue_styles[].enabled_by_default": "Whether this dialogue style should be preselected for new dialogue entries.",
  "dialogue_styles[].panel_prompt": "Visual description of the dialogue panel itself.",
  "dialogue_styles[].pointer_prompt": "How the panel pointer should aim toward the speaker.",
  "dialogue_styles[].lettering_prompt": "Lettering and readability instructions.",
  "dialogue_styles[].layout_rules": "Rules for panel size, placement, wrapping, and avoiding important artwork.",
  "dialogue_styles[].avoid": "Dialogue-specific negative terms.",
  "dialogue_styles[].notes": "Private notes about this dialogue style.",
  "compiler_profiles.final_image_prompt.include_story_premise": "Include story premise in the final ChatGPT/image prompt. Usually false; scene facts should dominate.",
  "compiler_profiles.final_image_prompt.include_visual_continuity": "Include short continuity rules in the final image prompt.",
  "compiler_profiles.final_image_prompt.include_dialogue_when_scene_has_dialogue": "Include dialogue panel instructions only when the scene has dialogue.",
  "compiler_profiles.final_image_prompt.include_reference_assignments": "Include explicit image-reference assignment instructions.",
  "compiler_profiles.final_image_prompt.include_final_verification": "Append a final checklist to reduce scene mistakes.",
  "compiler_profiles.local_render.purpose": "Purpose label for local rendering, usually composition preview rather than final art.",
  "compiler_profiles.local_render.include_dialogue": "Whether local preview prompts should include dialogue. Usually false.",
  "compiler_profiles.local_render.include_reference_tags": "Whether local render prompts should include unresolved asset/reference tags. Usually false.",
  "compiler_profiles.local_render.negative_text_terms": "Terms to add to local negative prompts when dialogue/text should be excluded.",
  "scene_index[].scene_id": "Stable ID of a scene listed in this story.",
  "scene_index[].scene_json_path": "Path to that scene's canonical .scene.json file.",
  "scene_index[].title": "Human-readable scene title.",
  "scene_index[].sequence": "Story order or page/chapter order.",
  "scene_index[].notes": "Optional author notes for this scene index entry."
}
```

---

# Scene JSON V3 Data Model

Create a new scene model.

Do not store generated `scene_brief`, `positive_prompt`, or `negative_prompt` as canonical scene data.

The compiler can generate and write those into output artifacts.

```json
{
  "schema_version": 3,
  "file_kind": "scene",
  "scene": {
    "id": "chapter_04_a_lending_hand",
    "name": "Chapter 04 - A Lending Hand",
    "slug": "Chapter-04-A-Lending-Hand",
    "sequence": 4,
    "story_settings_path": "Stories/FirstDay/FirstDay.story.json",
    "associated_png_path": "Stories/FirstDay/Scenes/Chapter-04-A-Lending-Hand.png",
    "story_beat": "Valindia unexpectedly offers help to Tsaeytte after Tsaeytte has fallen.",
    "author_notes": ""
  },
  "setup": {
    "canvas": {
      "orientation": "landscape",
      "aspect_ratio": "16:9",
      "width": null,
      "height": null
    },
    "composition": {
      "template": "two character interaction",
      "grid": {
        "columns": 3,
        "rows": 1,
        "draw_grid": false
      },
      "primary_focal_point": "the offered book and mutual gaze between Valindia and Tsaeytte",
      "left_to_right_order": [
        "valindia",
        "open_upside_down_book",
        "tsaeytte"
      ],
      "composition_notes": "Valindia occupies the left third, Tsaeytte occupies the right third, and the Spire archway anchors the center background."
    },
    "camera": {
      "shot_type": "wide shot",
      "camera_height": "eye-level",
      "camera_angle": "straight-on",
      "viewer_position": "front",
      "lens_feel": "normal",
      "focus_priority": "two main characters",
      "notes": ""
    },
    "environment": {
      "location": "stone approach beneath the Spire of Celestial Wisdom archway",
      "time_of_day": "mid-morning",
      "lighting": "diffuse sunlight with soft shadows falling from right to left",
      "mood": "tense and vulnerable, interrupted by an unexpected moment of empathy",
      "weather_or_atmosphere": "clear outdoor campus air",
      "general_foreground_notes": "Keep the stone pathway readable beneath the books and kneeling figure.",
      "general_background_notes": "The Spire archway should establish place without adding a crowd or distracting activity.",
      "important_exclusions": [
        "no crowd blocking the main characters",
        "no visible planning grid",
        "no split-panel comic layout",
        "no modern objects"
      ]
    },
    "style": {
      "inherit_story_art_style": true,
      "art_style_override": "",
      "dialogue_style_id": "compact_parchment",
      "visual_continuity_override": ""
    }
  },
  "scene_elements": [
    {
      "id": "tsaeytte",
      "display_name": "Tsaeytte",
      "element_type": "Character",
      "role": "fallen student being helped",
      "importance": "primary",
      "source_refs": {
        "identity_source": "Characters/Tsaeytte/Youth/Identity.md",
        "costume_source": "Characters/Tsaeytte/Youth/Costumes/Student.md",
        "location_source": "",
        "monster_source": "",
        "prop_source": ""
      },
      "reference_images": [
        {
          "tag": "{{ASSET:Tsaeytte:Youth:Student}}",
          "roles": [
            "identity",
            "hair",
            "ears",
            "costume",
            "proportions"
          ],
          "ignore": [
            "source pose",
            "source background",
            "source camera angle",
            "source framing"
          ],
          "notes": ""
        }
      ],
      "scene_visual_override": "",
      "fallback_visual_description": "",
      "notes": ""
    },
    {
      "id": "valindia",
      "display_name": "Valindia Vandemere",
      "element_type": "Character",
      "role": "student offering help",
      "importance": "primary",
      "source_refs": {
        "identity_source": "Characters/Valindia/Identity.md",
        "costume_source": "Characters/Valindia/Costumes/StudentFashion.md",
        "location_source": "",
        "monster_source": "",
        "prop_source": ""
      },
      "reference_images": [
        {
          "tag": "{{AUX:person:valindia-vandemere-profile}}",
          "roles": [
            "identity",
            "hair",
            "costume",
            "proportions"
          ],
          "ignore": [
            "source pose",
            "source background",
            "source camera angle",
            "source framing"
          ],
          "notes": ""
        }
      ],
      "scene_visual_override": "",
      "fallback_visual_description": "",
      "notes": ""
    },
    {
      "id": "spire_archway",
      "display_name": "The Spire Archway",
      "element_type": "Anchor",
      "role": "location anchor",
      "importance": "background",
      "source_refs": {
        "identity_source": "",
        "costume_source": "",
        "location_source": "Locations/The-Spire/Archway.md",
        "monster_source": "",
        "prop_source": ""
      },
      "reference_images": [
        {
          "tag": "{{AUX:place:the-spire-archway}}",
          "roles": [
            "architecture",
            "location design"
          ],
          "ignore": [
            "source camera composition",
            "source lighting",
            "source framing"
          ],
          "notes": ""
        }
      ],
      "scene_visual_override": "",
      "fallback_visual_description": "Grand stone magic academy archway.",
      "notes": ""
    }
  ],
  "placements": [
    {
      "id": "placement_tsaeytte",
      "scene_element_id": "tsaeytte",
      "screen_cell": {
        "row": 1,
        "column": 3,
        "name": "right"
      },
      "semantic_screen_region": "right foreground",
      "normalized_anchor": {
        "x": 0.74,
        "y": 0.66
      },
      "position_within_cell": "center",
      "depth": "foreground",
      "z_order": 20,
      "frame_coverage": "full body readable in kneeling pose",
      "distance_from_camera": "foreground",
      "visual_scale": "normal character scale, petite relative to Valindia",
      "must_be_visible": true,
      "visible_body_requirements": [
        "face",
        "both hands",
        "books",
        "kneeling posture"
      ],
      "pose": {
        "summary": "kneeling on the stone pathway after a fall",
        "temporary_condition": "fallen but alert",
        "body_view": "front-left three-quarter relative to camera, turned toward screen left",
        "head_view": "turned toward screen left and slightly upward",
        "action_direction_screen": "toward screen left",
        "gaze_target_element_id": "valindia",
        "gaze_description": "looking directly into Valindia's eyes",
        "expression": "wary, embarrassed, emotionally exposed",
        "left_arm_action": "reaches down and toward screen left for a closed book on the pathway",
        "right_arm_action": "holds two books tightly against her torso",
        "left_hand_detail": "reaching toward the ground book, not touching Valindia",
        "right_hand_detail": "securing the books against her body",
        "leg_foot_detail": "kneeling low on the pathway with posture readable and balanced",
        "balance_weight_detail": "low, braced, recovering from a fall"
      },
      "occlusion": {
        "occlusion_level": "none",
        "must_not_occlude": [
          "face",
          "left hand",
          "right arm books"
        ],
        "notes": ""
      },
      "placement_notes": ""
    },
    {
      "id": "placement_valindia",
      "scene_element_id": "valindia",
      "screen_cell": {
        "row": 1,
        "column": 1,
        "name": "left"
      },
      "semantic_screen_region": "left foreground",
      "normalized_anchor": {
        "x": 0.24,
        "y": 0.55
      },
      "position_within_cell": "center",
      "depth": "foreground",
      "z_order": 20,
      "frame_coverage": "full body or nearly full body",
      "distance_from_camera": "foreground",
      "visual_scale": "slightly taller than Tsaeytte",
      "must_be_visible": true,
      "visible_body_requirements": [
        "face",
        "left hand offering book",
        "right hand on hip",
        "standing posture"
      ],
      "pose": {
        "summary": "standing elegantly and offering a book toward Tsaeytte",
        "temporary_condition": "",
        "body_view": "front-right three-quarter relative to camera, angled toward screen center",
        "head_view": "tilted downward toward Tsaeytte",
        "action_direction_screen": "toward screen right",
        "gaze_target_element_id": "tsaeytte",
        "gaze_description": "looking directly into Tsaeytte's eyes",
        "expression": "unexpectedly empathetic and restrained, not mocking",
        "left_arm_action": "bent at the elbow and extending a book toward Tsaeytte",
        "right_arm_action": "right hand rests on her hip",
        "left_hand_detail": "holds the offered book just outside Tsaeytte's reach",
        "right_hand_detail": "rests on hip",
        "leg_foot_detail": "weight on anatomical left leg, anatomical right knee slightly bent, right boot heel raised",
        "balance_weight_detail": "casual but balanced stance"
      },
      "occlusion": {
        "occlusion_level": "none",
        "must_not_occlude": [
          "face",
          "left hand",
          "offered book"
        ],
        "notes": ""
      },
      "placement_notes": ""
    },
    {
      "id": "placement_spire_archway",
      "scene_element_id": "spire_archway",
      "screen_cell": {
        "row": 1,
        "column": 2,
        "name": "center"
      },
      "semantic_screen_region": "center background",
      "normalized_anchor": {
        "x": 0.5,
        "y": 0.42
      },
      "position_within_cell": "center",
      "depth": "background",
      "z_order": 0,
      "frame_coverage": "large background architecture",
      "distance_from_camera": "background",
      "visual_scale": "large architectural scale",
      "must_be_visible": true,
      "visible_body_requirements": [],
      "pose": {
        "summary": "stationary background architecture",
        "temporary_condition": "",
        "body_view": "",
        "head_view": "",
        "action_direction_screen": "",
        "gaze_target_element_id": "",
        "gaze_description": "",
        "expression": "",
        "left_arm_action": "",
        "right_arm_action": "",
        "left_hand_detail": "",
        "right_hand_detail": "",
        "leg_foot_detail": "",
        "balance_weight_detail": ""
      },
      "occlusion": {
        "occlusion_level": "partially behind foreground characters",
        "must_not_occlude": [
          "Valindia",
          "Tsaeytte",
          "offered book"
        ],
        "notes": "Archway should frame the interaction without crowding it."
      },
      "placement_notes": ""
    }
  ],
  "props_and_states": [
    {
      "id": "books_held_by_tsaeytte",
      "scene_element_id": "",
      "display_name": "Two books held by Tsaeytte",
      "count": 2,
      "owner_element_id": "tsaeytte",
      "holder_element_id": "tsaeytte",
      "held_in_hand": "right arm",
      "state": "held tightly against torso",
      "must_remain_visible": true,
      "placement_hint": "right foreground, against Tsaeytte's torso",
      "notes": ""
    },
    {
      "id": "book_tsaeytte_reaches_for",
      "scene_element_id": "",
      "display_name": "Closed book on pathway",
      "count": 1,
      "owner_element_id": "tsaeytte",
      "holder_element_id": "",
      "held_in_hand": "",
      "state": "closed, lying on stone pathway",
      "must_remain_visible": true,
      "placement_hint": "between Tsaeytte and the center foreground, within reach of Tsaeytte's left hand",
      "notes": ""
    },
    {
      "id": "open_upside_down_book",
      "scene_element_id": "",
      "display_name": "Open upside-down book",
      "count": 1,
      "owner_element_id": "tsaeytte",
      "holder_element_id": "",
      "held_in_hand": "",
      "state": "open and upside down on the pathway",
      "must_remain_visible": true,
      "placement_hint": "center foreground between the two characters",
      "notes": ""
    },
    {
      "id": "offered_book",
      "scene_element_id": "",
      "display_name": "Book offered by Valindia",
      "count": 1,
      "owner_element_id": "",
      "holder_element_id": "valindia",
      "held_in_hand": "left hand",
      "state": "held out toward Tsaeytte, not yet touched by Tsaeytte",
      "must_remain_visible": true,
      "placement_hint": "between Valindia and Tsaeytte, just outside Tsaeytte's reach",
      "notes": ""
    }
  ],
  "interactions": [
    {
      "id": "interaction_offered_book",
      "subject_element_id": "valindia",
      "action": "offers",
      "prop_id": "offered_book",
      "target_element_id": "tsaeytte",
      "source_hand": "left",
      "target_hand": "",
      "contact_state": "no contact",
      "distance": "just outside Tsaeytte's reach",
      "emotional_tone": "unexpectedly empathetic but restrained",
      "notes": "This is the central interaction."
    },
    {
      "id": "interaction_mutual_gaze",
      "subject_element_id": "valindia",
      "action": "mutual eye contact",
      "prop_id": "",
      "target_element_id": "tsaeytte",
      "source_hand": "",
      "target_hand": "",
      "contact_state": "",
      "distance": "",
      "emotional_tone": "tense and vulnerable",
      "notes": "Represent mutual gaze as a relationship, not duplicated placement prose only."
    }
  ],
  "dialogue": [
    {
      "id": "dialogue_001",
      "speaker_element_id": "tsaeytte",
      "text": "Potential is nothing without discipline.",
      "tone": "quietly repeating something painful or recently heard",
      "target_element_id": "",
      "include_in_final_image_prompt": true,
      "include_in_local_render": false,
      "panel_style_id": "compact_parchment",
      "preferred_screen_region": "upper right or upper center, wherever it avoids faces and hands",
      "pointer_target": "Tsaeytte's mouth",
      "max_lines": 3,
      "must_not_cover": [
        "Valindia's face",
        "Tsaeytte's face",
        "offered book",
        "Tsaeytte's reaching hand",
        "Spire archway focal area"
      ],
      "notes": ""
    }
  ],
  "reference_assignments": [
    {
      "id": "ref_tsaeytte",
      "tag": "{{ASSET:Tsaeytte:Youth:Student}}",
      "applies_to_element_id": "tsaeytte",
      "roles": [
        "identity",
        "hair",
        "ears",
        "costume",
        "proportions"
      ],
      "ignore": [
        "source pose",
        "source background",
        "source camera angle",
        "source framing"
      ],
      "notes": ""
    },
    {
      "id": "ref_valindia",
      "tag": "{{AUX:person:valindia-vandemere-profile}}",
      "applies_to_element_id": "valindia",
      "roles": [
        "identity",
        "hair",
        "costume",
        "proportions"
      ],
      "ignore": [
        "source pose",
        "source background",
        "source camera angle",
        "source framing"
      ],
      "notes": ""
    },
    {
      "id": "ref_spire_archway",
      "tag": "{{AUX:place:the-spire-archway}}",
      "applies_to_element_id": "spire_archway",
      "roles": [
        "architecture",
        "location design"
      ],
      "ignore": [
        "source camera composition",
        "source lighting",
        "source framing"
      ],
      "notes": ""
    }
  ],
  "avoid": {
    "scene_specific": [
      "extra characters",
      "crowd",
      "swapped character positions",
      "merged bodies",
      "duplicated characters",
      "incorrect gaze",
      "incorrect hand action",
      "floating books",
      "duplicated books",
      "cropped primary figures",
      "oversized speech panel",
      "text other than requested dialogue"
    ],
    "notes": ""
  },
  "render_settings": {
    "final_image_prompt": {
      "enabled": true,
      "output_path": "Stories/FirstDay/Scenes/Chapter-04-A-Lending-Hand.build/Final_Image_Prompt.md"
    },
    "local_render_brief": {
      "enabled": true,
      "output_path": "Stories/FirstDay/Scenes/Chapter-04-A-Lending-Hand.build/Local_Render_Brief.json"
    },
    "local_render_prompt": {
      "enabled": true,
      "output_path": "Stories/FirstDay/Scenes/Chapter-04-A-Lending-Hand.build/Local_Render_Prompt.md"
    },
    "scene_render_ir": {
      "enabled": true,
      "output_path": "Stories/FirstDay/Scenes/Chapter-04-A-Lending-Hand.build/Scene_Render_IR.json"
    }
  },
  "metadata": {
    "created_at": "",
    "updated_at": "",
    "created_by": "Zet Scene Builder V3"
  }
}
```

---

# Scene V3 Helper Text

Implement popup/helper text for every user-facing field.

Use this mapping or equivalent internal constants.

```json
{
  "scene.id": "Stable internal scene ID. Use a short lowercase identifier. Do not change casually after outputs or story indexes reference it.",
  "scene.name": "Human-readable scene title.",
  "scene.slug": "Filesystem-friendly scene name used for paths and generated files.",
  "scene.sequence": "Scene order within the story, chapter, or zine.",
  "scene.story_settings_path": "Path to the companion .story.json file containing story-wide art style, dialogue style, and compiler defaults.",
  "scene.associated_png_path": "Path where the rendered image for this scene should be stored or found.",
  "scene.story_beat": "One short sentence describing what emotionally or narratively happens in this scene.",
  "scene.author_notes": "Private author notes. These are not automatically included in prompts unless explicitly compiled.",
  "setup.canvas.orientation": "Image orientation: landscape, portrait, square, comic panel, or custom.",
  "setup.canvas.aspect_ratio": "Target image shape such as 16:9, 4:5, 1:1, or custom.",
  "setup.canvas.width": "Optional pixel width. Leave null if the renderer or preset controls this.",
  "setup.canvas.height": "Optional pixel height. Leave null if the renderer or preset controls this.",
  "setup.composition.template": "Reusable composition pattern, such as two character interaction, confrontation, establishing shot, or action scene.",
  "setup.composition.grid.columns": "Number of planning columns in the invisible layout grid.",
  "setup.composition.grid.rows": "Number of planning rows in the invisible layout grid.",
  "setup.composition.grid.draw_grid": "Whether the planning grid should appear in the image. Almost always false.",
  "setup.composition.primary_focal_point": "The main thing the viewer should notice first.",
  "setup.composition.left_to_right_order": "Ordered list of element IDs or prop IDs as they should appear from screen left to screen right.",
  "setup.composition.composition_notes": "Extra layout guidance that does not fit into a single field.",
  "setup.camera.shot_type": "Camera framing: close-up, medium shot, full-body shot, wide shot, establishing shot, etc.",
  "setup.camera.camera_height": "Camera height relative to subjects: low, eye-level, high, overhead.",
  "setup.camera.camera_angle": "Camera angle: straight-on, slight upward angle, slight downward angle, over-the-shoulder, etc.",
  "setup.camera.viewer_position": "Where the viewer/camera is positioned relative to the scene.",
  "setup.camera.lens_feel": "Broad lens impression: normal, wide, compressed/telephoto.",
  "setup.camera.focus_priority": "What the composition should prioritize: one character, two main characters, whole group, environment, or specific object.",
  "setup.camera.notes": "Extra camera or framing notes.",
  "setup.environment.location": "Where the scene takes place. Keep this visual and concrete.",
  "setup.environment.time_of_day": "Time of day if visually important.",
  "setup.environment.lighting": "Lighting direction, quality, and color.",
  "setup.environment.mood": "Emotional atmosphere conveyed by the image.",
  "setup.environment.weather_or_atmosphere": "Weather, haze, smoke, dust, fresh air, magical glow, or similar environmental conditions.",
  "setup.environment.general_foreground_notes": "Foreground details that support the scene without needing individual elements.",
  "setup.environment.general_background_notes": "Background details that support the scene without needing individual elements.",
  "setup.environment.important_exclusions": "Scene-level things that must not appear.",
  "setup.style.inherit_story_art_style": "Use the canonical art style from the story settings file.",
  "setup.style.art_style_override": "Scene-specific style override. Leave blank unless this scene intentionally differs from the story style.",
  "setup.style.dialogue_style_id": "ID of the story dialogue style used by this scene.",
  "setup.style.visual_continuity_override": "Scene-specific continuity note. Leave blank unless this scene intentionally contrasts with the story defaults.",
  "scene_elements[].id": "Stable internal ID for this element. Placements, interactions, references, and dialogue use this ID.",
  "scene_elements[].display_name": "Human-readable label shown in the UI and generated prompts.",
  "scene_elements[].element_type": "Type of visible thing: Character, Monster, Prop, or Anchor.",
  "scene_elements[].role": "Narrative or visual role in this scene, such as protagonist, threat, location anchor, offered object, or background feature.",
  "scene_elements[].importance": "How important this element is visually: primary, secondary, background, or extra.",
  "scene_elements[].source_refs.identity_source": "Path to canonical identity file for a recurring character or identity-sensitive element.",
  "scene_elements[].source_refs.costume_source": "Path to selected costume file for this scene.",
  "scene_elements[].source_refs.location_source": "Path to canonical location or architecture file for an Anchor.",
  "scene_elements[].source_refs.monster_source": "Path to canonical monster description file.",
  "scene_elements[].source_refs.prop_source": "Path to canonical prop description file.",
  "scene_elements[].reference_images[].tag": "Resolvable image reference tag used by Zet, such as {{ASSET:...}} or {{AUX:...}}.",
  "scene_elements[].reference_images[].roles": "What this reference image controls: identity, hair, costume, proportions, architecture, prop design, etc.",
  "scene_elements[].reference_images[].ignore": "What the renderer should ignore from the reference: pose, background, camera angle, lighting, framing.",
  "scene_elements[].scene_visual_override": "Scene-specific visual override. Use only for temporary scene-specific changes.",
  "scene_elements[].fallback_visual_description": "Short local visual description used only if no canonical source or reference is available.",
  "scene_elements[].notes": "Private notes for this element in this scene.",
  "placements[].id": "Stable placement ID. One scene element may have more than one placement if needed.",
  "placements[].scene_element_id": "The scene element this placement displays.",
  "placements[].screen_cell.row": "Planning grid row. Row 1 is the top row.",
  "placements[].screen_cell.column": "Planning grid column. Column 1 is the leftmost column.",
  "placements[].screen_cell.name": "Human-readable cell name, such as left, center, right, upper-left, or lower-center.",
  "placements[].semantic_screen_region": "Plain-language screen placement such as left foreground, center background, or lower-right midground.",
  "placements[].normalized_anchor.x": "Optional approximate horizontal position from 0.0 left to 1.0 right.",
  "placements[].normalized_anchor.y": "Optional approximate vertical position from 0.0 top to 1.0 bottom.",
  "placements[].position_within_cell": "Position inside the grid cell: center, left, right, upper, lower, upper-left, etc.",
  "placements[].depth": "Depth layer: foreground, midground, background, or distant background.",
  "placements[].z_order": "Draw/order priority. Higher values appear in front when overlap matters.",
  "placements[].frame_coverage": "How much of the element should be visible: full body, knees-up, waist-up, face only, large background architecture, etc.",
  "placements[].distance_from_camera": "Camera distance independent of narrative importance: foreground, midground, background, distant.",
  "placements[].visual_scale": "Relative visual size or physical scale. Use this to avoid mixing scale with importance.",
  "placements[].must_be_visible": "Whether this element must remain visibly readable in the final image.",
  "placements[].visible_body_requirements": "Specific parts that must be visible, such as face, hands, boots, wings, book, or weapon.",
  "placements[].pose.summary": "Concise pose summary.",
  "placements[].pose.temporary_condition": "Temporary state such as kneeling, falling, injured, floating, reaching, soaked, or exhausted.",
  "placements[].pose.body_view": "Body orientation relative to camera, such as front, front-left 3/4, left profile, back-left 3/4, back.",
  "placements[].pose.head_view": "Head orientation relative to camera or another element.",
  "placements[].pose.action_direction_screen": "Screen direction of action, such as toward screen left or toward center.",
  "placements[].pose.gaze_target_element_id": "Element ID that this element is looking at.",
  "placements[].pose.gaze_description": "Plain-language gaze instruction if the target ID alone is not enough.",
  "placements[].pose.expression": "Facial expression or visible emotional state.",
  "placements[].pose.left_arm_action": "What the anatomical left arm is doing.",
  "placements[].pose.right_arm_action": "What the anatomical right arm is doing.",
  "placements[].pose.left_hand_detail": "What the anatomical left hand is holding, touching, reaching for, or doing.",
  "placements[].pose.right_hand_detail": "What the anatomical right hand is holding, touching, reaching for, or doing.",
  "placements[].pose.leg_foot_detail": "Leg/foot stance, kneeling, balance, heel lift, visible feet, or stride details.",
  "placements[].pose.balance_weight_detail": "Weight distribution and balance cues when important.",
  "placements[].occlusion.occlusion_level": "How much this element is hidden by another element: none, partial, mostly hidden, behind foreground characters.",
  "placements[].occlusion.must_not_occlude": "Important details that must not be covered.",
  "placements[].occlusion.notes": "Extra overlap or visibility notes.",
  "placements[].placement_notes": "Private notes about this placement.",
  "props_and_states[].id": "Stable prop state ID. Use this for important props that need exact count, holder, state, or interaction.",
  "props_and_states[].scene_element_id": "Optional linked scene element ID if this prop is also listed as a reusable Scene Element.",
  "props_and_states[].display_name": "Human-readable prop label.",
  "props_and_states[].count": "Exact number of this prop represented by this entry.",
  "props_and_states[].owner_element_id": "Element ID of the owner, if story-relevant.",
  "props_and_states[].holder_element_id": "Element ID of the current holder, if any.",
  "props_and_states[].held_in_hand": "Which hand or arm holds the prop, if held.",
  "props_and_states[].state": "Open, closed, broken, glowing, upside down, sheathed, spilled, etc.",
  "props_and_states[].must_remain_visible": "Whether this prop must be clearly visible.",
  "props_and_states[].placement_hint": "Plain-language location for the prop.",
  "props_and_states[].notes": "Private notes about this prop state.",
  "interactions[].id": "Stable interaction ID.",
  "interactions[].subject_element_id": "Element initiating or owning the interaction.",
  "interactions[].action": "Action relationship, such as offers, attacks, protects, reaches toward, blocks, watches, or mutual eye contact.",
  "interactions[].prop_id": "Prop involved in the interaction, if any.",
  "interactions[].target_element_id": "Element receiving or targeted by the interaction.",
  "interactions[].source_hand": "Hand used by the subject, if relevant.",
  "interactions[].target_hand": "Hand used by the target, if relevant.",
  "interactions[].contact_state": "Whether contact occurs: no contact, touching, holding, striking, blocking, etc.",
  "interactions[].distance": "Important distance relationship, such as just outside reach, arm's length, across the room.",
  "interactions[].emotional_tone": "Emotional meaning of the interaction.",
  "interactions[].notes": "Private interaction notes.",
  "dialogue[].id": "Stable dialogue entry ID.",
  "dialogue[].speaker_element_id": "Element ID of the speaker.",
  "dialogue[].text": "Exact dialogue text to render. Keep punctuation final.",
  "dialogue[].tone": "How the line should feel emotionally.",
  "dialogue[].target_element_id": "Who the dialogue is addressed to, if anyone.",
  "dialogue[].include_in_final_image_prompt": "Whether this dialogue should be included in the final image prompt.",
  "dialogue[].include_in_local_render": "Whether local preview renders should include this dialogue. Usually false.",
  "dialogue[].panel_style_id": "Dialogue style ID from the story settings file.",
  "dialogue[].preferred_screen_region": "Where the dialogue panel should go if possible.",
  "dialogue[].pointer_target": "Where the dialogue pointer should aim, usually the speaker's mouth.",
  "dialogue[].max_lines": "Maximum preferred number of wrapped text lines.",
  "dialogue[].must_not_cover": "Faces, hands, props, or focal areas the panel must not cover.",
  "dialogue[].notes": "Private dialogue notes.",
  "reference_assignments[].id": "Stable reference assignment ID.",
  "reference_assignments[].tag": "Resolvable image reference tag.",
  "reference_assignments[].applies_to_element_id": "Scene element controlled by this reference.",
  "reference_assignments[].roles": "What the reference controls.",
  "reference_assignments[].ignore": "What to ignore from the reference.",
  "reference_assignments[].notes": "Private reference assignment notes.",
  "avoid.scene_specific": "Scene-specific negative prompt concepts and failure modes.",
  "avoid.notes": "Private notes about scene-specific avoid rules.",
  "render_settings.final_image_prompt.enabled": "Whether to generate the final image prompt artifact.",
  "render_settings.final_image_prompt.output_path": "Where to write the final image prompt markdown.",
  "render_settings.local_render_brief.enabled": "Whether to generate the local render brief JSON.",
  "render_settings.local_render_brief.output_path": "Where to write the local render brief.",
  "render_settings.local_render_prompt.enabled": "Whether to generate a local render prompt.",
  "render_settings.local_render_prompt.output_path": "Where to write the local render prompt.",
  "render_settings.scene_render_ir.enabled": "Whether to write the normalized scene render IR for debugging.",
  "render_settings.scene_render_ir.output_path": "Where to write the normalized scene render IR.",
  "metadata.created_at": "Timestamp when this file was created.",
  "metadata.updated_at": "Timestamp when this file was last saved.",
  "metadata.created_by": "Tool or feature that created this file."
}
```

---

# Scene Element Types

Allowed V3 element types:

```text
Character
Monster
Prop
Anchor
```

Meanings:

```text
Character
A named person or recurring identity-sensitive figure.

Monster
A creature, enemy, beast, demon, undead, construct, or other non-person threat. May still have recurring identity.

Prop
A movable object or important item: book, staff, sword, skull, potion, table, chair, corpse, scroll.

Anchor
A location-defining visual feature: doorway, archway, tower, bridge, statue, stair landing, throne, altar, pit, skyline.
```

Keep the data model open enough that `Prop` can be either:

1. a full `scene_element` with placements; or
2. a lighter entry in `props_and_states` when only count/holder/state matters.

Important props with exact screen position should become full `scene_elements`.

Handheld or counted props may be represented in `props_and_states`.

---

# UI Plan

Update the Scene Builder UI to V3.

Use the 3-column layout already planned.

```text
┌─────────────────────────────┬─────────────────────────────┬─────────────────────────────┐
│ Left Column                 │ Middle Column               │ Right Column                │
│ General Scene Settings      │ Grid Preview                 │ Elements + Detail Editor    │
│                             │                             │                             │
│ Setup                       │ Planning grid               │ Element List                │
│ Composition                 │ Placement labels            │ Add/Delete/Duplicate        │
│ Camera                      │ Depth badges                │                             │
│ Environment                 │ Selection handling          │ Element Properties          │
│ Style                       │                             │ Placement Fields            │
│ Render Settings             │                             │ Pose / Hands / Props        │
│                             │                             │ Dialogue / References       │
└─────────────────────────────┴─────────────────────────────┴─────────────────────────────┘
```

## Left Column

Sections:

```text
Scene
Canvas
Composition
Camera
Environment
Style
Render Settings
Validation
```

## Middle Column

Show the grid preview.

Requirements:

* current grid rows and columns
* cell labels
* scene element labels in each cell
* depth badges
* placement selection
* active cell selection
* no actual rendered preview required

Click behavior:

1. Select element in right column.
2. Click grid cell.
3. If selected element has no placement, create placement in that cell.
4. If selected element has one placement, move it to that cell.
5. If selected element has multiple placements, select the relevant placement or use explicit “Add Placement.”

## Right Column

Top:

```text
Scene Element List
[Add Element]
[Delete Selected]
[Duplicate]
[Add Placement]
[Delete Placement]
```

List rows should show:

```text
Display Name | Type | Importance | Placement Count
```

Bottom editor should use tabs or collapsible groups:

```text
Element
References
Placement
Pose / Hands
Props
Interactions
Dialogue
Avoid
```

For `Prop` and `Anchor`, de-emphasize character-specific pose fields but do not remove them from the data model.

For `Character` and `Monster`, emphasize:

* body view
* head view
* gaze
* expression
* hands/arms
* leg/foot details
* temporary condition

---

# Story Settings Editor

Add a small Story Settings editor.

It should edit `.story.json`, not the story `.md`.

Minimum UI:

```text
Story
Art Style
Visual Continuity
Dialogue Styles
Compiler Profiles
Scene Index
```

Optional convenience feature:

```text
Import from Story Markdown Compiler Sections
```

If implemented, this should be a one-time/manual import tool only. Do not make the compiler parse story markdown automatically.

Manual import can look for old bounded markdown sections:

```text
<!-- ZET:BEGIN STORY_TITLE -->
<!-- ZET:BEGIN CANONICAL_ART_STYLE -->
<!-- ZET:BEGIN STORY_PREMISE -->
<!-- ZET:BEGIN STORY_VISUAL_CONTINUITY -->
```

Then populate `.story.json`.

This is not a migration system. It is just an import helper.

---

# Compiler Plan

Create a normalized Prompt Scene IR before producing any renderer-specific output.

## Inputs

```text
Scene V3 JSON
Story Settings JSON
Referenced character/costume/location/monster/prop source files
Resolved image/reference tags
Compiler profile
```

## Output 1: Scene_Render_IR.json

This is a backend-neutral compiled object.

Suggested structure:

```json
{
  "source": {
    "scene_json_path": "",
    "story_settings_path": "",
    "source_hashes": {}
  },
  "canvas": {},
  "style": {},
  "composition": {},
  "camera": {},
  "environment": {},
  "elements": [],
  "placements": [],
  "props": [],
  "interactions": [],
  "dialogue": [],
  "references": [],
  "avoid": [],
  "final_verification": []
}
```

## Output 2: Final_Image_Prompt.md

Generate sections in this order:

```markdown
# Render Task

# Reference Image Assignment

# Camera and Composition

# Character and Monster Staging

# Props and Interactions

# Environment and Depth

# Lighting and Mood

# Dialogue Panel

# Must Preserve

# Avoid

# Final Verification
```

Only include `# Dialogue Panel` when `dialogue` exists and `include_in_final_image_prompt` is true.

## Output 3: Local_Render_Brief.json

Generate a compact local-render brief.

It should include:

```json
{
  "purpose": "composition preview only",
  "include_dialogue": false,
  "protected_facts": {},
  "positive_facts": [],
  "negative_facts": []
}
```

Local render should usually exclude:

* dialogue panel text
* long story premise
* markdown compiler notes
* raw reference tags
* ChatGPT-specific instructions

## Output 4: Local_Render_Prompt.md

Generate a local prompt from `Local_Render_Brief.json`.

Do not condense `Final_Image_Prompt.md`.

---

# Important Compiler Rules

## Prompt Precedence

From highest to lowest priority:

```text
1. explicit scene-specific override
2. structured scene placement, interaction, dialogue, prop fields
3. selected costume/source files
4. canonical character/location/monster/source files
5. element fallback visual description
6. story settings defaults
7. generic rendering defaults
```

## Do Not Store Generated Prompt Text in Scene JSON

Do not store:

```json
"generation_outputs": {
  "scene_brief": "",
  "positive_prompt": "",
  "negative_prompt": ""
}
```

in the source scene file.

Instead, generated outputs go to files defined in `render_settings`.

The scene JSON may store output paths and metadata, but not the generated prompt content.

---

# Validation

Implement V3 validation.

Minimum warnings/errors:

## Scene and Story

* missing scene ID
* missing scene name
* missing story settings path
* story settings path does not exist
* missing associated output path if render is enabled
* invalid schema version
* invalid file kind

## Setup

* invalid orientation
* invalid aspect ratio
* grid rows or columns less than 1
* `draw_grid` true with warning unless explicitly allowed
* missing primary focal point
* missing location
* missing lighting
* missing mood

## Scene Elements

* no scene elements
* duplicate element ID
* invalid element type
* invalid importance
* primary element has no placement
* Character or Monster missing source reference and fallback description
* Anchor missing location source, reference image, or fallback description

## Placements

* placement references missing scene element
* placement row/column outside grid
* duplicate placement ID
* foreground/background contradiction
* primary Character or Monster placed only in distant background
* must_be_visible true but no visibility requirements
* expression specified on Prop or Anchor should warn but not fail
* body/head/gaze missing for primary Character or Monster

## Pose and Hands

* hand-specific interaction exists but matching hand detail is blank
* prop claims to be held by a hand that pose fields do not mention
* contact_state conflicts with pose text
* left/right hand mismatch between interaction and pose

## Props

* exact counted prop has no state
* prop must remain visible but has no placement hint
* duplicate counted prop IDs
* central interaction references missing prop

## Dialogue

* dialogue speaker missing
* dialogue text blank
* dialogue included in final prompt but no dialogue style found
* dialogue panel has no pointer target
* dialogue must_not_cover is empty
* local render includes dialogue while local compiler profile says dialogue should be excluded

## References

* reference assignment applies to missing element
* reference assignment has no roles
* reference assignment has no ignore list
* primary Character or Monster has no reference image and no source file

## Avoid Rules

* missing scene-specific avoid list should warn only
* story default avoid not found should warn only

---

# File Operations

Implement clean V3 file helpers.

Suggested functions:

```python
def get_story_settings_path_from_story_md(story_md_path: Path) -> Path:
    return story_md_path.with_suffix(".story.json")
```

```python
def get_scene_json_path_from_scene_slug(scene_dir: Path, scene_slug: str) -> Path:
    return scene_dir / f"{scene_slug}.scene.json"
```

```python
def create_default_story_settings(story_md_path: Path | None = None) -> dict:
    ...
```

```python
def create_default_scene_v3(story_settings_path: Path | None = None) -> dict:
    ...
```

```python
def load_story_settings(path: Path) -> dict:
    ...
```

```python
def load_scene_v3(path: Path) -> dict:
    ...
```

```python
def save_story_settings(path: Path, data: dict) -> None:
    ...
```

```python
def save_scene_v3(path: Path, data: dict) -> None:
    ...
```

```python
def validate_story_settings(data: dict) -> list[ValidationMessage]:
    ...
```

```python
def validate_scene_v3(data: dict, story_settings: dict | None = None) -> list[ValidationMessage]:
    ...
```

```python
def compile_scene_render_ir(scene_data: dict, story_settings: dict, resolved_sources: dict) -> dict:
    ...
```

```python
def write_final_image_prompt(ir: dict, output_path: Path) -> None:
    ...
```

```python
def write_local_render_brief(ir: dict, output_path: Path) -> None:
    ...
```

```python
def write_local_render_prompt(local_brief: dict, output_path: Path) -> None:
    ...
```

Use equivalent language/framework functions if this area of Zet is not Python.

---

# UI Enum Suggestions

Use these enum values.

## Orientation

```text
landscape
portrait
square
comic panel
custom
```

## Element Type

```text
Character
Monster
Prop
Anchor
```

## Importance

```text
primary
secondary
background
extra
```

## Depth

```text
foreground
midground
background
distant background
```

## Body / Head View

```text
front
front-left 3/4
front-right 3/4
left profile
right profile
back-left 3/4
back-right 3/4
back
toward another element
custom
```

## Shot Type

```text
close-up
medium shot
full-body shot
wide shot
establishing shot
comic panel shot
```

## Camera Height

```text
low
eye-level
high
overhead
```

## Lens Feel

```text
normal
wide
compressed / telephoto
```

## Contact State

```text
no contact
touching
holding
grabbing
striking
blocking
supporting
custom
```

---

# New Stories, Scenes

Update the shared templates C:\Users\Joe\Projects\Zet_Library\Stories\_Scene_Template.md and C:\Users\Joe\Projects\Zet_Library\Stories\_Story_Template.md to align with V3. 

Make sure Add Story and Add Scene functions initalize V3 a new story from the Stories page and a V3 new scene from the Scenes page respectively.

---

# Tests / Manual Verification

Add automated tests where practical. Otherwise provide manual test checklist.

## Story Settings

1. Create `FirstDay.story.json`.
2. Confirm it saves with `schema_version: 1`.
3. Confirm dialogue style can be added and edited.
4. Confirm canonical art style can be edited.
5. Confirm scene index can list a `.scene.json`.

## Scene V3

1. Create `Chapter-04-A-Lending-Hand.scene.json`.
2. Confirm it saves with `schema_version: 3` and `file_kind: scene`.
3. Add story settings path.
4. Add Character, Character, Anchor.
5. Add placements for all three.
6. Add prop states for five books.
7. Add interaction for offered book.
8. Add dialogue entry.
9. Add reference assignments.
10. Save and reload.
11. Confirm all nested fields survive round trip.

## Grid

1. Set grid to 3 columns x 1 row.
2. Place Valindia in left cell.
3. Place Spire archway in center cell.
4. Place Tsaeytte in right cell.
5. Confirm grid preview labels match.

## Compiler

1. Compile scene.
2. Confirm `Scene_Render_IR.json` is written.
3. Confirm `Final_Image_Prompt.md` is written.
4. Confirm `Local_Render_Brief.json` is written.
5. Confirm `Local_Render_Prompt.md` is written.
6. Confirm dialogue appears in final prompt but not local render brief.
7. Confirm story art style appears in final prompt.
8. Confirm dialogue panel style appears only when dialogue exists.
9. Confirm generated files are not stored inside scene JSON.

## Validation

Verify warnings for:

* missing story settings file
* missing focal point
* missing lighting
* duplicate element ID
* placement references missing element
* interaction references missing prop
* dialogue speaker missing
* local render dialogue conflict
* primary Character with no placement
* primary Character missing gaze
* Prop with expression does not crash compiler
* Anchor with no pose does not generate awkward character wording

---

# Acceptance Criteria

This work is complete when:

1. Zet supports `.story.json` story settings files.
2. Zet supports `.scene.json` Scene Builder V3 files.
3. The scene `.json` is the canonical source of scene layout and staging.
4. Scene `.md` is no longer required as an input to the scene compiler.
5. Story `.md` remains a human-authored file and is not parsed during normal scene compilation.
6. Story-wide art style and dialogue panel style come from `.story.json`.
7. Scene-specific dialogue is stored in scene JSON.
8. Scene elements support Character, Monster, Prop, and Anchor.
9. Placements are top-level and link to scene elements by ID.
10. Pose, hands, props, interactions, references, and dialogue are first-class structured data.
11. Generated outputs are written as compiler artifacts, not stored as editable scene data.
12. The Scene Builder UI has the 3-column layout.
13. Helper/popup text exists for all user-facing fields.
14. The compiler creates `Scene_Render_IR.json`, `Final_Image_Prompt.md`, `Local_Render_Brief.json`, and `Local_Render_Prompt.md`.
15. Validation catches the main scene-building mistakes without blocking normal drafting.
16. No V1/V2 migration code is added.
17. Existing non-Scene-Builder Zet behavior remains intact.

---

# Non-Goals

Do not implement:

* V1/V2 migration
* automatic parsing of story markdown during normal compilation
* full top-down plan view
* 3D staging
* ComfyUI workflow export
* automatic image analysis
* automatic character source discovery
* complex drag-and-drop if click/select is faster
* generated image comparison
* prompt-history database

Focus on clean V3 source ownership, structured scene definition, helper text, and compiler outputs.
