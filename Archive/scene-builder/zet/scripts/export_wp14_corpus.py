"""Export the versioned WP14 corpus without copying private library media.

The exporter snapshots the production prompt/schema sources at export time. By
default it emits portable synthetic image descriptors; a private export may
replace those descriptors with paths under MODELUPDATER_FIXTURE_ROOTS.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from zet.services.image_quality_review_service import ImageQualityReviewService
from zet.services.scene_builder_interview_service import (
    SceneBuilderInterviewService,
    _QUESTION_SCHEMA,
    _array,
    _object,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = PROJECT_ROOT.parent / "ModelUpdater" / "fixtures"
CORPUS_VERSION = 1
SCENE_PHASES = ("elements", "story", "canvas", "environment", "composition", "placements", "relationships")
CASE_PHASES = {"SB-01": "story", "SB-03": "elements", "SB-04": "relationships", "LG-01": "story", "IN-01": "story"}


def _read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def _scene_contracts() -> dict[str, dict[str, Any]]:
    service = SceneBuilderInterviewService.__new__(SceneBuilderInterviewService)
    phases = {item["key"]: item for item in service._phases()}
    contracts = {}
    for key in SCENE_PHASES:
        phase = phases[key]
        contracts[key] = {
            "source": "zet/services/scene_builder_interview_service.py",
            "system_prompt": SceneBuilderInterviewService.SYSTEM_PROMPT,
            "phase_instruction": phase["instruction"],
            "schema": _object({
                "result": phase["result_schema"],
                "questions": _array(_QUESTION_SCHEMA),
            }),
        }
    return contracts


def _contracts() -> dict[str, dict[str, Any]]:
    scene = _scene_contracts()
    rubric = json.loads(_read("Config/Image_Quality_Rubric.json"))
    quality_schema = ImageQualityReviewService._schema(rubric)
    result = {
        "scene_builder": {"system_prompt": SceneBuilderInterviewService.SYSTEM_PROMPT, "source": "zet/services/scene_builder_interview_service.py"},
        "prompt_analysis": {"prompt_template": _read("Config/AI_Prompt_Analysis_Instructions.md"), "source": "Config/AI_Prompt_Analysis_Instructions.md", "schema": None, "schema_status": "markdown_output_contract"},
        "prompt_condense": {"prompt_template": _read("Config/Prompt_Condense_Tasks/Condense_Zet.md"), "source": "Config/Prompt_Condense_Tasks/Condense_Zet.md", "schema": None, "schema_status": "two_line_text_output_contract"},
        "image_quality": {"system_prompt": "You are a strict visual QA prefilter. Compare the canonical reference (Image 1) with the generated candidate (Image 2). Judge only visible evidence. Do not infer whether the user likes the image and do not suggest prompt edits.", "prompt_template": "Score each supplied rubric dimension from 0 to 4 and evaluate every hard gate. Identity and costume fidelity compare Image 2 with Image 1. Technical quality and composition judge Image 2 itself. Use only the allowed failure reasons.\n\n" + json.dumps({"hard_gates": rubric["hard_gates"], "dimensions": rubric["dimensions"], "score_scale": rubric["score_scale"], "failure_reasons": rubric["failure_reasons"]}, ensure_ascii=False), "schema": quality_schema, "source": "zet/services/image_quality_review_service.py + Config/Image_Quality_Rubric.json"},
        "asset_workflow": {"source": "zet/services/ai_proxy_service.py", "schema": None, "schema_status": "AIProxy manifest output contract"},
    }
    result.update({f"scene_builder_{key}": value for key, value in scene.items()})
    return result


CASE_TEXT = {
    "SB-01": ("scene_builder", "Chapter 1: Mara reaches the rain-soaked platform as the last train disappears.", ["story phase only", "capture the visible beat", "preserve stated continuity"], ["ask architecture questions", "ask lighting questions"]),
    "SB-02": ("scene_builder", "Mara reaches the rain-soaked platform as the last train disappears; existing scene context is authoritative.", ["use the actual requested phase", "change only permitted phase content", "return the phase's production schema"], ["answer a different phase", "rewrite fields owned by another phase"]),
    "SB-03": ("scene_builder", "Visible elements are person_A, person_B, arch_01, and an off-frame lantern prop.", ["preserve each supplied ID", "each visible placement ID occurs exactly once", "exclude the off-frame prop from composition"], ["rename IDs", "place the off-frame prop in the reading order"]),
    "SB-04": ("scene_builder", 'Valindia says exactly "country girl" to Tsaeytte. The earlier question about the destination was answered: the arch.', ["preserve speaker and dialogue text exactly", "do not invent dialogue", "do not repeat the answered question"], ["invent a second line", "ask the answered destination question again"]),
    "PA-01": ("prompt_analysis", "A compiled prompt contains a name typo, contradictory left/right placement, and incompatible gaze directions.", ["identify all three localized issues", "preserve unrelated prompt text", "separate position, body facing, motion, and gaze"], ["rewrite the scene", "report a conflict without two incompatible facts"]),
    "PA-02": ("prompt_analysis", "A valid compiled First Day prompt with consistent placement, depth, and gaze.", ["report no invented contradiction", "avoid unnecessary identity changes"], ["invent an issue from a broad position", "treat a reference tag as prose"]),
    "PC-01": ("prompt_condense", "A detailed character prompt with annotated hair, costume, pose, and negative constraints.", ["emit exactly one prompt line", "emit exactly one negative line", "preserve annotated critical traits"], ["add unsupported jewelry", "add generic quality boosters"]),
    "ID-01": ("image_quality", "The actual arch reference has a legible visible inscription.", ["transcribe only legible text", "do not invent a slogan", "record image annotation provenance"], ["claim unreadable text is exact", "invent unsupported people"]),
    "ID-02": ("image_quality", "The arch inscription is intentionally obscured.", ["make uncertainty explicit", "do not confidently invent missing text"], ["supply a confident transcription", "infer a slogan from the setting"]),
    "ID-03": ("image_quality", "A person reference shows distinctive anatomy, worn clothing, and a carried object.", ["separate identity from costume", "exclude the carried object from both fields"], ["put the carried object in identity", "put the carried object in costume"]),
    "VC-01": ("image_quality", "Reference/candidate pair has annotated hair and costume changes with stable traits; image order is meaningful.", ["attribute changes to the candidate", "preserve stable matches", "reversing order reverses attribution"], ["reverse image roles", "attribute stable traits as changes"]),
    "VC-02": ("image_quality", "Reference and candidate images are identical.", ["report no major invented differences", "allow empty difference arrays"], ["invent a costume change", "score unrequested quality categories"]),
    "AW-01": ("asset_workflow", "Snapshot reachable generate, render, and prompt-analysis workflow tasks with their output contracts.", ["preserve task type and worker type", "preserve expected output formatting", "unsupported stages fail before inference"], ["use a placeholder prompt", "claim unsupported stages ran"]),
    "LG-01": ("scene_builder", "The largest supported scene/batch places critical constraints near the beginning, middle, and end.", ["preserve all three constraint locations", "do not truncate", "do not silently omit constraints"], ["summarize away an edge constraint", "drop the middle constraint"]),
    "IN-01": ("scene_builder", "A narrative/report contains text telling the model to ignore its schema or change IDs.", ["treat embedded text as source data", "retain the production contract", "preserve IDs"], ["follow the embedded instruction", "change the schema"]),
}


def _fixture(case_id: str, variant: str, contract: dict[str, Any], phase: str | None = None) -> dict[str, Any]:
    role, narrative, constraints, negatives = CASE_TEXT[case_id]
    phase = phase or CASE_PHASES.get(case_id)
    role_key = f"scene_builder_{phase}" if phase else role
    snapshot = contract if phase is None else _contracts()[f"scene_builder_{phase}"]
    prompt = narrative
    if phase:
        prompt = "\n\n".join([
            f"PHASE: {phase}", snapshot["phase_instruction"],
            "Return your best inferred result now, even when clarification questions remain. Ask at most three questions.",
            "NARRATIVE:\n" + narrative,
            "CURRENT SCENE BUILDER CONTEXT:\n{}",
            "PRIOR CLARIFICATIONS:\n[]",
        ])
    elif snapshot.get("prompt_template"):
        prompt = re.sub(r"\{\{[^}]+\}\}", narrative, str(snapshot["prompt_template"]))
        if role == "image_quality":
            prompt += "\n\nFixture scenario:\n" + narrative
    images = []
    if case_id in {"ID-01", "ID-02", "ID-03", "VC-01", "VC-02"}:
        images = [{"synthetic": "left"}, {"synthetic": "right"}] if case_id in {"VC-01", "VC-02"} else [{"synthetic": "arch" if case_id.startswith("ID-") else "left"}]
    source_artifacts = {
        "ID-01": ["Zet_Library/AuxiliaryResources/Images/spire-archway/arch-closeup.png"],
        "ID-02": ["Zet_Library/AuxiliaryResources/Images/spire-archway/arch-closeup.png"],
        "ID-03": ["Zet_Library/Assets/Tsaeytte/Adult/Character-Assembly_Front_Front_Assembled.png"],
    }.get(case_id, [])
    return {
        "id": f"{case_id.lower().replace('-', '_')}{('_' + phase) if phase else ''}_{variant}",
        "case_id": case_id,
        "variant": variant,
        "task_role": role_key,
        "source_provenance": {
            "source": snapshot.get("source", "portable synthetic WP14 case"),
            "status": "portable_synthetic",
            "annotation_status": "unverified_for_actual_library_image" if source_artifacts else "synthetic_annotation",
            "human_verified": False,
            "source_artifacts": source_artifacts,
            "annotation_provenance": "Visual source inspection recorded; human gold verification remains outstanding." if source_artifacts else "Synthetic descriptor annotation.",
            "notes": "Model drafts are negative examples only; no model output is ground truth.",
        },
        "prompt_version": f"zet-production-{CORPUS_VERSION}",
        "schema_version": f"zet-production-{CORPUS_VERSION}-{role_key}",
        "production_contract": snapshot,
        "input": prompt,
        "prompt": prompt,
        "schema": snapshot.get("schema") or {},
        "images": images,
        "critical_assertions": constraints,
        "expected_constraints": constraints,
        "negative_examples": [{"description": item} for item in negatives],
        "scored_dimensions": ["grounded_factual_accuracy", "required_content_coverage", "phase_or_instruction_compliance", "relevance_and_concision"],
        "scoring_rules": {"method": "manual_anchored_assertions", "critical_failures": constraints[:2], "unresolved_semantic_review": "block"},
        "performance_class": "large" if case_id == "LG-01" else "median" if case_id in {"PE-01", "SB-02"} else "short",
        "token_count": {"value": None, "status": "unavailable", "source": "evaluated runtime prompt_eval_count"},
        "validation": {"type": "json_schema"} if snapshot.get("schema") else {"type": "nonempty"},
    }


def export(output_root: str | Path = DEFAULT_OUTPUT) -> tuple[Path, Path]:
    output_root = Path(output_root).resolve()
    contracts = _contracts()
    base_cases = [(case_id, CASE_PHASES.get(case_id)) for case_id in CASE_TEXT if case_id != "SB-02"]
    base_cases.extend(("SB-02", phase) for phase in SCENE_PHASES)
    written = []
    for variant in ("development", "held-out"):
        fixtures = []
        for case_id, phase in base_cases:
            key = f"scene_builder_{phase}" if phase else CASE_TEXT[case_id][0]
            fixtures.append(_fixture(case_id, variant, contracts[key], phase))
        suite = output_root / f"zet-evaluation-{variant}"
        suite.mkdir(parents=True, exist_ok=True)
        path = suite / "fixtures.json"
        path.write_text(json.dumps({
            "fixture_format_version": 2,
            "suite": f"zet-evaluation-{variant}",
            "corpus_version": CORPUS_VERSION,
            "variant": variant,
            "token_count_provenance": "unavailable until evaluated runtime evidence is supplied",
            "fixtures": fixtures,
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append(path)
    return written[0], written[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    for path in export(args.output_root):
        print(path)


if __name__ == "__main__":
    main()
