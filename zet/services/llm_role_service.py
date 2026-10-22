"""One inventory for creative LLM callers, model inheritance and Config cards."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LLMRole:
    key: str
    label: str
    description: str
    model_setting: str
    skill: str = "off"
    capabilities: tuple[str, ...] = ("text",)
    providers: tuple[str, ...] = ("codex", "ollama")
    status: str = "active"
    prompt_fields: tuple[str, ...] = ()


ROLES = (
    LLMRole("narrative_interview", "Narrative interview", "Proposes editable scene fields and resolves intent; not a render prompt.", "ai_narrative_scene_model"),
    LLMRole("narrative_prompt", "Narrative prompt writing", "Writes scene, backdrop adaptation and assembly prompts.", "ai_narrative_scene_model", "authoring", prompt_fields=("scene", "rendering")),
    LLMRole("image_prompt", "Image-to-prompt drafting", "Writes a complete generation prompt from an image.", "ai_image_prompt_generation_model", "authoring", ("vision",), prompt_fields=("prompt", "negative_prompt")),
    LLMRole("inventory_identity", "Inventory identity description", "Extracts stable identifying facts, not image-generation prose.", "codex_default_model", capabilities=("vision",), providers=("codex",)),
    LLMRole("inventory_metadata", "Inventory catalog metadata", "Extracts stable identity and costume metadata.", "ai_image_description_model", capabilities=("vision",)),
    LLMRole("reconstruction_prompt", "Reconstruction prompt drafting", "Writes the intended result independently of analysis-only source pixels.", "ai_image_prompt_generation_model", "authoring", ("vision",), prompt_fields=("content_prompt",)),
    LLMRole("reconstruction_review", "Reconstruction review", "Compares target and candidate; writes scoped correction suggestions.", "ai_image_prompt_generation_model", "review", ("vision",), prompt_fields=("items[].correction",)),
    LLMRole("character_description", "Minor / Quick Character description", "Drafts reusable appearance prose; keeps observations and identity separate.", "ai_quick_character_wizard_model", "fragments", ("vision",), prompt_fields=("description",)),
    LLMRole("character_review", "Minor / Quick Character review", "Reviews visible deviations and suggests scoped edits.", "ai_quick_character_wizard_model", "review", ("vision",), prompt_fields=("items[].correction", "refinements")),
    LLMRole("costume_observation", "Costume reference observation", "Extracts visible source facts without rewriting prompts.", "ai_costume_wizard_model", capabilities=("vision",)),
    LLMRole("costume_template", "Costume template drafting / revision", "Writes image-generation wording inside protected template structure.", "ai_costume_wizard_model", "fragments", prompt_fields=("costume_role", "footwear", "footwear_contact", "facts", "view_overrides", "view_suppression", "equipment_facts", "equipment_view_overrides", "identity_rules", "scene_identity", "scene_anchors", "markdown")),
    LLMRole("costume_evidence_review", "Costume draft evidence review", "Checks unsupported facts and template structure; does not rewrite.", "ai_costume_wizard_model", capabilities=("vision",)),
    LLMRole("costume_render_review", "Costume render review", "Suggests targeted corrections to a test render.", "ai_costume_wizard_model", "review", ("vision",), prompt_fields=("refinements",)),
    LLMRole("character_prompt_review", "Character governing-template review", "Proposes selectable corrections to source wording and compiled previews.", "codex_default_model", "review", prompt_fields=("findings[].after",)),
    LLMRole("template_revision", "Historical template revision", "Continues historical image-evidence template proposals.", "codex_default_model", "review", ("vision",), status="compatibility", prompt_fields=("edits[].text",)),
    LLMRole("local_prompt_improvement", "Local prompt improvement", "Diagnoses prompt wording from rendered evidence.", "codex_default_model", "review", ("vision",), ("codex",), prompt_fields=("observations",)),
    LLMRole("character_refinement", "Dedicated character image refinement", "Suggests scoped corrections to the selected character image.", "codex_default_model", "review", ("vision",), prompt_fields=("items[].correction",)),
    LLMRole("image_ranking", "Comparative candidate ranking", "Orders candidates by visible compliance; not a prompt-writing task.", "codex_default_model", capabilities=("vision",), providers=("codex",)),
    LLMRole("body_review_codex", "Body candidate assessment — Codex", "Assesses anatomy, orientation and visible compliance.", "codex_default_model", capabilities=("vision",), providers=("codex",)),
    LLMRole("body_review_local", "Body candidate assessment — local", "Assesses anatomy, orientation and visible compliance.", "local_body_reference_review_model", capabilities=("vision",)),
    LLMRole("recipe_qa", "Recipe Lab visual QA", "Scores rubric evidence; explicitly excludes prompt edits.", "local_body_reference_review_model", capabilities=("vision",)),
    LLMRole("asset_workflow", "Traditional asset workflow", "Compatibility asset-stage responses; traditional character generation is retired.", "ai_asset_workflow_model", status="compatibility"),
    LLMRole("prompt_condense", "Traditional prompt condensation", "Compatibility prompt rewriting; does not reactivate retired workflows.", "prompt_condense_model", "authoring", status="compatibility", prompt_fields=("response",)),
    LLMRole("scene_builder", "Scene Builder", "Retired configuration; no active request producer.", "ai_scene_builder_model", status="retired"),
    LLMRole("prompt_analysis", "Scene prompt analysis", "Retired configuration; no active request producer.", "ai_prompt_analysis_model", "review", status="retired"),
)
ROLE_BY_KEY = {role.key: role for role in ROLES}


def skill_modules(role: LLMRole, operation: str = "mixed") -> list[str]:
    """Declare applicable instruction sources for runtime and Config inspection."""
    if role.skill == "off" or role.status == "retired":
        return []
    if operation not in {"generate", "edit", "composite", "mixed"}:
        raise ValueError(f"{role.label} needs an explicit generate/edit/composite/mixed render operation.")
    modules = ["SKILL.md"]
    if operation in {"generate", "mixed"}:
        modules.append("references/t2i_rules.md")
    if operation in {"edit", "composite", "mixed"}:
        modules.append("references/edit_rules.md")
    if role.skill == "authoring":
        modules.append("references/cheat_sheet.md")
    return modules + ["adapters/contract.md", f"adapters/{role.skill}.md"]


def get_role(key: str) -> LLMRole:
    try:
        return ROLE_BY_KEY[key]
    except (KeyError, TypeError):
        raise ValueError(f"Unknown LLM role: {key!r}. Register the request's purpose before publication.") from None


def validate_overrides(values) -> dict[str, str]:
    if not isinstance(values, dict):
        raise ValueError("LLMRoles.Models must be a role-to-model table.")
    result = {}
    for key, value in values.items():
        role = get_role(key)
        if not isinstance(value, str):
            raise ValueError(f"Model override for {key} must be text.")
        model = value.strip()
        if model:
            validate_provider(role, model)
            result[key] = model
    return result


def validate_provider(role: LLMRole, model: str) -> None:
    provider = "codex" if model.startswith("codex:") else "ollama"
    if provider not in role.providers:
        raise ValueError(f"{role.label} supports {', '.join(role.providers)} models.")


def resolve_role_model(config, key: str, explicit: str = "", *, fallback: str = "") -> str:
    role = get_role(key)
    default = str(getattr(config, role.model_setting, fallback) or fallback)
    if role.model_setting == "codex_default_model" and not default.startswith("codex:"):
        default = "codex:" + default
    model = str(explicit or getattr(config, "llm_role_models", {}).get(key) or default).strip()
    validate_provider(role, model)
    return model
