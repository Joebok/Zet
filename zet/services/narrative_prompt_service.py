"""Short narrative instructions and deterministic reference bindings."""
import json


def object_schema(properties: dict) -> dict:
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


TEXT = {"type": "string"}
INTERVIEW_SCHEMA = object_schema({
    "narrative": TEXT, "staging": TEXT, "physical_context": TEXT, "framing": TEXT,
    "questions": {"type": "array", "maxItems": 2, "items": TEXT},
})
PROMPT_SCHEMA = object_schema({"scene": {"type": "string", "maxLength": 1600},
                               "rendering": {"type": "string", "maxLength": 1000}})


def llm_request(detail: dict, kind: str, message: str = "") -> tuple[str, dict]:
    # Whole-scene intent can describe actors and events outside this target.
    # Supply only this target's direction and the inherited visual context.
    context = {key: detail[key] for key in ("title", "kind", "narrative", "staging", "physical_context", "framing", "context")}
    context["elements"] = [{key: item.get(key, "") for key in ("id", "name", "kind", "appearance", "reference_role", "reference")}
                           for item in detail["elements"]]
    context["reference_images"] = [{"image_index": index, "name": item["name"], "role": item["reference_role"]}
                                   for index, item in enumerate((el for el in detail["elements"] if el["asset_id"]), 1)]
    if kind == "interview":
        instructions = (
            "You are an illustrator interviewing a scene director. Write coherent, editable prose about one visible instant. "
            "Describe participants responding to each other, not independent poses. Preserve supplied people, props, and facts. "
            "For a backdrop describe the environment; do not add people. Infer ordinary staging confidently. "
            "Ask at most two questions only when their answers materially change the image. Never ask for facts already supplied "
            "by scene context or references, technical fields, coordinates, or approval of your writing. Questions are optional; "
            "produce usable draft fields even when asking questions. Do not invent significant props, identities or costumes. "
            "Apply the user's latest direction and use interview history to avoid repeating answered questions. "
            "Return narrative, staging, physical_context, framing and questions as JSON."
        )
        context["history"] = detail["interview"]
        schema = INTERVIEW_SCHEMA
    else:
        instructions = (
            "Write a concise Qwen Image 2.1 illustration prompt as JSON with scene and rendering paragraphs. "
            "Begin with 'Create a new illustration' and use supplied images only for their stated roles. "
            "Integrate narrative, reactions, gestures, staging, important props, framing and visibility into one coherent event. "
            "Preserve named participants and essential facts. Use narrative direction over generic aesthetics. "
            "References preserve identity and costume, not source pose, gaze or camera. Do not invent extra people or significant props. "
            "Only reference_images identifies supplied images. Other elements have text directions only. Do not claim that a "
            "text-only prop or subject has a supplied image. Do not mention image numbers or describe reference bindings in your paragraphs. "
            "Keep the scene paragraph under 150 words and the rendering paragraph under 80 words. "
            "Use inherited camera, perspective, lighting and style. For a subscene omit surrounding architecture except surfaces "
            "necessary for the action and use a plain neutral background. For a backdrop depict the environment and only the "
            "deliberately assigned subjects. Eliminate redundant or contradictory wording. Do not write reference bindings or "
            "add master-canvas placement coordinates; these are supplied separately."
        )
        schema = PROMPT_SCHEMA
    return instructions + "\n\nCurrent inputs:\n" + json.dumps(context, ensure_ascii=False) + "\n\nLatest direction:\n" + message, schema


def assemble_prompt(detail: dict, prose: dict, references: list[dict]) -> str:
    if not all(isinstance(prose.get(key), str) and prose[key].strip() for key in ("scene", "rendering")):
        raise ValueError("The LLM returned no usable scene or rendering prose.")
    bindings = []
    referenced_elements = [item for item in detail["elements"] if item["asset_id"]]
    for index, reference in enumerate(references, 1):
        role = reference["role"]
        if role == "appearance":
            purpose = ("Preserve recognizable identity and clothing; source pose, gaze and camera are not authoritative."
                       if referenced_elements[index - 1]["kind"] == "subject" else
                       "Preserve defining physical appearance; source placement and composition are not authoritative.")
        else:
            purpose = f"Use for {role}; do not copy unrelated subjects or composition."
        bindings.append(f"<image{index}> depicts {reference['label']}. {purpose}")
    subjects = [item["name"] for item in detail["elements"] if item["kind"] == "subject"]
    constraints = [f"Exactly {len(subjects)} named subjects: {', '.join(subjects)}. Each appears once; no extra people."
                   if subjects else "No people or additional characters."]
    constraints.append(f"Framing: {detail['framing']}. Canvas: {detail['width']} × {detail['height']} pixels.")
    if detail["kind"] == "subscene":
        constraints.append("Plain neutral background. Keep required silhouettes and gestures visible; do not crop required body parts.")
    operation = "Create an environment-only illustration with no people or characters.\n" if detail["kind"] == "backdrop" and not subjects else ""
    return (f"Scene\n{operation}{prose['scene'].strip()}\n\nReferences\n" + ("\n".join(bindings) or "No reference images.")
            + f"\n\nRendering\n{prose['rendering'].strip()}\n\nConstraints\n" + "\n".join(constraints))
