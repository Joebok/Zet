"""Apply the authorized First Day pipeline test data through the existing API."""
import json
from pathlib import Path
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:8081"
SCENE = "/api/stories/FirstDay/scenes/Chapter-01-Standing-in-Wonder/builder"
OUT = Path(__file__).parent

def api(path, data=None, method=None):
    request = Request(BASE + path, data=json.dumps(data).encode() if data is not None else None,
                      headers={"Content-Type": "application/json"}, method=method)
    with urlopen(request, timeout=90) as response:
        return json.load(response)

data = api(SCENE)["document"]["data"]
boys = json.loads((OUT / "schoolboy-imports.json").read_text(encoding="utf-8-sig"))
target = next(s for s in data["subscenes"] if s["kind"] == "element" and s["anchor_element_id"] == "Schoolboys_440071c5")
target["name"] = "Schoolboys and Kaeldor"
target["setup"]["canvas"] = {"orientation": "landscape", "aspect_ratio": "4:3"}
target["setup"]["composition"] = {
    "focal_point": "The playful interaction between Schoolboy 1, Schoolboy 2, and Kaeldor",
    "left_to_right": ["schoolboy_1", "schoolboy_2", "Kaeldor_e02a5624"],
    "composition_notes": "Exactly three separate young elven males, all full body and clearly identifiable. Red-haired Schoolboy 1 at left gently shoves dark-haired Schoolboy 2 at center by the shoulder; Schoolboy 2 leans away, laughing, raising his hands in mock protest. Kaeldor at right grins and points at the two boys. Their hands and bodies remain distinct. No other people, no speech panels. A single captured moment of harmless horseplay, not a sequence of panels.",
}
target["setup"]["environment"]["location"] = "A simple stretch of the academy stone pathway, beyond the archway. No arch or buildings in this character-group reference."
target["setup"]["environment"]["general_background_notes"] = "Simple unobtrusive light background. This three-person group will be placed small in the background of the full scene."
group = next(e for e in data["scene_elements"] if e["id"] == "Schoolboys_440071c5")
group["reference_images"] = []
group["fallback_visual_description"] = "One group of exactly three elven academy students: red-haired Schoolboy 1, dark-haired Schoolboy 2, and Kaeldor."
group["element_visual_override"] = "Preserve all three distinct students and their playful interaction from the subscene reference. Schoolboy 1 gently shoves Schoolboy 2, who laughs; Kaeldor stands to their right, pointing and grinning. Render this group once in the background beyond the archway."
kaeldor = next(e for e in data["scene_elements"] if e["id"] == "Kaeldor_e02a5624")
kaeldor["subscene_id"] = target["id"]
kaeldor["element_visual_override"] = "Short light brown hair with shaved geometric sides, ivory open-collar shirt and burgundy waistcoat from his identity reference; grinning and pointing toward the schoolboys."
for boy in boys:
    number = boy["boy"]
    ident = f"schoolboy_{number}"
    description = ("Slim young elf with tousled copper-red hair and freckles" if number == 1
                   else "Young elf with olive skin, short dark hair, hazel eyes and a rounder face")
    data["scene_elements"].append({
        "id": ident, "display_name": f"Schoolboy {number}", "resource_type": "Person", "element_type": "Character",
        "subscene_id": target["id"], "reference_images": [{"asset_id": boy["asset_id"], "label": f"Schoolboy {number}",
        "roles": ["identity", "costume"], "preserve": ["face", "hair", "pointed ears", "academy clothing"],
        "ignore": ["source pose", "source background", "source framing"], "primary_prompt_source": True}],
        "fallback_visual_description": description + ", ivory shirt, burgundy waistcoat, charcoal trousers, brown boots.",
        "element_visual_override": "Gently pushing Schoolboy 2 at the shoulder while smiling" if number == 1 else "Leaning away from Schoolboy 1 with raised hands in mock protest and laughing",
    })
    data["placements"].append({"id": f"{ident}_placement", "scene_element_id": ident,
        "position_within_cell": "left" if number == 1 else "center", "depth": "midground",
        "pose": {"summary": "Extending one hand to Schoolboy 2's shoulder" if number == 1 else "Leaning sideways with both hands raised in playful protest",
                 "gaze_target_element_id": "schoolboy_2" if number == 1 else "schoolboy_1", "expression": "playfully amused"},
        "motion": {"state": "moving", "direction_screen": "right", "cue": "Harmless schoolboy horseplay"}})
