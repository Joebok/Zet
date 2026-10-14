"""Short narrative instructions and deterministic reference bindings."""
import json
import re

from zet.services.narrative_interview_service import FIELD_PURPOSES, MOMENT_FIELDS, VISUAL_FIELDS


def object_schema(properties: dict) -> dict:
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


TEXT = {"type": "string"}
INTERVIEW_SCHEMA = object_schema({
    "proposals": {"type": "array", "items": object_schema({
        "scope": {"type": "string", "enum": ["moment", "appearance", "visual"]},
        "field": {"type": "string", "enum": [*MOMENT_FIELDS, "appearance", *VISUAL_FIELDS]},
        "element_id": TEXT, "text": TEXT, "reason": TEXT,
    })},
    "conflicts": {"type": "array", "items": TEXT},
    "questions": {"type": "array", "maxItems": 2, "items": TEXT},
})
PROMPT_SCHEMA = object_schema({"scene": TEXT, "rendering": TEXT})


def llm_request(detail: dict, kind: str, message: str = "") -> tuple[str, dict]:
    # Whole-scene intent can describe actors and events outside this target.
    # Supply only this target's direction and the inherited visual context.
    context = {key: detail[key] for key in ("title", "kind", "narrative", "staging", "physical_context", "framing", "context")}
    context["shared_visual_context"] = detail.get("inherited_context", detail["context"])
    context["local_overrides"] = detail.get("visual_overrides", {})
    context["visual_sources"] = {key: "override" if context["local_overrides"].get(key) else "shared" for key in VISUAL_FIELDS}
    context["field_purposes"] = FIELD_PURPOSES
    context["canvas"] = {"width": detail["width"], "height": detail["height"]}
    context["elements"] = [{key: item.get(key, "") for key in ("id", "name", "kind", "appearance", "reference_role", "reference")}
                           for item in detail["elements"]]
    context["reference_images"] = [{"image_index": index, "name": item["name"], "role": item["reference_role"]}
                                   for index, item in enumerate((el for el in detail["elements"] if el.get("reference")), 1)]
    backdrop_source = detail["kind"] == "backdrop" and detail.get("source_snapshot", {}).get("image_file")
    if backdrop_source:
        source = detail["source_snapshot"]
        context["source_backdrop"] = {key: source.get(key) for key in ("title", "prompt", "generation_inputs", "current_inputs")}
        context["adaptation"] = detail.get("backdrop_adaptation", {})
        context["canvas"] = {"width": detail["width"], "height": detail["height"]}
        for ref in context["reference_images"]:
            ref["image_index"] += 1
        context["reference_images"].insert(0, {"image_index": 1, "name": source["title"], "role": "backdrop source"})
    if detail["kind"] == "assembly":
        context["elements"] = []
        context["source_groups"] = detail.get("source_groups", [])
        context["reference_images"] = [{"image_index": 1, "name": "Placed final scene", "role": "composition"}]
        if detail.get("assembly_mode") == "assemble_references":
            context["reference_images"] = [{key: value for key, value in ref.items() if key != "path"}
                                           for ref in detail.get("assembly_references", [])]
            context["canvas"] = {"width": detail["width"], "height": detail["height"]}
    if kind == "interview":
        instructions = (
            "You are an illustrator interviewing a scene director. Write coherent, editable prose about one visible instant. "
            "Describe participants responding to each other, not independent poses. Preserve supplied people, props, and facts. "
            "For a backdrop describe the environment; do not add people. Infer ordinary staging confidently. "
            "Ask at most two questions only when their answers materially change the image. Never ask for facts already supplied "
            "by scene context or references, technical fields, coordinates, or approval of your writing. Questions are optional; "
            "produce usable draft fields even when asking questions. Do not invent significant props, identities or costumes. "
            "Apply the user's latest direction and use interview history to avoid repeating answered questions. "
            "Return proposals, conflicts and questions as JSON."
        )
        context["history"] = detail["interview"]
        schema = INTERVIEW_SCHEMA
    else:
        instructions = (
            "Write a concise Qwen Image 2.1 illustration prompt as JSON with scene and rendering paragraphs. "
            "Begin with 'Create a new illustration' and use supplied images only for their stated roles. "
            "Integrate narrative, reactions, gestures, staging, important props, framing and visibility into one coherent event. "
            "Preserve named participants and essential facts. Use narrative direction over generic aesthetics. "
            "Use exact supplied element names when introducing participants and describing their actions. "
            "Repeat the actor's name for gestures, held objects, effects and interactions whenever ownership could be ambiguous. "
            "Avoid ownerless action fragments and ambiguous pronouns; clearly name whose hand holds an object or creates an effect. "
            "References preserve identity and costume, not source pose, gaze or camera. Authored equipment omissions or "
            "changes take precedence over reference gear. Do not invent extra people or significant props. "
            "Only reference_images identifies supplied images. Other elements have text directions only. Do not claim that a "
            "text-only prop or subject has a supplied image. Do not mention image numbers or describe reference bindings in your paragraphs. "
            "Write the shortest complete prompt without weakening or dropping supplied facts. Preserve explicit equipment "
            "and weapon exclusions, anatomy, gesture ownership and the strength of every relative-height comparison "
            "(for example 'head and shoulders taller', not just 'taller'). Explain height using supplied comparisons, "
            "ground plane and depth; never infer physical height from reference-image framing. Put action in scene and "
            "visual treatment in rendering, without repeating action in rendering. "
            "Use effective camera, perspective, lighting and style from context, which already applies local overrides. "
            "Do not reintroduce shared values replaced by an active override. For a subscene omit surrounding architecture except surfaces "
            "necessary for the action and use a plain neutral background. For a backdrop depict the environment and only the "
            "deliberately assigned subjects. Eliminate redundant or contradictory wording. Do not write reference bindings or "
            "add master-canvas placement coordinates; these are supplied separately."
        )
        schema = PROMPT_SCHEMA
    if detail["kind"] == "assembly":
        instructions = (
            "You are finishing an already assembled illustration. Preserve the supplied complete groups, identities, "
            "poses, props, camera, scale, placement and environment. Describe the overall visible moment and coherent "
            "lighting, joins and contact shadows. Do not restage, redraw or add participants. Do not request a neutral "
            "background or describe numeric layer coordinates. The supplied image is the placed final composition. "
            + ("Return proposals, conflicts and at most two optional questions as JSON."
               if kind == "interview" else "Return concise scene and rendering paragraphs as JSON. Do not write image bindings.")
        )
        if detail.get("assembly_mode") == "assemble_references":
            instructions = (
                "Assemble a coherent illustration from separate original background and subscene references. "
                "Preserve identities, clothing, poses, props and internal group arrangements. Redraw only as needed "
                "to integrate edges, lighting and contact shadows. Discard unrelated group backgrounds and floors. "
                "Follow the supplied source rectangle placement, scale, backdrop fit and back-to-front order; "
                "do not restage or add participants. Source groups without reference_images are planning context only. "
                "Do not claim a composite image is supplied. Numeric placement and image bindings are appended separately. "
                + ("Return proposals, conflicts and at most two optional questions as JSON."
                   if kind == "interview" else "Return concise scene and rendering paragraphs as JSON. Do not write image bindings.")
            )
    if backdrop_source:
        if kind != "interview":
            instructions = instructions.replace("Begin with 'Create a new illustration'", "Begin with an instruction to adapt the supplied backdrop")
        instructions += (" Adapt the supplied backdrop, preserving its recognizable setting and architecture. "
                         "Apply the adaptation direction, output dimensions and requested expansion side or changed viewpoint. "
                         "Source text is historical context; current destination direction takes precedence. "
                         "Do not preserve source framing when a viewpoint or expansion change is requested. "
                         "Describe an image edit rather than creating an unrelated environment. Do not add people unless deliberately assigned.")
    if kind == "interview":
        instructions += (
            " Propose whole-field replacements only for moment fields (narrative, staging, physical_context, framing), "
            "assigned elements' appearance, or visual fields (setting, camera, perspective, lighting, style). "
            "For appearance use scope='appearance', field='appearance' and the assigned element_id; for moment or visual "
            "use the corresponding scope/field and an empty element_id. text is the complete replacement; reason briefly "
            "explains the change. Omit unchanged fields. Keep identity, anatomy, clothing, intrinsic size and equipment "
            "changes in shared appearance notes; propose moving poses, expressions and interactions to moment fields. "
            "When moving information, propose both affected fields and explain the relationship. Analyze all supplied "
            "text for conflicting instructions, identifying fields in conflicts. Active local overrides intentionally "
            "replace shared values, so that difference alone is not a conflict. Resolve clear conflicts using the latest "
            "explicit user direction; preserve unresolved facts and ask at most two material questions when intent is "
            "unclear. Preserve weapon exclusions and exact relative-height comparisons. Current saved inputs are "
            "authoritative: history may contain rejected or unapplied proposals. Reference metadata is text only; you "
            "cannot inspect image anatomy, height or pose. Do not change names, references, membership, dimensions, models, "
            "assembly placement or source snapshots. Return proposals, conflicts and questions as JSON."
        )
    return instructions + "\n\nCurrent inputs:\n" + json.dumps(context, ensure_ascii=False) + "\n\nLatest direction:\n" + message, schema


