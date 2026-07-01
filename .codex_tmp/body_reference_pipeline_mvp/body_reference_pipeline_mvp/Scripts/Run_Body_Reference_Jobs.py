from __future__ import annotations

import argparse
import fnmatch
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


SECTION_RE = re.compile(
    r"<!--\s*ZET:BEGIN\s+([A-Z0-9_{}-]+)\s*-->\s*(.*?)\s*<!--\s*ZET:END\s+\1\s*-->",
    re.DOTALL,
)

PLACEHOLDER_RE = re.compile(r"\{\{[^}]+\}\}")


class PipelineError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class CompiledSections:
    required: dict[str, str]
    optional: dict[str, str]
    missing_optional: list[str]

    @property
    def all_included(self) -> dict[str, str]:
        merged = {}
        merged.update(self.required)
        merged.update(self.optional)
        return merged


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def read_json(path: Path) -> Any:
    if not path.exists():
        raise PipelineError("MISSING_CONFIG", f"Missing config file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PipelineError("INVALID_JSON", f"Invalid JSON in {path}: {exc}") from exc


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def normalize_view(raw_view: str, aliases: dict[str, str], view_text: dict[str, Any]) -> str:
    if not raw_view or not str(raw_view).strip():
        raise PipelineError("MISSING_JOB_FIELD", "Job is missing View.")

    raw = str(raw_view).strip()

    if raw in view_text:
        return raw

    lookup_variants = [
        raw.strip().lower(),
        raw.strip().lower().replace("_", "-"),
        raw.strip().lower().replace("_", " "),
    ]

    for key in lookup_variants:
        if key in aliases:
            return aliases[key]

    raise PipelineError("UNKNOWN_VIEW", f"Unknown view value: {raw_view}")


def load_template_sections(template_path: Path) -> dict[str, str]:
    if not template_path.exists():
        raise PipelineError("MISSING_TEMPLATE", f"Template does not exist: {template_path}")

    text = template_path.read_text(encoding="utf-8")
    sections: dict[str, str] = {}

    for match in SECTION_RE.finditer(text):
        name = match.group(1).strip()
        body = match.group(2).strip()

        if name in sections:
            raise PipelineError("DUPLICATE_SECTION", f"Duplicate section in template: {name}")

        sections[name] = body

    begin_count = len(re.findall(r"<!--\s*ZET:BEGIN\s+", text))
    end_count = len(re.findall(r"<!--\s*ZET:END\s+", text))

    if begin_count != end_count or begin_count != len(sections):
        raise PipelineError(
            "MALFORMED_TEMPLATE_MARKERS",
            f"Malformed ZET markers in {template_path}. BEGIN={begin_count}, END={end_count}, parsed={len(sections)}",
        )

    return sections


def resolve_view_section(section_name: str, view_token: str) -> str:
    return section_name.replace("{VIEW}", view_token)


def section_is_empty(value: str | None) -> bool:
    return value is None or not value.strip()


def select_sections(
    all_sections: dict[str, str],
    bundle: dict[str, Any],
    view_token: str,
) -> CompiledSections:
    required: dict[str, str] = {}
    optional: dict[str, str] = {}
    missing_required: list[str] = []
    missing_optional: list[str] = []

    for raw_name in bundle.get("required_sections", []):
        name = resolve_view_section(raw_name, view_token)
        value = all_sections.get(name)
        if section_is_empty(value):
            missing_required.append(name)
        else:
            required[name] = value.strip()

    for raw_name in bundle.get("optional_sections", []):
        name = resolve_view_section(raw_name, view_token)
        value = all_sections.get(name)
        if section_is_empty(value):
            missing_optional.append(name)
        else:
            optional[name] = value.strip()

    if missing_required:
        raise PipelineError(
            "MISSING_REQUIRED_SECTION",
            "Missing required template section(s): " + ", ".join(missing_required),
        )

    included_names = list(required.keys()) + list(optional.keys())
    forbidden_patterns = bundle.get("forbidden_sections", [])

    for name in included_names:
        for pattern in forbidden_patterns:
            if fnmatch.fnmatch(name, pattern):
                raise PipelineError(
                    "FORBIDDEN_SECTION_INCLUDED",
                    f"Included section {name} matches forbidden pattern {pattern}",
                )

    return CompiledSections(required=required, optional=optional, missing_optional=missing_optional)


def load_static_prompt_template(config_dir: Path, template_name: str) -> str:
    template_path = config_dir / "Prompt_Templates" / f"{template_name}.md"
    if not template_path.exists():
        raise PipelineError("MISSING_CONFIG", f"Missing prompt template: {template_path}")
    return template_path.read_text(encoding="utf-8")


def replace_section_placeholders(
    prompt_template: str,
    compiled: CompiledSections,
    view_token: str,
) -> str:
    included = compiled.all_included

    def repl(match: re.Match[str]) -> str:
        raw_name = match.group(1)
        section_name = resolve_view_section(raw_name, view_token)

        if section_name in included:
            return included[section_name].strip()

        if section_name in compiled.missing_optional:
            return ""

        raise PipelineError(
            "UNRESOLVED_PLACEHOLDER",
            f"Prompt template references unavailable section: {section_name}",
        )

    return re.sub(r"\{\{SECTION:([A-Z0-9_{}-]+)\}\}", repl, prompt_template)


def build_final_prompt(
    prompt_template: str,
    job: dict[str, Any],
    compiled: CompiledSections,
    view_token: str,
    view_info: dict[str, str],
) -> str:
    prompt = prompt_template

    replacements = {
        "{{CHARACTER_NAME}}": str(job["Character"]),
        "{{CHARACTER_PHASE}}": str(job["Phase"]),
        "{{VIEW_TOKEN}}": view_token,
        "{{VIEW_LABEL}}": view_info["label"],
        "{{VIEW_INSTRUCTION}}": view_info["instruction"],
    }

    for key, value in replacements.items():
        prompt = prompt.replace(key, value)

    prompt = replace_section_placeholders(prompt, compiled, view_token)

    prompt = re.sub(r"\n{3,}", "\n\n", prompt).strip() + "\n"

    unresolved = PLACEHOLDER_RE.findall(prompt)
    if unresolved:
        raise PipelineError(
            "UNRESOLVED_PLACEHOLDER",
            "Final prompt contains unresolved placeholder(s): " + ", ".join(unresolved),
        )

    if "<!-- ZET:" in prompt:
        raise PipelineError(
            "ZET_MARKER_IN_FINAL_PROMPT",
            "Final prompt contains ZET markers.",
        )

    return prompt


def build_compiled_sections_md(
    job: dict[str, Any],
    view_token: str,
    compiled: CompiledSections,
) -> str:
    lines: list[str] = []

    lines.append("# Compiled Sections")
    lines.append("")
    lines.append(f"Job ID: {job.get('Job ID', '')}")
    lines.append(f"Task: {job.get('Task', '')}")
    lines.append(f"Character: {job.get('Character', '')}")
    lines.append(f"Phase: {job.get('Phase', '')}")
    lines.append(f"View Token: {view_token}")
    lines.append("")

    lines.append("## Included Required Sections")
    lines.append("")
    for name in compiled.required:
        lines.append(f"- {name}")
    lines.append("")

    lines.append("## Included Optional Sections")
    lines.append("")
    for name in compiled.optional:
        lines.append(f"- {name}")
    if not compiled.optional:
        lines.append("- None")
    lines.append("")

    lines.append("## Missing Optional Sections")
    lines.append("")
    for name in compiled.missing_optional:
        lines.append(f"- {name}")
    if not compiled.missing_optional:
        lines.append("- None")
    lines.append("")

    for name, content in compiled.all_included.items():
        lines.append("---")
        lines.append("")
        lines.append(f"# {name}")
        lines.append("")
        lines.append(content.strip())
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def build_dependency_manifest(
    job: dict[str, Any],
    view_token: str,
    bundle: dict[str, Any],
) -> dict[str, Any]:
    resource_policy = bundle.get("resources", {})
    return {
        "job_id": job.get("Job ID", ""),
        "task": job.get("Task", ""),
        "character": job.get("Character", ""),
        "phase": job.get("Phase", ""),
        "view_token": view_token,
        "resources_allowed": False,
        "resources": [],
        "resource_policy": resource_policy,
        "notes": [
            "Body-reference uses no external, cached, discovered, or prior-rendered image resources unless explicitly allowed by future task configuration."
        ],
    }


def build_prompt_review_md(job: dict[str, Any], final_prompt_path: Path, view_token: str) -> str:
    return f"""# Prompt Review

Job ID: {job.get("Job ID", "")}
Task: {job.get("Task", "")}
Character: {job.get("Character", "")}
Phase: {job.get("Phase", "")}
View: {view_token}
Prompt File: {final_prompt_path}

Review Status: PENDING
Reviewer: HUMAN
Reviewed At:

## Checklist

- [ ] Prompt specifies full-body technical body-reference.
- [ ] Prompt includes requested view token and plain-language view instruction.
- [ ] Prompt includes body facts.
- [ ] Prompt includes identity/body preservation rules.
- [ ] Prompt includes technical fitment shell.
- [ ] Prompt avoids costume sections.
- [ ] Prompt avoids picaresque/flavor sections.
- [ ] Prompt avoids narrative scene instructions.
- [ ] Prompt avoids emotional acting.
- [ ] Prompt avoids props/weapons/equipment.
- [ ] Prompt contains no unresolved placeholders.
- [ ] Prompt contains no ZET markers.

## Static Review Findings

PENDING

## Notes

"""


def build_image_review_md(job: dict[str, Any], expected_output: Path, view_token: str) -> str:
    return f"""# Image Review

Job ID: {job.get("Job ID", "")}
Task: {job.get("Task", "")}
Character: {job.get("Character", "")}
Phase: {job.get("Phase", "")}
View: {view_token}
Image File: {expected_output}

Review Status: PENDING
Reviewer: HUMAN
Reviewed At:

## Checklist

- [ ] Full body visible from head to feet.
- [ ] Requested view is correct.
- [ ] Body proportions match the template.
- [ ] Fitment shell is correct.
- [ ] No costume details were added.
- [ ] No props or weapons were added.
- [ ] No narrative scene was added.
- [ ] Lighting/background are neutral.
- [ ] Image is useful for later head/costume fitment.

## Notes

"""


def require_job_field(job: dict[str, Any], field: str) -> None:
    if field not in job or not str(job[field]).strip():
        raise PipelineError("MISSING_JOB_FIELD", f"Job is missing required field: {field}")


def derive_output_dir(
    project_root: Path,
    job: dict[str, Any],
    view_info: dict[str, str],
) -> Path:
    explicit = job.get("Output Directory")
    if explicit and str(explicit).strip():
        return project_root / str(explicit)

    character = str(job["Character"])
    phase = str(job["Phase"])
    folder_name = view_info["folder_name"]

    return project_root / "Characters" / character / phase / "Body_Reference" / folder_name


def derive_expected_output(output_dir: Path, job: dict[str, Any], view_info: dict[str, str]) -> Path:
    explicit = job.get("Expected Output")
    if explicit and str(explicit).strip():
        explicit_path = Path(str(explicit))
        if explicit_path.is_absolute():
            return explicit_path
        return output_dir / explicit_path

    return output_dir / f"Body-{view_info['output_name_fragment']}.png"


def process_body_reference_job(
    project_root: Path,
    config_dir: Path,
    job: dict[str, Any],
) -> dict[str, Any]:
    for field in ["Job ID", "Task", "Character", "Phase", "View", "Template Path"]:
        require_job_field(job, field)

    bundles = read_json(config_dir / "Prompt_Task_Bundles.json")
    aliases = read_json(config_dir / "Prompt_View_Aliases.json")
    view_text = read_json(config_dir / "Prompt_View_Text.json")

    bundle = bundles.get("body-reference")
    if not bundle:
        raise PipelineError("MISSING_CONFIG", "Missing body-reference bundle in Prompt_Task_Bundles.json")

    view_token = normalize_view(str(job["View"]), aliases, view_text)

    if view_token not in view_text:
        raise PipelineError("UNKNOWN_VIEW", f"View token has no view text entry: {view_token}")

    view_info = view_text[view_token]

    template_path = project_root / str(job["Template Path"])
    all_sections = load_template_sections(template_path)
    compiled = select_sections(all_sections, bundle, view_token)

    output_dir = derive_output_dir(project_root, job, view_info)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_files = bundle.get("output_files", {})

    final_prompt_path = output_dir / output_files.get("final_prompt", "Final_Image_Prompt.md")
    compiled_sections_path = output_dir / output_files.get("compiled_sections", "Compiled_Sections.md")
    dependency_manifest_path = output_dir / output_files.get("dependency_manifest", "dependency_manifest.json")
    prompt_review_path = output_dir / output_files.get("prompt_review", "Prompt_Review.md")
    image_review_path = output_dir / output_files.get("image_review", "Image_Review.md")
    expected_output_path = derive_expected_output(output_dir, job, view_info)

    prompt_template = load_static_prompt_template(config_dir, bundle["static_prompt_template"])
    final_prompt = build_final_prompt(prompt_template, job, compiled, view_token, view_info)
    compiled_md = build_compiled_sections_md(job, view_token, compiled)
    manifest = build_dependency_manifest(job, view_token, bundle)

    final_prompt_path.write_text(final_prompt, encoding="utf-8")
    compiled_sections_path.write_text(compiled_md, encoding="utf-8")
    write_json(dependency_manifest_path, manifest)
    prompt_review_path.write_text(build_prompt_review_md(job, final_prompt_path, view_token), encoding="utf-8")
    image_review_path.write_text(build_image_review_md(job, expected_output_path, view_token), encoding="utf-8")

    updated = dict(job)
    updated["Status"] = bundle.get("next_status", "READY_FOR_PROMPT_REVIEW")
    updated["Next Actor"] = bundle.get("next_actor", "HUMAN")
    updated["View Token"] = view_token
    updated["Output Directory"] = str(output_dir.relative_to(project_root))
    updated["Expected Output"] = str(expected_output_path.relative_to(project_root))
    updated["Final Prompt"] = str(final_prompt_path.relative_to(project_root))
    updated["Compiled Sections"] = str(compiled_sections_path.relative_to(project_root))
    updated["Dependency Manifest"] = str(dependency_manifest_path.relative_to(project_root))
    updated["Prompt Review"] = str(prompt_review_path.relative_to(project_root))
    updated["Image Review"] = str(image_review_path.relative_to(project_root))
    updated["Error Code"] = ""
    updated["Error Message"] = ""
    updated["Last Updated"] = now_iso()

    return updated


def load_jobs(job_list_path: Path) -> list[dict[str, Any]]:
    if not job_list_path.exists():
        raise PipelineError("MISSING_JOB_LIST", f"Missing job list: {job_list_path}")

    data = read_json(job_list_path)

    if isinstance(data, list):
        return data

    if isinstance(data, dict) and isinstance(data.get("jobs"), list):
        return data["jobs"]

    raise PipelineError("INVALID_JOB_LIST", "Job list must be a JSON list or an object with a 'jobs' list.")


def save_jobs(job_list_path: Path, jobs: list[dict[str, Any]]) -> None:
    original = read_json(job_list_path)
    if isinstance(original, dict) and isinstance(original.get("jobs"), list):
        original["jobs"] = jobs
        write_json(job_list_path, original)
    else:
        write_json(job_list_path, jobs)


def should_process(job: dict[str, Any]) -> bool:
    return (
        str(job.get("Task", "")).strip() == "body-reference"
        and str(job.get("Status", "")).strip() == "READY_FOR_COMPILE"
        and str(job.get("Next Actor", "")).strip() == "PYTHON"
    )


def mark_error(job: dict[str, Any], err: PipelineError) -> dict[str, Any]:
    updated = dict(job)
    updated["Status"] = "ERROR"
    updated["Next Actor"] = "HUMAN"
    updated["Error Code"] = err.code
    updated["Error Message"] = err.message
    updated["Last Updated"] = now_iso()
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description="Run body-reference compile jobs.")
    parser.add_argument("--project-root", default=".", help="Project root directory.")
    parser.add_argument("--job-list", default="Job_List.json", help="Path to job list JSON.")
    parser.add_argument("--config-dir", default="Config", help="Path to config directory.")
    parser.add_argument("--dry-run", action="store_true", help="Process without saving job list changes.")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    job_list_path = (project_root / args.job_list).resolve()
    config_dir = (project_root / args.config_dir).resolve()

    jobs = load_jobs(job_list_path)
    updated_jobs: list[dict[str, Any]] = []

    processed = 0
    errors = 0

    for job in jobs:
        if not should_process(job):
            updated_jobs.append(job)
            continue

        try:
            updated_jobs.append(process_body_reference_job(project_root, config_dir, job))
            processed += 1
        except PipelineError as err:
            updated_jobs.append(mark_error(job, err))
            errors += 1

    if not args.dry_run:
        save_jobs(job_list_path, updated_jobs)

    print(f"Body-reference jobs processed: {processed}")
    print(f"Body-reference jobs errored: {errors}")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
