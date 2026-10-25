"""Structured pilot evaluation, evidence-backed directions, and prompt authoring."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def verified_images(references):
    result = []
    for reference in references:
        path = Path(str(reference.get("path") or reference.get("image_path") or ""))
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != reference.get("sha256"):
            raise ValueError("A frozen input image is missing or changed. Restore it or start a fresh run.")
        result.append(path)
    return result


def object_schema(properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


TEXT = {"type": "string"}
TEXTS = {"type": "array", "items": TEXT}
SCORE = object_schema({"id": TEXT, "result": {"type": "string", "enum": ["pass", "fail", "unclear"]}, "explanation": TEXT})


class PilotAIReview:
    def __init__(self, service):
        self.service = service

    def generate(self, record, task):
        packet = record["packet"]
        round_record = next(r for r in record["history"] if r["id"] == task["round_id"])
        refs = packet.get("analysis_references", [])
        images = verified_images(refs)
        reference_map = [{k: r.get(k) for k in ("id", "role", "prompt_role", "view", "source_view", "label", "render_index", "audience")} for r in refs]
        context = {"target": {k: packet.get(k) for k in ("pipeline", "view", "costume", "facts", "required_constraints")},
                   "criteria": round_record["criteria_records"], "criteria_revision": round_record["criteria_revision"],
                   "references": reference_map, "rendered_prompt": round_record["prompt"]}
        context["target"]["rendering_mode"] = self.service._record_mode(record)
        if context["target"]["rendering_mode"] == "rotate":
            context["reference_strategy"] = (
                "Rotate the dressed edit base in Image 1 into the target view. Image 2 is the Assembly "
                "orientation, stance and framing reference only; never dress or copy its fitment clothing. "
                "Preserve the dressed source's identity and costume, subject to authored construction requirements.")
        if task["kind"] == "evaluation":
            attempt = next(a for a in round_record["attempts"] if a["id"] == task["attempt_id"])
            images += verified_images([attempt])
            context.update(attempt_id=attempt["id"], seed=attempt["seed"])
            schema = object_schema({"attempt_id": TEXT, "criteria_revision": {"type": "integer"},
                                    "criteria": {"type": "array", "items": SCORE}, "summary": TEXT})
            instruction = ("Evaluate ONLY the final attached image, the current pilot output. Earlier images are labeled references. "
                "Score every criterion ID exactly once using pass/fail/unclear and concrete visible evidence. "
                "Respect the target view, intentional asymmetry and occlusion. Use unclear when evidence is insufficient. "
                "Do not infer a pass from the prompt. Do not write a new prompt or refinement directions. "
                "Return the exact attempt_id and criteria_revision supplied below.")
            role = "prompt_generator_evaluation"
        else:
            attempts = self.service._attempts(round_record)
            images += verified_images(attempts)
            context["outputs_in_attachment_order"] = [{"id": a["id"], "seed": a["seed"],
                "ai_evaluation": a.get("ai_evaluation"), "human_conclusions": a.get("human_correction")}
                for a in attempts]
            context["prior_rounds"] = [{"round": r["round"], "prompt": r["prompt"],
                "results": [{"seed": a["seed"], "human_conclusions": a.get("human_correction")}
                            for a in self.service._attempts(r)]} for r in record["history"][:-1]]
            context["previous_approved_directions"] = [r.get("approved_text", "") for r in record.get("direction_history", [])]
            if task["kind"] == "direction":
                schema = object_schema({"direction": TEXT, "rationale": TEXT, "preserve": TEXTS, "evidence_ids": TEXTS})
                instruction = ("Propose concise editable directions for the next prompt, using the entire four-seed result set. "
                    "Human conclusions override your own assessment. Distinguish repeated defects from seed-specific variation. "
                    "Identify what should change, why, and successful attributes to preserve; cite supplied output IDs in evidence_ids. "
                    "Respect the frozen reference strategy, facts, compiler constraints and target view. "
                    "Do not propose source edits, reference replacement, or a different edit base. Do not write the final render prompt.")
                role = "prompt_generator_direction"
            else:
                if packet.get("instruction_modules") != self.service._instruction_modules(record["pipeline"], packet["operation"]):
                    raise ValueError("Prompt-authoring guidance changed after setup. Start a fresh run to use the new guidance.")
                context.update(packet_id=packet["packet_id"], packet_hash=packet["packet_hash"],
                               baseline_prompt=packet["baseline_prompt"], approved_directions=record["directions"]["approved_text"],
                               draft_feedback=record.get("draft_feedback", ""))
                schema = object_schema({"packet_id": TEXT, "packet_hash": TEXT, "prompt": TEXT,
                                        "reference_ids": TEXTS, "proposals": TEXTS, "summary": TEXT})
                instruction = ("Write the complete final render prompt following the human-approved directions. "
                    "Use compiler facts and only the frozen renderer bindings. Cite renderer images using their exact {{REF:id}} token; "
                    "analysis references and pilot outputs must not be cited as renderer attachments. "
                    "Preserve every required compiler constraint VERBATIM, including clauses using literal Image N wording. "
                    "Return the supplied packet_id and packet_hash unchanged and list exactly the reference IDs cited. "
                    "Describe changes concisely in summary for approval without reading the full prompt. "
                    "Never change source facts. Put any durable suggestions separately in proposals.")
                role = "prompt_generator"
        answer, runtime = self.service.app.ai_proxy_service.ai_proxy_path_service.jobs.generate_json(
            task["model"], "", instruction + "\n" + json.dumps(context, ensure_ascii=False), schema, images,
            task_type="local_prompt_generator_" + task["kind"], role=role,
            render_context={"operation": packet["operation"], "pipeline": record["pipeline"], "bindings_owned_by_zet": True},
            workflow=record["pipeline"], owner={**self.service._owner(record), "phase": task["kind"]})
        if task["kind"] == "evaluation":
            expected = {c["id"] for c in round_record["criteria_records"]}
            scores = answer.get("criteria") or []
            if (answer.get("attempt_id") != task["attempt_id"] or answer.get("criteria_revision") != task["criteria_revision"]
                    or len(scores) != len(expected) or {c.get("id") for c in scores} != expected
                    or any(c.get("result") not in {"pass", "fail", "unclear"} for c in scores)):
                raise ValueError("AI evaluation did not match this image and criterion revision.")
        elif task["kind"] == "direction":
            if not str(answer.get("direction") or "").strip() or set(answer.get("evidence_ids") or []) - {a["id"] for a in attempts}:
                raise ValueError("Suggested directions contain empty text or unknown image evidence.")
        return answer, runtime