def _bind_reference_names(prose: dict, references: list[dict]) -> dict:
    """Bind first element mentions using the frozen order sent to the image encoder."""
    tags = {}
    names = []
    for index, reference in enumerate(references, 1):
        if reference["role"] == "backdrop source":
            continue
        name = reference["label"].strip()
        key = name.casefold()
        if key in tags:
            raise ValueError(f"Ambiguous reference label '{name}': use distinct element names for each reference image.")
        tags[key] = f"<image{index}>"
        names.append(name)
    if not names:
        return prose
    # One pass prevents shorter names from matching inside already-bound longer names.
    pattern = re.compile(
        r"(?<!\w)(?P<name>" + "|".join(re.escape(name) for name in sorted(names, key=len, reverse=True))
        + r")(?!\w)(?P<possessive>['’]s(?!\w))?(?:[ \t]*<image\d+>)*", re.IGNORECASE)

    bound = set()

    def bind(match):
        name = match.group("name")
        key = name.casefold()
        suffix = "" if key in bound else " " + tags[key]
        bound.add(key)
        return name + (match.group("possessive") or "") + suffix

    return {**prose, **{key: pattern.sub(bind, prose[key]) for key in ("scene", "rendering")}}


def assemble_prompt(detail: dict, prose: dict, references: list[dict]) -> str:
    if not all(isinstance(prose.get(key), str) and prose[key].strip() for key in ("scene", "rendering")):
        raise ValueError("The LLM returned no usable scene or rendering prose.")
    if detail["kind"] == "assembly":
        if detail.get("assembly_mode") == "assemble_references":
            bindings = []
            for reference in references:
                tag = f"<image{reference['image_index']}>"
                if reference["role"] == "base":
                    placement = ("Use as the base background behind all groups. "
                                 + ("Fill the canvas, preserving aspect ratio and cropping centrally as needed."
                                    if reference["fit"] == "cover" else
                                    "Fit the complete background centrally, preserving aspect ratio; retain white margins where needed."))
                else:
                    placement = (f"Place its full source-image rectangle at top-left ({reference['x']}, {reference['y']}) pixels, "
                                 f"with size {reference['width']} × {reference['height']} pixels. "
                                 "Discard unrelated source backgrounds and floors; preserve the complete group within that rectangle.")
                bindings.append(f"{tag} depicts {reference['label']}. {placement}")
            groups = [f"<image{reference['image_index']}>" for reference in references if reference["role"] != "base"]
            depth = ("Back-to-front group order: " + ", ".join(groups) + ". Each later group is in front of earlier groups where they overlap.") if groups else ""
            return (f"Scene\nAssemble one coherent final illustration from the supplied sources. {prose['scene'].strip()}\n\nReferences\n"
                    + ("\n".join(bindings) or "No reference images supplied yet.")
                    + f"\n\nPlacement\nCoordinates use the canvas top-left as origin, with X rightward and Y downward. {depth} "
                    "Clip source rectangles at the canvas boundary; do not shift groups to bring off-canvas content into view.\n\n"
                    f"Rendering\n{prose['rendering'].strip()}\n\nConstraints\n"
                    "Preserve identities, clothing, poses, props and internal group arrangements. Do not add or duplicate participants. "
                    "Integrate edges, lighting and contact shadows naturally. Produce a complete image, not a collage of source backgrounds. "
                    f"Canvas: {detail['width']} × {detail['height']} pixels.")
        return (f"Scene\n{prose['scene'].strip()}\n\nReferences\n"
                "<image1> is the assembled final scene. Preserve its complete groups, poses, props, scale, placement and environment.\n\n"
                f"Rendering\n{prose['rendering'].strip()}\n\nConstraints\n"
                "Blend background joins and add contact shadows. Do not add, remove, resize, move or redraw subjects. "
                f"Keep the composition unchanged. Canvas: {detail['width']} × {detail['height']} pixels.")
    prose = _bind_reference_names(prose, references)
    bindings = []
    referenced_elements = [item for item in detail["elements"]
                           if item.get("asset_id") or item.get("reference_key")]
    element_index = 0
    for index, reference in enumerate(references, 1):
        role = reference["role"]
        if role == "backdrop source":
            bindings.append(f"<image{index}> is the original backdrop. Preserve its recognizable setting and architecture; apply the requested changes.")
            continue
        if role == "appearance":
            purpose = ("Preserve recognizable identity and clothing; source pose, gaze and camera are not authoritative."
                       if referenced_elements[element_index]["kind"] == "subject" else
                       "Preserve defining physical appearance; source placement and composition are not authoritative.")
        else:
            purpose = f"Use for {role}; do not copy unrelated subjects or composition."
        bindings.append(f"<image{index}> depicts {reference['label']}. {purpose}")
        element_index += 1
    subjects = [item["name"] for item in detail["elements"] if item["kind"] == "subject"]
    constraints = [f"Exactly {len(subjects)} named subjects: {', '.join(subjects)}. Each appears once; no extra people."
                   if subjects else "No people or additional characters."]
    constraints.append(f"Framing: {detail['framing']}. Canvas: {detail['width']} × {detail['height']} pixels.")
    if detail["kind"] == "subscene":
        constraints.append("Plain neutral background. Keep required silhouettes and gestures visible; do not crop required body parts.")
    if detail["kind"] == "backdrop" and detail.get("source_snapshot", {}).get("image_file"):
        adaptation = detail.get("backdrop_adaptation", {})
        constraints.append(f"Backdrop operation: {adaptation.get('operation', 'edit')}. {adaptation.get('direction', '')}")
        if adaptation.get("operation") == "expand":
            constraints.append(f"Expand the original environment toward {adaptation.get('expand_side', 'right')}; maintain visual continuity.")
    operation = "Create an environment-only illustration with no people or characters.\n" if detail["kind"] == "backdrop" and not subjects else ""
    if operation and detail.get("source_snapshot", {}).get("image_file"):
        operation = "Adapt the supplied environment-only backdrop with no people or characters.\n"
    return (f"Scene\n{operation}{prose['scene'].strip()}\n\nReferences\n" + ("\n".join(bindings) or "No reference images.")
            + f"\n\nRendering\n{prose['rendering'].strip()}\n\nConstraints\n" + "\n".join(constraints))