for placement in data["placements"]:
    if placement["scene_element_id"] == "Kaeldor_e02a5624":
        placement.update(position_within_cell="right", depth="midground", world_position="To the right of both schoolboys in the group")
        placement["pose"] = {"summary": "Standing at the right, one hand pointing toward the schoolboys", "gaze_target_element_id": "schoolboy_2", "expression": "grinning"}
    elif placement["scene_element_id"] == "Schoolboys_440071c5":
        placement.update(world_position="Small three-person group beyond the arch, in the left-center background; Kaeldor is part of this group", placement_notes="Visible through the arch opening, clear of Tsaeytte and the dialogue box. Preserve exactly three students from the subscene; do not add a duplicate Kaeldor.")
    elif placement["scene_element_id"] == "Tsaeytte":
        placement["pose"].update(summary="Standing in the right foreground, viewed from behind at three-quarter angle, head tilted upward to read the arch inscription, holding a stack of books in both arms", gaze_target_element_id="Spire_Archway_a1489c35")
data["interactions"] += [
    {"id": "schoolboy_shove", "subject_element_id": "schoolboy_1", "relationship": "playfully shoves", "target_element_id": "schoolboy_2", "note": "One hand on the shoulder, harmless horseplay; Schoolboy 2 leans away laughing."},
    {"id": "kaeldor_points", "subject_element_id": "Kaeldor_e02a5624", "relationship": "points at", "target_element_id": "schoolboy_2", "note": "Kaeldor grins at the boys' antics from their right."},
]
data["setup"]["composition"]["left_to_right"] = ["Schoolboys_440071c5", "Tsaeytte"]
data["setup"]["composition"]["composition_notes"] = "Tsaeytte is the primary focus in the right foreground, seen from behind at three-quarter angle holding books, head tilted up to read the inscription across the top of the arch. The arch inscription and her upward gaze must be visible. Beyond the arch, one small group of exactly three students is goofing around: Schoolboy 1, Schoolboy 2, and Kaeldor on their right. Keep the whole group visible."
data["dialogue"][0]["notes"] = "Compact rectangular ivory parchment dialogue box beside Tsaeytte, with a small pointer to her mouth, exactly two lines: Potential is nothing / without discipline. Do not cover the arch inscription or the background group."
arch = next(e for e in data["scene_elements"] if e["id"] == "Spire_Archway_a1489c35")
arch["element_visual_override"] = 'Preserve the ornate academy archway and view of the Spire from the reference. The inscription across the upper arch reads "POTENTIAL IS NOTHING WITHOUT DISCIPLINE"; the inner arch reads "THE SPIRE OF CELESTIAL WISDOM". Keep the inscription visible above Tsaeytte.'
data["setup"]["environment"]["general_background_notes"] = "Beyond the archway, the Schoolboys subscene contains both schoolboys and Kaeldor as a single visible background group. Kaeldor appears once, within this group."
data["final_image_prompt_overrides"]["final_verification"] = "Tsaeytte looks upward at the arch inscription while holding books; her dialogue box reads exactly Potential is nothing without discipline; both individual schoolboys and Kaeldor appear in the background goofing around."
result = api(SCENE, data, "PUT")
(OUT / "configured-scene.json").write_text(json.dumps(result["document"]["data"], indent=2), encoding="utf-8")
print(result["message"])
print("subscene:", target["id"])
