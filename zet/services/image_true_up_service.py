"""Intent-aware visual comparison and correction preparation for both hosts."""
from __future__ import annotations

import json

from zet.services.image_reconstruction_contract import (
    CATEGORIES, correction_items, target_instructions, validate_report,
)


_STRING = {"type": "string"}
_ITEM_PROPERTIES = {key: _STRING for key in ("feature", "evidence", "expected", "observed", "correction")}
_ITEM_PROPERTIES.update(category={"type": "string", "enum": list(CATEGORIES)},
                        visibility={"type": "string", "enum": ["visible", "occluded", "uncertain"]},
                        severity={"type": "string", "enum": ["minor", "major", "info"]})
REPORT_SCHEMA = {"type": "object", "properties": {
    "summary": _STRING, "items": {"type": "array", "items": {
        "type": "object", "properties": _ITEM_PROPERTIES,
        "required": list(_ITEM_PROPERTIES), "additionalProperties": False}}},
    "required": ["summary", "items"], "additionalProperties": False}


class ImageTrueUpService:
    INSTRUCTION_VERSION = 5

    def __init__(self, ask):
        self.ask = ask

    def compare(self, model, target, images, context):
        prompt = (
            "Compare image 1 (candidate) with the ordered source evidence, and an approved front if labeled. "
            "Evaluate against the TARGET CONTRACT, never an unconditional source match. Explicit edits take "
            "precedence: absent removed equipment is intentional_change_satisfied, not drift. Evaluate "
            "edits against the latest operator feedback in the task context when supplied; that feedback "
            "can intentionally override earlier target direction. For other views the approved front "
            "establishes the completed design. Report missed "
            "edits separately. Compare facial proportions, hair silhouette/length using facial landmarks, "
            "anatomical sides, body build and stable costume construction. "
            "Check actual visible coverage and construction, not just a broad costume resemblance: cropped "
            "versus covered midriff, bare thighs versus added trousers, skirt layers/hem, knee guards and "
            "boot height/armor, and clasp/jewelry shape, color and material. A leather outfit and cloak can "
            "still differ substantially at those landmarks. Inspect source and candidate rather than "
            "assuming the requested prompt was satisfied; report each visible mismatch separately. "
            "Do not penalize a requested style, pose or camera change. Occluded/uncertain details are "
            "not_evaluable, with no correction. "
            "Do not turn the face toward camera to reveal hidden identity features. Only visible accidental "
            "drift, missing edits and style/view problems receive actionable corrections. Evidence must cite "
            "an image role/number and visible feature; never invent an identity score.\n"
            + target_instructions(target) + "\nImage roles and requested view:\n" + json.dumps(context))
        return validate_report(self.ask(model, prompt, REPORT_SCHEMA, images))

    def correction(self, model, target, report, item_ids, instructions, context):
        items = correction_items(report, item_ids, instructions)
        return "\n\n".join(filter(None, [
            "Edit the provided candidate image. Change only the requested details and preserve everything "
            "else, including its face, identity, style and costume. The latest operator feedback takes "
            "precedence over earlier direction and suggested corrections wherever they differ. Earlier "
            "intentional edits, such as removed equipment, remain in effect unless explicitly changed. "
            "Original images are comparison evidence only.",
            "Earlier requested changes (retain unless explicitly overridden below):\n" + target["change_text"],
            "Selected suggestions:\n" + "\n".join(item["correction"] for item in items) if items else "",
            "Operator feedback:\n" + instructions if instructions.strip() else "",
            context,
        ]))
