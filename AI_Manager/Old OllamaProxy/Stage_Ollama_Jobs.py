#!/usr/bin/env python3
"""
Stage_Ollama_Jobs.py

Filesystem-backed Ollama proxy coordinator.

This script never calls Ollama directly. It is fast coordinator logic only:
- harvest completed Answer folders
- discard late/obsolete answers
- reset stale WAITING_FOR_OLLAMA_ANSWER jobs
- stage new Ask folders for jobs assigned to OLLAMA or OLLAMA_PROXY
- update Queue/Job_List.json

Workers are the only scripts that call Ollama:
- Ollama_File_Worker.py
- Ollama_File_Worker.ps1
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from datetime import datetime
import time
import shutil

DEFAULT_OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_OLLAMA_URLS = [DEFAULT_OLLAMA_URL]

FINISHED_STATUSES = {"FINISHED", "DONE", "COMPLETE", "COMPLETED"}

JOB_HEADERS = [
    "Job",
    "Status",
    "Next Actor",
    "Next Action",
    "Expected Output",
    "Final Expected Image",
    "Task",
    "Character",
    "Phase",
    "Body View",
    "Head View",
    "Folder",
    "Asset ID",
    "Error Code",
    "Error State",
    "Error Source",
    "Error Message",
    "Error Time",
]

PROTECTED_BEGIN_TEMPLATE = "<!-- BEGIN PYTHON_INSERT:{tag} -->"
PROTECTED_END_TEMPLATE = "<!-- END PYTHON_INSERT:{tag} -->"

@dataclass
class JobRow:
    values: dict[str, str]

    @property
    def job(self) -> str:
        return self.values.get("Job", "").strip()

    @property
    def status(self) -> str:
        return self.values.get("Status", "").strip()

    @property
    def next_actor(self) -> str:
        return self.values.get("Next Actor", "").strip()

    @property
    def next_action(self) -> str:
        return self.values.get("Next Action", "").strip()

    @property
    def expected_output(self) -> str:
        return self.values.get("Expected Output", "").strip()

    @property
    def final_expected_image(self) -> str:
        return self.values.get("Final Expected Image", "").strip()

    @property
    def error_state(self) -> str:
        return self.values.get("Error State", "").strip().upper()

    @property
    def task(self) -> str:
        return self.values.get("Task", "").strip()

    @property
    def folder(self) -> Path:
        return Path(self.values.get("Folder", "").strip()).expanduser()


def md_cell(value: str) -> str:
    return str(value).replace("\n", " ").replace("|", "\\|").strip()


def unescape_md_cell(value: str) -> str:
    return value.replace("\\|", "|").strip()


def is_error_paused(row: "JobRow") -> bool:
    return row.error_state == "ERROR"


def clear_error_fields(row: "JobRow") -> None:
    row.values["Error Code"] = ""
    row.values["Error State"] = ""
    row.values["Error Source"] = ""
    row.values["Error Message"] = ""
    row.values["Error Time"] = ""


def set_error_fields(row: "JobRow", source: str, exc: Exception | str) -> None:
    message = str(exc).replace("|", "/").replace("\n", " ").strip()
    row.values["Error Code"] = type(exc).__name__ if isinstance(exc, Exception) else "ERROR"
    row.values["Error State"] = "ERROR"
    row.values["Error Source"] = source
    row.values["Error Message"] = message[:500]
    row.values["Error Time"] = datetime.now().isoformat(timespec="seconds")


def ollama_prompt_filename(expected_output: str) -> str:
    try:
        name = Path(expected_output).name
        stem = Path(name).stem
        if not stem or stem.lower() in {"human review", "none", "n/a"}:
            raise ValueError("not a usable filename")
        stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("._-")
        if not stem:
            raise ValueError("empty sanitized filename")
        return f"OLLAMA-{stem}.md"
    except Exception:
        return "OLLAMA_Prompt_unknown.md"


def load_peer_script(module_filename: str, module_name: str):
    """Load a sibling script from the Scripts folder without requiring package imports."""
    script_path = Path(__file__).resolve().parent / module_filename
    if not script_path.exists():
        raise FileNotFoundError(f"Required helper script not found: {script_path}")
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load helper script: {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def advance_job_after_output(job: "JobRow", output_name: str, manifest: dict) -> None:
    """Use Advance_Job.py logic so all actors share overlay and advancement rules."""
    advance_module = load_peer_script("Advance_Job.py", "advance_job_helper")
    advance_module.advance_row_after_output(
        job.values,
        job_folder=job.folder,
        completed_output=output_name,
        manifest=manifest,
    )
    print(f"Advanced {job.job} after {output_name}")


VIEW_FILE_STEMS = {
    "front": "Front",
    "front-left-3/4": "Front-Left-3-4",
    "left-profile": "Left-Profile",
    "back-left-3/4": "Back-Left-3-4",
    "back": "Back",
    "back-right-3/4": "Back-Right-3-4",
    "right-profile": "Right-Profile",
    "front-right-3/4": "Front-Right-3-4",
}


def final_expected_image_for_row(row: "JobRow") -> str:
    task = row.task
    body_view = row.values.get("Body View", "").strip()
    head_view = row.values.get("Head View", "").strip()
    view = head_view if task == "head-fitment" else body_view
    stem = VIEW_FILE_STEMS.get(view)
    if not stem:
        stem = view.replace("/", "-").replace(" ", "-")
    if task == "body-reference":
        return f"Body-{stem}.png"
    if task == "head-fitment":
        return f"Head-Fitment-{stem}.png"
    if task == "character-assembly":
        return f"Character-Assembled-{stem}.png"
    if task == "costume-fitment":
        return f"Costume-Fitment-{stem}.png"
    return ""



JOB_JSON_VERSION = 1

ROW_TO_JSON_FIELD = {
    "Job": "job_id",
    "Status": "status",
    "Next Actor": "next_actor",
    "Next Action": "next_action",
    "Expected Output": "expected_output",
    "Final Expected Image": "final_expected_image",
    "Task": "task",
    "Character": "character",
    "Phase": "phase",
    "Body View": "body_view",
    "Head View": "head_view",
    "Folder": "folder",
    "Asset ID": "asset_id",
}
JSON_TO_ROW_FIELD = {v: k for k, v in ROW_TO_JSON_FIELD.items()}


def json_job_to_row(job: dict) -> dict[str, str]:
    row: dict[str, str] = {}
    for json_key, row_key in JSON_TO_ROW_FIELD.items():
        value = job.get(json_key, "")
        row[row_key] = "" if value is None else str(value)
    error = job.get("error", {}) if isinstance(job.get("error", {}), dict) else {}
    row["Error Code"] = str(error.get("code", "") or "")
    row["Error State"] = str(error.get("state", "") or "")
    row["Error Source"] = str(error.get("source", "") or "")
    row["Error Message"] = str(error.get("message", "") or "")
    row["Error Time"] = str(error.get("time", "") or "")
    for header in JOB_HEADERS:
        row.setdefault(header, "")
    return row


def row_to_json_job(row: dict[str, str]) -> dict:
    job: dict = {}
    for row_key, json_key in ROW_TO_JSON_FIELD.items():
        job[json_key] = str(row.get(row_key, "") or "")
    job["error"] = {
        "code": str(row.get("Error Code", "") or ""),
        "state": str(row.get("Error State", "") or "NONE"),
        "source": str(row.get("Error Source", "") or ""),
        "message": str(row.get("Error Message", "") or ""),
        "time": str(row.get("Error Time", "") or ""),
    }
    if not job["error"]["state"].strip():
        job["error"]["state"] = "NONE"
    return job


def load_job_json(path: Path) -> dict:
    if not path.exists():
        return {"version": JOB_JSON_VERSION, "jobs": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Job list JSON must be an object: {path}")
    data.setdefault("version", JOB_JSON_VERSION)
    data.setdefault("jobs", [])
    if not isinstance(data["jobs"], list):
        raise ValueError(f"Job list JSON field 'jobs' must be a list: {path}")
    return data


def write_job_json(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    active_rows = [r for r in rows if str(r.get("Status", "")).strip().upper() not in FINISHED_STATUSES]

    def job_sort_key(row: dict[str, str]) -> tuple[int, str]:
        job = row.get("Job", "")
        m = re.search(r"(\d+)$", job)
        return (int(m.group(1)) if m else 10**9, job)

    active_rows.sort(key=job_sort_key)
    data = {
        "version": JOB_JSON_VERSION,
        "jobs": [row_to_json_job(row) for row in active_rows],
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_job_list(path: Path) -> list[JobRow]:
    if not path.exists():
        raise FileNotFoundError(f"Job list not found: {path}")
    data = load_job_json(path)
    rows: list[JobRow] = []
    for job in data.get("jobs", []):
        if isinstance(job, dict):
            rows.append(JobRow(json_job_to_row(job)))
    return rows


def write_job_list(path: Path, rows: list[JobRow]) -> None:
    row_dicts: list[dict[str, str]] = []
    for row in rows:
        if not row.values.get("Final Expected Image", "").strip():
            row.values["Final Expected Image"] = final_expected_image_for_row(row)
        row.values.setdefault("Asset ID", "")
        row.values.setdefault("Error Code", "")
        row.values.setdefault("Error State", "NONE")
        row.values.setdefault("Error Source", "")
        row.values.setdefault("Error Message", "")
        row.values.setdefault("Error Time", "")
        row_dicts.append(row.values)
    write_job_json(path, row_dicts)

def select_jobs(rows: Iterable[JobRow], actor: str, status: str, only_job: str | None) -> list[JobRow]:
    selected: list[JobRow] = []
    for row in rows:
        if only_job and row.job != only_job:
            continue
        if row.status.strip().upper() != status.upper():
            continue
        if row.next_actor.strip().upper() != actor.upper():
            continue
        if is_error_paused(row):
            continue
        selected.append(row)
    return selected


def load_job_inputs(job: JobRow) -> tuple[str, dict]:
    spec_path = job.folder / "Character_Specification.md"
    manifest_path = job.folder / "dependency_manifest.json"

    if not spec_path.exists():
        raise FileNotFoundError(f"Missing Character_Specification.md for {job.job}: {spec_path}")

    spec_text = spec_path.read_text(encoding="utf-8")
    manifest: dict = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    return spec_text, manifest


def build_prompt(job: JobRow, spec_text: str, manifest: dict, output_name: str, module_rules: str) -> str:
    task = job.task
    image_summary = ""
    referenced_images = manifest.get("referenced_images", []) if isinstance(manifest, dict) else []
    if referenced_images:
        lines = []
        for img in referenced_images[:80]:
            ref = img.get("reference", "")
            copied_to = img.get("copied_to", "")
            status = img.get("status", "")
            if copied_to:
                try:
                    rel = Path(copied_to).resolve().relative_to(job.folder.resolve()).as_posix()
                except Exception:
                    rel = copied_to
                lines.append(f"- {ref} -> {rel} ({status})")
            else:
                lines.append(f"- {ref} ({status})")
        image_summary = "\n".join(lines)

    protected_job_metadata = ""
    if isinstance(manifest, dict):
        protected_job_metadata = str(manifest.get("protected_job_metadata", "") or "")
    if not protected_job_metadata:
        match = re.search(
            r"## Protected Job Metadata - Python-Owned\n.*?(?=\n## |\Z)",
            spec_text,
            flags=re.DOTALL,
        )
        if match:
            protected_job_metadata = match.group(0).strip()

    if job.task == "head-fitment" and output_name.lower() == "final_image_prompt.md":
        return f"""You are a local prompt-construction model in a modular fantasy character image pipeline.

You do not have filesystem access. Python has already read the files for you.

Your job is to produce the content of Final_Image_Prompt.md only.

This is a final renderer prompt, not a Render_Packet.md and not a process explanation.

Job metadata:
- Job: {job.job}
- Task: {job.task}
- Character: {job.values.get('Character', '')}
- Phase: {job.values.get('Phase', '')}
- Body View: {job.values.get('Body View', '')}
- Head View: {job.values.get('Head View', '')}
- Next Action: {job.next_action}

MANDATORY FOR HEAD-FITMENT FINAL PROMPTS:
- The output must clearly require a standalone head-and-neck module.
- Use the exact phrase: standalone head-and-neck module.
- Clearly say: No shoulders.
- Clearly say: No torso.
- Clearly say: No bust or bust wrap.
- Clearly say: the body fitment source is only a fitment reference.
- Clearly say: use the body source only for fitment reference geometry.
- Clearly say: remove any shoulders, chest, bust wrap, torso, body mannequin geometry, gray mannequin head, or body-source upper-body material.
- Do not write a full-body character render prompt.
- Do not write a Render_Packet.md.

Copy the Protected Job Metadata block exactly and preserve all filenames.

<<<BEGIN PROTECTED_JOB_METADATA>>>
{protected_job_metadata if protected_job_metadata else '- MISSING: no protected metadata was found. If missing, copy Job metadata exactly and do not infer alternate views.'}
<<<END PROTECTED_JOB_METADATA>>>

Local image references discovered by Python:
{image_summary if image_summary else 'NONE - this job has no input source images; do not request uploaded source images.'}

Render_Packet.md, if present, and Character_Specification.md source material are below. Create a concise final image prompt that a renderer can follow.

{module_rules}

Character_Specification.md:

<<<BEGIN CHARACTER_SPECIFICATION>>>
{spec_text}
<<<END CHARACTER_SPECIFICATION>>>
"""

    # This task is intentionally conservative. Ollama should prepare a packet or smoke-test
    # output, not creatively reinterpret the character.
    return f"""You are a local preprocessing model in a modular fantasy character image pipeline.

You do not have filesystem access. Python has already read the files for you.

Your job is to produce the content of this output file only:

{output_name}

Job metadata:
- Job: {job.job}
- Task: {job.task}
- Character: {job.values.get('Character', '')}
- Phase: {job.values.get('Phase', '')}
- Body View: {job.values.get('Body View', '')}
- Head View: {job.values.get('Head View', '')}
- Task: {job.values.get('Task', '')}
- Next Action: {job.next_action}

# PRIMARY REQUIREMENT - COPY PROTECTED JOB METADATA AND Modest Technical Fitment Shell SAFETY TEXT EXACTLY

This requirement overrides all other instructions in this prompt.

The following block is Python-owned. It is the authority for task, body view, head view, selected view instruction, source filenames, and output filename.

Copy this block exactly into the Render_Packet.md output near the top under the heading:

## Protected Job Metadata - Python-Owned

Do not infer view names or source filenames from examples.
Do not default to front view.
Do not replace front-left-3/4, front-right-3/4, profile, or back views with front view.
The output is incorrect if it uses a different view or filename than this block.

<<<BEGIN PROTECTED_JOB_METADATA>>>
{protected_job_metadata if protected_job_metadata else '- MISSING: no protected metadata was found. If missing, copy Job metadata exactly and do not infer alternate views.'}
<<<END PROTECTED_JOB_METADATA>>>

# PRIMARY REQUIREMENT - COPY MODEST TECHNICAL FITMENT SHELL EXACTLY

If the Character_Specification.md or dependency_manifest.json contains a Modest Technical Fitment Shell section, copy the full section exactly.

Do not summarize it.

Do not dilute it.

Do not reduce it to a heading.

Do not replace it with "no clothing."

Do not write unqualified "no clothing" where it could imply nudity.

The output is incorrect if the Modest Technical Fitment Shell is omitted, summarized, or contradicted.

# SECONDARY PRIMARY REQUIREMENT - DO NOT SUMMARIZE BODY CONSTRAINTS

This requirement overrides all lower-priority instructions in this prompt.

For the section:

## Critical Body / Fitment Constraints

Copy the complete Character Body Specification content verbatim.

Do not summarize it.

Do not compress it.

Do not generalize it.

Do not rewrite it.

Do not replace it with references such as:
"Preserve exact body-shape constraints from Character-Body-Specifications.md."

Do not omit any silhouette rules, proportion rules, numeric targets, avoid lists, or lower-body correction rules.

The output is incorrect if any body constraints are summarized, omitted, or replaced with references.

Completeness is more important than brevity.

When in doubt, copy more information rather than less.

## Rules

1. Do not invent new character details.

2. Do not remove constraints.

3. Preserve exact constraint wording.

4. Do not summarize body specifications.

5. Do not summarize mannequin requirements.

6. Do not summarize view instructions.

6a. Preserve the Protected Job Metadata values exactly.

6b. Use the Protected Job Metadata source filenames and output filename exactly.

7. Do not replace constraints with references to source files.

8. If a constraint appears in the source material, copy it into the render packet.

9. Completeness is more important than brevity.

10. Return only the Markdown content for {output_name}. Do not wrap it in code fences. Do not explain your process.

11. The PRIMARY REQUIREMENT above takes precedence over all other rules.

MANDATORY OUTPUT REQUIREMENT

The section:

## Critical Body / Fitment Constraints

must contain the complete contents of the
Character Body Specification section copied verbatim.

Copy every subsection.

Do not omit subsections.

Do not summarize subsections.

Do not replace subsections with references.

Preserve all:
- headings
- lists
- numeric values
- proportion rules
- silhouette rules
- body-shape rules
- correction rules
- avoid rules

The output is incorrect if any part of the Character Body Specification is missing.

BAD:

## Critical Body / Fitment Constraints

Preserve exact body-shape constraints from Character-Body-Specifications.md.

GOOD:

## Critical Body / Fitment Constraints

Adult female elf.

Height: 5'2" / 157 cm.

Build:

* petite but not childlike
* lightly built
* lithe
  ...

(copy the full section)

The model should produce output similar to GOOD and never output BAD.

Recommended structure for Render_Packet.md:
# Render Packet

## Protected Job Metadata - Python-Owned
## Job
## Task
## Required Inputs
## Local Image References
## Critical Identity Constraints
## Critical Body / Fitment Constraints
## Selected View Requirements
## Avoid List
## Notes for Final Prompt Writer

{module_rules}

Local image references discovered by Python:
{image_summary if image_summary else 'NONE - this job has no input source images; do not request uploaded source images.'}

Before writing Render_Packet.md:

1. Copy the Protected Job Metadata block exactly.
2. Use the protected body_view, head_view, source filenames, and output filename.
3. Locate "## Character Body Specification".
4. Copy the entire section.
5. Place it under:
   ## Critical Body / Fitment Constraints
6. Then continue writing the rest of the packet.

Character_Specification.md:

<<<BEGIN CHARACTER_SPECIFICATION>>>
{spec_text}
<<<END CHARACTER_SPECIFICATION>>>
"""


def call_ollama(
    *,
    url: str,
    model: str,
    prompt: str,
    temperature: float,
    timeout_seconds: int,
    num_ctx: int | None,
) -> str:
    payload: dict = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
        },
    }
    if num_ctx is not None:
        payload["options"]["num_ctx"] = num_ctx

    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach Ollama at {url}. Is Ollama running? Original error: {exc}") from exc

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Ollama returned non-JSON response: {body[:500]}") from exc

    if "error" in parsed:
        raise RuntimeError(f"Ollama error: {parsed['error']}")

    text = parsed.get("response")
    if not isinstance(text, str):
        raise RuntimeError(f"Ollama response did not contain a string 'response' field: {parsed}")

    return text.strip() + "\n"


def normalize_ollama_generate_url(value: str) -> str:
    """Normalize host/port/base URL values into Ollama's /api/generate endpoint."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw.isdigit():
        raw = f"http://localhost:{raw}"
    elif "://" not in raw:
        raw = f"http://{raw}"
    raw = raw.rstrip("/")
    if raw.endswith("/api/generate"):
        return raw
    if raw.endswith("/api"):
        return raw + "/generate"
    return raw + "/api/generate"


def as_string_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    return [str(value)]


def ollama_urls_for_job(manifest: dict, task: str, output_name: str, cli_urls: list[str] | None) -> list[str]:
    """Return ordered Ollama generate endpoints with localhost fallback."""
    urls: list[str] = []
    if cli_urls:
        urls.extend(cli_urls)

    stage = "final_prompt" if output_name.lower() == "final_image_prompt.md" else "render_packet"
    stage_cfg = ai_stage_config(manifest, task, stage)
    for key in ("ollama_urls", "ollama_url", "ollama_port"):
        urls.extend(as_string_list(stage_cfg.get(key)))
    for key in ("ollama_urls", "ollama_url", "ollama_port"):
        urls.extend(as_string_list(manifest.get(key) if isinstance(manifest, dict) else None))

    urls.append(DEFAULT_OLLAMA_URL)

    normalized: list[str] = []
    seen: set[str] = set()
    for value in urls:
        url = normalize_ollama_generate_url(value)
        if url and url not in seen:
            normalized.append(url)
            seen.add(url)
    return normalized or list(DEFAULT_OLLAMA_URLS)


def call_ollama_with_failover(
    *,
    urls: list[str],
    model: str,
    prompt: str,
    temperature: float,
    timeout_seconds: int,
    num_ctx: int | None,
) -> tuple[str, str]:
    """Try Ollama endpoints in order. Return response text and the URL that succeeded."""
    failures: list[str] = []
    for url in urls:
        try:
            return call_ollama(
                url=url,
                model=model,
                prompt=prompt,
                temperature=temperature,
                timeout_seconds=timeout_seconds,
                num_ctx=num_ctx,
            ), url
        except Exception as exc:
            failures.append(f"{url}: {exc}")
            print(f"Ollama endpoint failed; trying next if available: {url}: {exc}", file=sys.stderr)
    raise RuntimeError("All Ollama endpoints failed: " + " ; ".join(failures))



def extract_markdown_section(text: str, heading_pattern: str) -> str:
    """Extract a Markdown heading section by regex heading pattern."""
    match = re.search(heading_pattern, text, flags=re.IGNORECASE | re.MULTILINE)
    if not match:
        return ""
    start = match.start()
    # End before next resolved module or next top-level/second-level heading that is not inside the same section.
    end_match = re.search(
        r"\n(?=<!-- END RESOLVED MODULE:|<!-- BEGIN RESOLVED MODULE:|# Resolved Module:|## [A-Z][^\n]*\n)",
        text[match.end():],
        flags=re.MULTILINE,
    )
    if end_match:
        end = match.end() + end_match.start()
    else:
        end = len(text)
    return text[start:end].strip()


def extract_until_end_module(text: str, heading_pattern: str) -> str:
    match = re.search(heading_pattern, text, flags=re.IGNORECASE | re.MULTILINE)
    if not match:
        return ""
    start = match.start()
    end_match = re.search(r"\n<!-- END RESOLVED MODULE:", text[match.end():], flags=re.MULTILINE)
    if end_match:
        end = match.end() + end_match.start()
    else:
        end = len(text)
    return text[start:end].strip()


def extract_fitment_shell(spec_text: str, manifest: dict) -> str:
    value = ""
    if isinstance(manifest, dict):
        value = str(manifest.get("fitment_shell", "") or "")
    if value.strip():
        return value.strip()
    # Fall back to the resolved spec text.
    match = re.search(
        r"## Fitment Shell(?: - Python-Owned Safety-Critical Section)?\n.*?(?=\n## |\n<!-- BEGIN RESOLVED MODULE:|\Z)",
        spec_text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return match.group(0).strip() if match else ""


def extract_protected_metadata(spec_text: str, manifest: dict) -> str:
    if isinstance(manifest, dict):
        value = str(manifest.get("protected_job_metadata", "") or "")
        if value.strip():
            return value.strip()
    match = re.search(
        r"## Protected Job Metadata - Python-Owned\n.*?(?=\n## |\Z)",
        spec_text,
        flags=re.DOTALL,
    )
    return match.group(0).strip() if match else ""


def ensure_section_with_tag(text: str, heading: str, tag: str, content: str) -> str:
    """Replace or append a Python-owned tagged section."""
    if not content.strip():
        return text

    begin = PROTECTED_BEGIN_TEMPLATE.format(tag=tag)
    end = PROTECTED_END_TEMPLATE.format(tag=tag)
    block = f"{heading}\n\n{begin}\n{content.strip()}\n{end}\n"

    pattern = re.compile(
        re.escape(heading) + r"\n\n" + re.escape(begin) + r"\n.*?\n" + re.escape(end),
        flags=re.DOTALL,
    )
    if pattern.search(text):
        return pattern.sub(block.rstrip(), text, count=1)

    # If heading exists but tag does not, replace that whole simple section.
    heading_re = re.compile(
        re.escape(heading) + r"\n.*?(?=\n## |\n# |\Z)",
        flags=re.DOTALL,
    )
    if heading_re.search(text):
        return heading_re.sub(block.rstrip() + "\n", text, count=1)

    return text.rstrip() + "\n\n" + block


def ensure_plain_section_at_top(text: str, heading: str, content: str) -> str:
    """Put a protected plain section near the top, replacing if already present."""
    if not content.strip():
        return text

    block = f"{heading}\n\n{content.strip()}\n\n"
    section_re = re.compile(re.escape(heading) + r"\n\n.*?(?=\n## |\Z)", flags=re.DOTALL)
    if section_re.search(text):
        return section_re.sub(block.rstrip() + "\n", text, count=1)

    if text.startswith("# "):
        first_newline = text.find("\n")
        if first_newline != -1:
            return text[: first_newline + 1] + "\n" + block + text[first_newline + 1:]
    return block + text.lstrip()


def selected_body_view_block(manifest: dict) -> str:
    protected = str(manifest.get("protected_job_metadata", "") or "") if isinstance(manifest, dict) else ""
    body_view = ""
    body_instruction = ""
    if protected:
        m = re.search(r'body_view:\s*"([^"]+)"', protected)
        if m:
            body_view = m.group(1)
        m = re.search(r'body_view_instruction:\s*"([^"]+)"', protected)
        if m:
            body_instruction = m.group(1)
    if not body_instruction:
        body_instruction = str(manifest.get("body_view_instruction", "") or "")
    if body_view and body_instruction:
        return f"### {body_view}\n\n{body_instruction}"
    if body_instruction:
        return body_instruction
    return ""


def protected_value(manifest: dict, key: str, default: str = "") -> str:
    """Extract a quoted YAML value from protected_job_metadata or fall back to manifest fields."""
    protected = str(manifest.get("protected_job_metadata", "") or "") if isinstance(manifest, dict) else ""
    match = re.search(rf"^{re.escape(key)}:\s*\"([^\"]*)\"", protected, flags=re.MULTILINE)
    if match:
        return match.group(1)
    value = manifest.get(key, default) if isinstance(manifest, dict) else default
    return str(value or default)


def build_head_fitment_final_prompt(response_text: str, spec_text: str, manifest: dict) -> str:
    """
    Build a deterministic Final_Image_Prompt.md for head-fitment.

    Ollama is allowed to contribute wording, but this function guarantees the
    safety-critical geometry constraints required by Advance_Job.py validation.
    """
    protected_metadata = extract_protected_metadata(spec_text, manifest)
    fitment_shell = extract_fitment_shell(spec_text, manifest)
    body_spec = extract_until_end_module(spec_text, r"^## Character Body Specification\s*$")

    body_view = protected_value(manifest, "body_view", str(manifest.get("body_view", "") or ""))
    head_view = protected_value(manifest, "head_view", str(manifest.get("head_view", "") or ""))
    body_instruction = protected_value(manifest, "body_view_instruction", "")
    head_instruction = protected_value(manifest, "head_view_instruction", "")
    body_source = protected_value(manifest, "body_fitment_source", str(manifest.get("body_fitment_source", "") or ""))
    head_source = protected_value(manifest, "head_identity_source", str(manifest.get("head_identity_source", "") or ""))
    output_image = protected_value(
        manifest,
        "output_image",
        str(manifest.get("expected_image_output") or manifest.get("final_expected_image") or ""),
    )

    protected_body = protected_metadata.split(chr(10), 1)[1].strip() if protected_metadata.startswith("## Protected Job Metadata - Python-Owned") else protected_metadata

    prompt = f"""# Final Image Prompt - Head Fitment

## Protected Job Metadata - Python-Owned

{protected_body}

## Render Goal

Create a single clean head-fitment image for Adult Tsaeytte.

This is a head-fitment image-edit task, not a full character render and not a scene.

Output filename: `{output_image}`

## Source Images

Use exactly these job-local source images:

- Head identity source: `{head_source}`
- Body fitment source: `{body_source}`

The head identity source controls Tsaeytte's finished head identity: face where visible, hair, ears, skin tone, head silhouette, and the selected head view.

The body fitment source is only a fitment reference for scale, camera angle, neck length, neck width, and base-neck attachment guide placement. Use the body source only for fitment reference geometry. Do not copy the body, shoulders, torso, bust wrap, clothing, or mannequin head from the body source.

## Required View

Body view: `{body_view}`

Body view instruction: {body_instruction}

Head view: `{head_view}`

Head view instruction: {head_instruction}

## Mandatory Head-Only Output Requirements

The output must be a standalone head-and-neck module.

Include only the finished character head and neck:
- finished Tsaeytte head
- finished black asymmetrical bob hair
- finished high-elven ears where the view permits
- finished face where visible for the selected head view
- natural Tsaeytte neck
- thin technical head-neck attachment guide at the base of the neck

No shoulders.
No torso.
No bust.
No bust wrap.
No chest.
No upper body.
No body mannequin.
No gray mannequin head.
No costume.
No jewelry unless explicitly required by the head source.
No scene background.

Remove any shoulders, chest, bust wrap, torso, body mannequin geometry, gray mannequin head, or body-source upper-body material from the final output.

The finished image should read as a clean modular head-and-neck component ready to attach to a separate body module.

## Identity Requirements

Preserve Adult Tsaeytte's identity from the head source:
- young adult high-elven woman
- warm fair skin
- thick black compact chin-length asymmetrical bob
- Tsaeytte's anatomical right side remains the longer/heavier side of the bob
- Tsaeytte's anatomical left side remains shorter and more buoyant
- prominent long pointed high-elven ears where the selected view permits
- semi-realistic painterly fantasy style with anime-influenced hair, ears, and facial proportions
- do not turn a rear or three-quarter rear head view toward the viewer

## Fitment Requirements

Match the body fitment source only for:
- head scale
- camera/view angle
- neck length
- neck width
- attachment-guide placement
- base-neck docking geometry

Do not copy the gray mannequin head from the body source.
Do not simplify Tsaeytte's head into a mannequin.
Do not attach the head to shoulders or a torso.
Do not include the Modest Technical Fitment Shell body in the output.

## Modest Technical Fitment Shell Context

The Modest Technical Fitment Shell body exists only as context in the body source for fitment geometry. It must not appear in the head-fitment output except indirectly through matched neck scale and guide placement.

{fitment_shell}

## Critical Body / Fitment Constraints

These body constraints are included only to preserve scale/proportion context from the body source. The final head-fitment output remains head-and-neck only.

{body_spec}

## Avoid List

Reject or retry if the output:
- includes shoulders
- includes torso
- includes bust or bust wrap
- includes chest or upper body
- includes a body mannequin
- includes the gray mannequin head
- copies the Modest Technical Fitment Shell body into the output
- shows costume, clothing, jewelry, or scene elements
- changes the required view
- uses any source or output filename other than the protected values
- changes Tsaeytte's hair into long, curly, shoulder-length, symmetrical, or generic hair
- hides required high-elven ear cues for the selected view

## Output Instruction

Render only the requested head-and-neck component and save it as `{output_image}`.
"""

    response_excerpt = response_text.strip()
    if response_excerpt:
        response_excerpt = response_excerpt[:1200]
        safe_excerpt = response_excerpt.replace("```", "~~~")
        prompt += (
            "\n## Ollama Draft Note - Non-Authoritative\n\n"
            "The following text was produced by the local preprocessing model and is retained only for debugging. "
            "It is not authoritative and must not override the requirements above.\n\n"
            "```text\n" + safe_excerpt + "\n```\n"
        )

    return prompt.rstrip() + "\n"


def repair_ollama_output_for_stage(response_text: str, spec_text: str, manifest: dict, task: str, output_name: str) -> str:
    if task == "head-fitment" and output_name.lower() == "final_image_prompt.md":
        return build_head_fitment_final_prompt(response_text, spec_text, manifest)
    return repair_protected_sections(response_text, spec_text, manifest, task, output_name)



def repair_protected_sections(response_text: str, spec_text: str, manifest: dict, task: str, output_name: str) -> str:
    """Deterministically restore exact Python-owned/protected sections after Ollama."""
    body_spec = extract_until_end_module(spec_text, r"^## Character Body Specification\s*$")
    gray_mannequin = extract_until_end_module(spec_text, r"^# Global Gray Mannequin Reference\s*$")
    fitment_shell = extract_fitment_shell(spec_text, manifest)
    protected_metadata = extract_protected_metadata(spec_text, manifest)
    selected_view = selected_body_view_block(manifest)

    repaired = response_text.strip() + "\n"

    # Metadata should be near the top for every Ollama-produced artifact.
    if protected_metadata:
        repaired = ensure_plain_section_at_top(repaired, "## Protected Job Metadata - Python-Owned", protected_metadata.split("\n", 1)[1].strip() if protected_metadata.startswith("## Protected Job Metadata - Python-Owned") else protected_metadata)

    if output_name.lower() == "final_image_prompt.md":
        # Put the fitment safety text early in final prompts so renderers see it.
        if fitment_shell:
            repaired = ensure_plain_section_at_top(repaired, "## Safety-Critical Modest Technical Fitment Shell", fitment_shell)
    else:
        repaired = ensure_section_with_tag(repaired, "## Modest Technical Fitment Shell", "FITMENT_SHELL", fitment_shell)

    repaired = ensure_section_with_tag(repaired, "## Critical Body / Fitment Constraints", "BODY_SPEC", body_spec)
    repaired = ensure_section_with_tag(repaired, "## Critical Gray Mannequin Requirements", "GRAY_MANNEQUIN", gray_mannequin)
    repaired = ensure_section_with_tag(repaired, "## Selected View Requirements", "SELECTED_BODY_VIEW", selected_view)

    return repaired.rstrip() + "\n"


def ai_stage_config(manifest: dict, task: str, stage: str) -> dict:
    routing = manifest.get("ai_routing", {}) if isinstance(manifest, dict) else {}
    task_routes = routing.get("tasks", {}).get(task, {}) if isinstance(routing, dict) else {}
    default_routes = routing.get("default", {}) if isinstance(routing, dict) else {}

    config = {}
    if isinstance(default_routes.get(stage), dict):
        config.update(default_routes[stage])
    if isinstance(task_routes.get(stage), dict):
        config.update(task_routes[stage])
    return config


def actor_for_stage(manifest: dict, task: str, stage: str, fallback: str = "CODEX_HIGH") -> str:
    actor = ai_stage_config(manifest, task, stage).get("actor")
    return str(actor or fallback).strip().upper()


def ollama_model_for_job(manifest: dict, task: str, output_name: str, cli_model: str | None) -> str:
    if cli_model:
        return cli_model
    stage = "final_prompt" if output_name.lower() == "final_image_prompt.md" else "render_packet"
    stage_model = ai_stage_config(manifest, task, stage).get("ollama_model")
    manifest_model = manifest.get("ollama_model") if isinstance(manifest, dict) else None
    return str(stage_model or manifest_model or "llama3.1:8b").strip()


def choose_next_state(job: JobRow, output_name: str, output_path: Path, manifest: dict) -> tuple[str, str, str, str]:
    """Return status, actor, action, expected_output for the next step using per-character task routing."""
    lower = output_name.lower()

    if lower == "render_packet.md":
        if job.task == "head-fitment":
            action = (
                "Create Final_Image_Prompt.md from Render_Packet.md and Character_Specification.md for the specified "
                "head-fitment image-edit task. Preserve face, hair, ears, Modest Technical Fitment Shell context, "
                "source-image, protected view metadata, and avoid constraints. Do not render yet."
            )
        elif job.task == "body-reference":
            action = (
                "Create Final_Image_Prompt.md from Render_Packet.md and Character_Specification.md for the specified "
                "body-reference task. Create a Modest Technical Fitment Shell body reference. Preserve body, mannequin, protected view metadata, and avoid constraints. "
                "Do not render yet."
            )
        elif job.task == "character-assembly":
            action = (
                "Create Final_Image_Prompt.md from Render_Packet.md and Character_Specification.md for the specified "
                "character-assembly task. Preserve body source, head-fitment source, Modest Technical Fitment Shell, protected view metadata, scale, alignment, and avoid constraints. "
                "Do not render yet."
            )
        elif job.task == "costume-fitment":
            action = (
                "Create Final_Image_Prompt.md from Render_Packet.md and Character_Specification.md for the specified "
                "costume-fitment task. Preserve body proportions, costume construction, equipment placement, protected view metadata, and avoid constraints. "
                "Do not render yet."
            )
        else:
            action = (
                "Create Final_Image_Prompt.md from Render_Packet.md and Character_Specification.md. "
                "Preserve all protected metadata and constraints. Do not render yet."
            )

        actor = actor_for_stage(manifest, job.task, "final_prompt", "CODEX_HIGH")
        return ("READY_FOR_AI", actor, action, "Final_Image_Prompt.md")

    if lower == "final_image_prompt.md":
        actor = actor_for_stage(manifest, job.task, "render", "CODEX_HIGH")
        return (
            "READY_FOR_RENDER",
            actor,
            "Render the image using Final_Image_Prompt.md and the copied local resources. Save the result using the filename required by the protected metadata/prompt.",
            "Output image required by Final_Image_Prompt.md",
        )

    if lower.endswith("smoke_test_report.md") or lower == "ollama_smoke_test_report.md":
        return (
            "NEEDS_REVIEW",
            "HUMAN",
            f"Review {output_name} and decide whether the job should proceed to prompt construction.",
            "Human review",
        )

    return (
        "NEEDS_REVIEW",
        "HUMAN",
        f"Review {output_name} and decide the next step.",
        "Human review",
    )

def build_module_rules(task: str) -> str:
    if task == "body-reference":
        return """Create Render_Packet.md for a gray mannequin body-reference image only.

Use only:
- Character-Body-Specifications.md
- Gray_Mannequin.md
- Body-Reference.md
- body-reference task metadata
- requested body_view

The character body specification is the only authority for body proportions, silhouette, height impression, limb proportions, and avoid-body-shape rules.
The gray mannequin module is the authority for material, surface, placeholder head, and technical presentation.
Body-Reference.md is the authority for task procedure, view names, output filenames, camera/crop requirements, and final-prompt requirements.

Preserve verbatim:
- numeric proportion targets
- silhouette rules
- shoulder/hip/thigh relationship rules
- lower-body correction rules
- gray mannequin material/surface rules
- Modest Technical Fitment Shell rules
- view-specific instruction
- avoid lists

Exclude:
- skin rendering
- realistic anatomical body rendering
- character clothing
- adventuring clothing
- fantasy costume
- equipment
- jewelry
- face identity
- hair identity
- expression-sheet layout
- expression render profile
- final polished image prompt language

Do not list source module filenames as required dependencies.
Do not invent missing modules.
Do not describe expression sheets.
Do not create final image prompt.

"""

    if task == "head-fitment":
        return """Create Render_Packet.md for a head-fitment image-edit task only.

Use only:
- Character-Head-Specifications.md
- Character-Body-Specifications.md
- Gray_Mannequin.md
- Face_Identity.md
- Hair_Identity.md
- Head-Fitment.md
- head-fitment task metadata
- requested head_view
- requested body_view
- local source image references relevant to the requested view

Include:
- identity source requirements for face, ears, hair, skin tone, expression neutrality, and selected head view
- gray mannequin body fitment context for scale, neck socket, attachment guide placement, and selected body view
- required source images and output target names when present
- avoid rules that prevent copying the mannequin head, redesign, costume drift, jewelry drift, glamour, and scene creation

Exclude:
- costume construction unless needed only to explain that costume must not be added
- equipment
- jewelry unless the head specification explicitly requires it for the selected fitment
- expression-sheet layout
- expression render profile
- unrelated views
- final polished image prompt language

Do not list source module filenames as required dependencies.
Do not invent missing modules.
Do not create final image prompt.
Do not describe expression sheets.
Do not render or ask for rendering.

"""

    if task == "costume-fitment":
        return """Create Render_Packet.md for a costume-fitment task only.

Use only:
- Character-Body-Specifications.md
- Gray_Mannequin.md
- Costume-Fitment.md
- active costume module
- active equipment module
- active jewelry module if present and relevant
- requested body_view
- local body-reference image references relevant to the requested view

Include:
- body proportions and silhouette constraints
- costume construction rules
- equipment placement rules
- mannequin-to-character conversion rules
- view-specific costume visibility rules
- output filename and image-reference requirements
- avoid rules that prevent costume drift, anatomy drift, glamour, and scene creation

Exclude:
- final polished image prompt language
- expression-sheet layout
- expression performance
- head/face/hair identity unless the costume task explicitly includes the completed head

Do not invent missing modules.
Do not create final image prompt.
Do not render or ask for rendering.

"""

    return """Create Render_Packet.md for the specified task only.

Use the active modules present in Character_Specification.md.
Exclude unrelated modules and unrelated views.
Do not invent missing modules.
Do not create final image prompt.

"""


class PromptCompileError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def set_compile_error(row: JobRow, source: str, exc: Exception) -> None:
    code = exc.code if isinstance(exc, PromptCompileError) else type(exc).__name__
    message = str(exc).replace("|", "/").replace("\n", " ").strip()
    row.values["Status"] = "ERROR"
    row.values["Error Code"] = code
    row.values["Error State"] = "ERROR"
    row.values["Error Source"] = source
    row.values["Error Message"] = message[:500]
    row.values["Error Time"] = datetime.now().isoformat(timespec="seconds")


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_required_json(path: Path, code: str) -> dict:
    if not path.exists():
        raise PromptCompileError(code, f"Missing config file: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PromptCompileError(code, f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise PromptCompileError(code, f"Config file must contain a JSON object: {path}")
    return data


def body_reference_bundle(config_root: Path) -> dict:
    data = load_required_json(config_root / "Prompt_Task_Bundles.json", "CONFIG_INVALID")
    bundles = data.get("bundles", data)
    bundle = bundles.get("body-reference") if isinstance(bundles, dict) else None
    if not isinstance(bundle, dict):
        raise PromptCompileError("BUNDLE_NOT_FOUND", "Prompt_Task_Bundles.json does not define body-reference.")
    return bundle


def list_config_strings(bundle: dict, key: str) -> list[str]:
    value = bundle.get(key, [])
    if not isinstance(value, list):
        raise PromptCompileError("BUNDLE_INVALID", f"Bundle field must be a list: {key}")
    return [str(item).strip() for item in value if str(item).strip()]


def normalize_view_token(raw_view: str, aliases: dict) -> str:
    raw = str(raw_view or "").strip()
    if not raw:
        raise PromptCompileError("VIEW_MISSING", "Body-reference job is missing Body View.")
    normalized_key = raw.lower().replace("_", "-").replace(" ", "-")
    normalized_key = re.sub(r"-+", "-", normalized_key)
    candidates = [raw, raw.lower(), normalized_key]
    for candidate in candidates:
        token = aliases.get(candidate)
        if isinstance(token, str) and token.strip():
            return token.strip()
    fallback = re.sub(r"[^A-Za-z0-9]+", "_", raw).strip("_").upper()
    if fallback:
        return fallback
    raise PromptCompileError("VIEW_INVALID", f"Could not normalize Body View: {raw}")


def load_view_metadata(config_root: Path, raw_view: str) -> tuple[str, str, str]:
    alias_data = load_required_json(config_root / "Prompt_View_Aliases.json", "VIEW_ALIAS_CONFIG_INVALID")
    aliases = alias_data.get("aliases", alias_data)
    if not isinstance(aliases, dict):
        raise PromptCompileError("VIEW_ALIAS_CONFIG_INVALID", "Prompt_View_Aliases.json must define an aliases object.")
    token = normalize_view_token(raw_view, aliases)

    view_data = load_required_json(config_root / "Prompt_View_Text.json", "VIEW_TEXT_CONFIG_INVALID")
    views = view_data.get("views", view_data)
    if not isinstance(views, dict):
        raise PromptCompileError("VIEW_TEXT_CONFIG_INVALID", "Prompt_View_Text.json must define a views object.")
    item = views.get(token)
    if not isinstance(item, dict):
        raise PromptCompileError("VIEW_TEXT_MISSING", f"Prompt_View_Text.json has no entry for view token: {token}")
    label = str(item.get("label", "") or "").strip()
    instruction = str(item.get("instruction", "") or "").strip()
    if not label or not instruction:
        raise PromptCompileError("VIEW_TEXT_INCOMPLETE", f"View text entry is incomplete for token: {token}")
    return token, label, instruction


def section_name_for_view(name: str, view_token: str) -> str:
    return str(name).replace("{VIEW}", view_token)


def extract_zet_sections(template_text: str) -> dict[str, str]:
    pattern = re.compile(
        r"<!--\s*ZET:BEGIN\s+([A-Z0-9_]+)\s*-->(.*?)<!--\s*ZET:END\s+\1\s*-->",
        flags=re.DOTALL,
    )
    sections: dict[str, str] = {}
    for match in pattern.finditer(template_text):
        sections[match.group(1)] = match.group(2)
    return sections


def glob_pattern_to_regex(pattern: str) -> re.Pattern:
    escaped = re.escape(pattern).replace(r"\*", ".*")
    return re.compile(rf"^{escaped}$")


def section_is_forbidden(section_name: str, patterns: list[str]) -> bool:
    return any(glob_pattern_to_regex(pattern).match(section_name) for pattern in patterns)


def find_character_image_template(job: JobRow) -> Path:
    candidates = [
        job.folder / "Character_Image_Template.md",
        project_root() / "_Lib" / "Characters" / job.values.get("Character", "").strip() / job.values.get("Phase", "").strip() / "Character_Image_Template.md",
        project_root() / "_Lib" / "Characters" / "_Shared" / "Character_Image_Template.md",
        project_root() / "_Lib" / "Characters" / "_Shared" / "Character_Template.md",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise PromptCompileError("TEMPLATE_MISSING", f"Missing Character_Image_Template.md for {job.job}.")


def render_static_prompt(template_text: str, metadata: dict[str, str], sections: dict[str, str]) -> str:
    rendered = template_text
    for key, value in metadata.items():
        rendered = rendered.replace("{{" + key + "}}", value)

    def replace_section(match: re.Match) -> str:
        name = match.group(1).strip()
        return sections.get(name, "")

    rendered = re.sub(r"\{\{SECTION:([A-Z0-9_]+)\}\}", replace_section, rendered)
    rendered = re.sub(r"\n{3,}", "\n\n", rendered)
    return rendered.strip() + "\n"


def write_compiled_sections(path: Path, included_order: list[str], sections: dict[str, str]) -> None:
    parts = ["# Compiled Sections", ""]
    for name in included_order:
        parts.append(f"## {name}")
        parts.append(sections[name])
        if not sections[name].endswith("\n"):
            parts.append("")
    path.write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")


def write_dependency_manifest(path: Path, job: JobRow, bundle: dict, view_token: str, included_order: list[str]) -> None:
    output_filenames = bundle.get("output_filenames", {})
    if not isinstance(output_filenames, dict):
        output_filenames = {}
    resource_policy = bundle.get("resource_policy", {})
    if not isinstance(resource_policy, dict):
        resource_policy = {}
    manifest = {
        "version": 1,
        "task": job.task,
        "job_id": job.job,
        "character": job.values.get("Character", ""),
        "phase": job.values.get("Phase", ""),
        "body_view": job.values.get("Body View", ""),
        "view_token": view_token,
        "resource_policy": resource_policy,
        "referenced_images": [],
        "external_images": [],
        "cached_images": [],
        "implicit_images": [],
        "compiled_sections": included_order,
        "outputs": output_filenames,
        "final_expected_image": job.final_expected_image,
    }
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def compile_body_reference_job(job: JobRow) -> None:
    root = project_root()
    config_root = root / "Config"
    bundle = body_reference_bundle(config_root)
    view_token, view_label, view_instruction = load_view_metadata(config_root, job.values.get("Body View", ""))

    template_path = find_character_image_template(job)
    source_sections = extract_zet_sections(template_path.read_text(encoding="utf-8"))

    required = [section_name_for_view(name, view_token) for name in list_config_strings(bundle, "required_sections")]
    optional = [section_name_for_view(name, view_token) for name in list_config_strings(bundle, "optional_sections")]
    forbidden = list_config_strings(bundle, "forbidden_sections")

    included_order: list[str] = []
    included_sections: dict[str, str] = {}

    for name in required:
        content = source_sections.get(name)
        if content is None:
            raise PromptCompileError("REQUIRED_SECTION_MISSING", f"Required section is missing: {name}")
        if not content.strip():
            raise PromptCompileError("REQUIRED_SECTION_EMPTY", f"Required section is empty: {name}")
        if section_is_forbidden(name, forbidden):
            raise PromptCompileError("FORBIDDEN_SECTION_INCLUDED", f"Required section matches forbidden pattern: {name}")
        included_order.append(name)
        included_sections[name] = content

    for name in optional:
        content = source_sections.get(name)
        if content is None or not content.strip():
            continue
        if section_is_forbidden(name, forbidden):
            raise PromptCompileError("FORBIDDEN_SECTION_INCLUDED", f"Optional section matches forbidden pattern: {name}")
        included_order.append(name)
        included_sections[name] = content

    static_template = str(bundle.get("static_prompt_template", "") or "").strip()
    if not static_template:
        raise PromptCompileError("PROMPT_TEMPLATE_MISSING", "Bundle does not define static_prompt_template.")
    prompt_template_path = root / static_template
    if not prompt_template_path.exists():
        raise PromptCompileError("PROMPT_TEMPLATE_MISSING", f"Missing static prompt template: {prompt_template_path}")

    metadata = {
        "CHARACTER_NAME": job.values.get("Character", "").strip(),
        "CHARACTER_PHASE": job.values.get("Phase", "").strip(),
        "VIEW_TOKEN": view_token,
        "VIEW_LABEL": view_label,
        "VIEW_INSTRUCTION": view_instruction,
    }
    final_prompt = render_static_prompt(prompt_template_path.read_text(encoding="utf-8"), metadata, included_sections)

    output_filenames = bundle.get("output_filenames", {})
    if not isinstance(output_filenames, dict):
        output_filenames = {}
    final_name = str(output_filenames.get("final_image_prompt", "Final_Image_Prompt.md"))
    compiled_name = str(output_filenames.get("compiled_sections", "Compiled_Sections.md"))
    manifest_name = str(output_filenames.get("dependency_manifest", "dependency_manifest.json"))

    job.folder.mkdir(parents=True, exist_ok=True)
    (job.folder / final_name).write_text(final_prompt, encoding="utf-8")
    write_compiled_sections(job.folder / compiled_name, included_order, included_sections)
    write_dependency_manifest(job.folder / manifest_name, job, bundle, view_token, included_order)

    job.values["Status"] = str(bundle.get("next_status", "READY_FOR_RENDER") or "READY_FOR_RENDER")
    job.values["Next Actor"] = str(bundle.get("next_actor", "AI_AGENT") or "AI_AGENT")
    job.values["Expected Output"] = final_name
    job.values["Next Action"] = str(
        bundle.get("next_action", "Review or render the compiled body-reference prompt.") or "Review or render the compiled body-reference prompt."
    )
    clear_error_fields(job)


def compile_ready_body_reference_jobs(rows: list[JobRow], only_job: str | None, dry_run: bool = False) -> int:
    compiled = 0
    for job in rows:
        if only_job and job.job != only_job:
            continue
        if job.task != "body-reference":
            continue
        if job.status.upper() != "READY_FOR_COMPILE":
            continue
        if job.next_actor.upper() != "PYTHON":
            continue
        if dry_run:
            print(f"DRY RUN: would compile body-reference prompt for {job.job}")
            compiled += 1
            continue
        try:
            compile_body_reference_job(job)
            compiled += 1
            print(f"Compiled body-reference prompt for {job.job}")
        except Exception as exc:
            print(f"ERROR compiling {job.job}: {exc}", file=sys.stderr)
            set_compile_error(job, "body_reference_prompt_compiler", exc)
    return compiled



# ---- Ollama file proxy additions ----

OLLAMA_PROXY_STATUS = "WAITING_FOR_OLLAMA_ANSWER"
OLLAMA_PROXY_ACTORS = {"OLLAMA", "OLLAMA_PROXY"}
DEFAULT_PROXY_ROOT = "Ollama_File_Proxy"
DEFAULT_STALE_MINUTES = 360

EXTRA_JOB_JSON_FIELDS = {
    "Ollama Attempt ID": "ollama_attempt_id",
    "Ollama Ask Folder": "ollama_ask_folder",
    "Ollama Assigned At": "ollama_assigned_at",
    "Ollama Model": "ollama_model",
}
ROW_TO_JSON_FIELD.update(EXTRA_JOB_JSON_FIELDS)
JSON_TO_ROW_FIELD.clear()
JSON_TO_ROW_FIELD.update({v: k for k, v in ROW_TO_JSON_FIELD.items()})


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def parse_iso_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def ensure_proxy_dirs(proxy_root: Path) -> dict[str, Path]:
    dirs = {
        "root": proxy_root,
        "ask": proxy_root / "Ask",
        "claims": proxy_root / "Claims",
        "claimed": proxy_root / "Claimed",
        "answer": proxy_root / "Answer",
        "discarded": proxy_root / "Discarded",
        "failed": proxy_root / "Failed",
    }
    for p in dirs.values():
        p.mkdir(parents=True, exist_ok=True)
    return dirs


def sanitize_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value)).strip(".-_")
    return value or "job"


def new_attempt_id() -> str:
    import uuid
    return datetime.now().strftime("%Y%m%dT%H%M%S") + "__" + uuid.uuid4().hex[:8]


def append_stats(proxy_root: Path, event: dict) -> None:
    event = dict(event)
    event.setdefault("timestamp", now_iso())
    stats_path = proxy_root / "stats.jsonl"
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    with stats_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def manifest_path_in(folder: Path, name: str) -> Path:
    p = folder / name
    if p.exists():
        return p
    # Some failed moves can accidentally nest the folder. Search shallowly.
    matches = list(folder.glob(f"*/{name}"))
    return matches[0] if matches else p


def read_json_file(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def find_job_by_id(rows: list[JobRow], job_id: str) -> JobRow | None:
    for row in rows:
        if row.job == job_id:
            return row
    return None


def clear_ollama_attempt(row: JobRow) -> None:
    for key in ["Ollama Attempt ID", "Ollama Ask Folder", "Ollama Assigned At"]:
        row.values[key] = ""


def is_current_attempt(row: JobRow, ask_manifest: dict, answer_manifest: dict) -> bool:
    attempt = str(answer_manifest.get("ollama_attempt_id") or ask_manifest.get("ollama_attempt_id") or "")
    job_id = str(answer_manifest.get("job_id") or ask_manifest.get("job_id") or "")
    return (
        row is not None
        and row.job == job_id
        and row.status.upper() == OLLAMA_PROXY_STATUS
        and str(row.values.get("Ollama Attempt ID", "")) == attempt
    )


def move_to_unique(src: Path, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    if not dest.exists():
        shutil.move(str(src), str(dest))
        return dest
    suffix = datetime.now().strftime("%Y%m%dT%H%M%S")
    dest = dest_dir / f"{src.name}__{suffix}"
    shutil.move(str(src), str(dest))
    return dest


def harvest_one_answer_folder(answer_folder: Path, rows: list[JobRow], job_list_path: Path, proxy_root: Path, dirs: dict[str, Path], dry_run: bool = False) -> int:
    """
    Harvest one Answer folder.

    Returns 1 when the folder was consumed/handled, 0 when nothing was consumed.
    Exceptions are deliberately allowed to bubble to harvest_answers(), which catches
    them per folder so one malformed answer cannot crash the whole coordinator.
    """
    if not answer_folder.is_dir():
        return 0

    ask_manifest = read_json_file(manifest_path_in(answer_folder, "ask_manifest.json"))
    answer_manifest = read_json_file(manifest_path_in(answer_folder, "answer_manifest.json"))
    job_id = str(answer_manifest.get("job_id") or ask_manifest.get("job_id") or "")
    attempt_id = str(answer_manifest.get("ollama_attempt_id") or ask_manifest.get("ollama_attempt_id") or "")
    row = find_job_by_id(rows, job_id)
    worker_id = str(answer_manifest.get("worker_id") or "")
    model = str(answer_manifest.get("ollama_model") or ask_manifest.get("ollama_model") or "")
    status = str(answer_manifest.get("status") or "").upper()
    expected_output = str(ask_manifest.get("expected_output") or answer_manifest.get("expected_output") or "")

    if row is None or not is_current_attempt(row, ask_manifest, answer_manifest):
        print(f"Discarding late/obsolete answer: {answer_folder.name}")
        append_stats(proxy_root, {
            "event": "late_discard",
            "job_id": job_id,
            "attempt_id": attempt_id,
            "worker_id": worker_id,
            "model": model,
        })
        if not dry_run:
            move_to_unique(answer_folder, dirs["discarded"])
        return 1

    if status != "SUCCESS":
        print(f"Worker reported failure for {row.job}; returning job to READY_FOR_AI")
        append_stats(proxy_root, {
            "event": "worker_error",
            "job_id": job_id,
            "attempt_id": attempt_id,
            "worker_id": worker_id,
            "model": model,
            "error_message": str(answer_manifest.get("error_message") or ""),
        })
        if not dry_run:
            row.values["Status"] = "READY_FOR_AI"
            row.values["Next Actor"] = "OLLAMA"
            clear_ollama_attempt(row)
            move_to_unique(answer_folder, dirs["failed"])
        return 1

    if not expected_output:
        print(f"Answer missing expected_output; discarding: {answer_folder.name}")
        append_stats(proxy_root, {"event": "bad_answer", "job_id": job_id, "attempt_id": attempt_id})
        if not dry_run:
            move_to_unique(answer_folder, dirs["discarded"])
        return 1

    output_src = answer_folder / expected_output
    if not output_src.exists():
        matches = list(answer_folder.glob(f"*/{expected_output}"))
        output_src = matches[0] if matches else output_src
    if not output_src.exists():
        print(f"Answer output missing ({expected_output}); returning job to READY_FOR_AI")
        append_stats(proxy_root, {
            "event": "missing_output",
            "job_id": job_id,
            "attempt_id": attempt_id,
            "worker_id": worker_id,
            "model": model,
        })
        if not dry_run:
            row.values["Status"] = "READY_FOR_AI"
            row.values["Next Actor"] = "OLLAMA"
            clear_ollama_attempt(row)
            move_to_unique(answer_folder, dirs["failed"])
        return 1

    elapsed = answer_manifest.get("elapsed_seconds", "")
    print(f"Harvesting answer for {row.job}: {expected_output}")
    if not dry_run:
        dest = row.folder / expected_output
        dest.parent.mkdir(parents=True, exist_ok=True)
        manifest = read_json_file(row.folder / "dependency_manifest.json")
        if expected_output.lower().endswith(".md"):
            spec_path = row.folder / "Character_Specification.md"
            spec_text = spec_path.read_text(encoding="utf-8", errors="replace") if spec_path.exists() else ""
            response_text = output_src.read_text(encoding="utf-8", errors="replace")
            repaired_text = repair_ollama_output_for_stage(response_text, spec_text, manifest, row.task, expected_output)
            dest.write_text(repaired_text, encoding="utf-8")
        else:
            shutil.copy2(output_src, dest)

        # Keep manifests in the job folder for current attempt debugging, but no heavy logs.
        (row.folder / "ollama_answer_manifest.json").write_text(
            json.dumps(answer_manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (row.folder / "ollama_ask_manifest.json").write_text(
            json.dumps(ask_manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        try:
            advance_job_after_output(row, expected_output, manifest)
        except Exception as exc:
            # Advance_Job.py may reject bad model output, especially malformed
            # Final_Image_Prompt.md files. Do not crash Stage_Ollama_Jobs.py;
            # park this job in ERROR for review and move the answer to Failed.
            print(f"ERROR advancing {row.job} after {expected_output}: {exc}", file=sys.stderr)
            set_error_fields(row, "Stage_Ollama_Jobs.py/Advance_Job.py", exc)
            clear_ollama_attempt(row)
            append_stats(proxy_root, {
                "event": "advance_error",
                "job_id": job_id,
                "attempt_id": attempt_id,
                "worker_id": worker_id,
                "model": model,
                "expected_output": expected_output,
                "error_message": str(exc),
            })
            move_to_unique(answer_folder, dirs["failed"])
            return 1

        clear_ollama_attempt(row)
        append_stats(proxy_root, {
            "event": "success",
            "job_id": job_id,
            "attempt_id": attempt_id,
            "worker_id": worker_id,
            "model": model,
            "elapsed_seconds": elapsed,
            "expected_output": expected_output,
        })
        shutil.rmtree(answer_folder, ignore_errors=True)
    return 1


def harvest_answers(rows: list[JobRow], job_list_path: Path, proxy_root: Path, dry_run: bool = False) -> int:
    dirs = ensure_proxy_dirs(proxy_root)
    harvested = 0

    for answer_folder in sorted(dirs["answer"].iterdir() if dirs["answer"].exists() else []):
        try:
            harvested += harvest_one_answer_folder(
                answer_folder,
                rows,
                job_list_path,
                proxy_root,
                dirs,
                dry_run=dry_run,
            )
        except Exception as exc:
            # A single corrupt/incomplete answer folder should not stop harvest,
            # stale-reset, or staging for the rest of the queue.
            print(f"ERROR harvesting answer folder {answer_folder.name}: {exc}", file=sys.stderr)
            append_stats(proxy_root, {
                "event": "harvest_error",
                "answer_folder": answer_folder.name,
                "error_message": str(exc),
            })
            if not dry_run:
                try:
                    move_to_unique(answer_folder, dirs["failed"])
                except Exception as move_exc:
                    print(f"ERROR moving bad answer folder {answer_folder.name} to Failed: {move_exc}", file=sys.stderr)
            continue

    return harvested


def active_proxy_records(proxy_root: Path) -> dict[str, dict[str, str]]:
    """
    Return one active Ask/Claimed record per job_id.

    Active means work that should prevent staging a new Ask:
    - Ask/<ask_folder>
    - Claimed/<worker>/<ask_folder>
    - Claims/<ask_folder>.claim.json when the matching Ask folder still exists

    Answer folders are intentionally not treated as active because harvest_answers()
    consumes them before staging decisions.
    """
    dirs = ensure_proxy_dirs(proxy_root)
    records: dict[str, dict[str, str]] = {}

    def folder_mtime_iso(folder: Path) -> str:
        try:
            return datetime.fromtimestamp(folder.stat().st_mtime).isoformat(timespec="seconds")
        except Exception:
            return ""

    def remember(folder: Path, state: str, worker_id: str = "") -> None:
        manifest = read_json_file(manifest_path_in(folder, "ask_manifest.json"))
        job_id = str(manifest.get("job_id") or "")
        attempt_id = str(manifest.get("ollama_attempt_id") or "")
        ask_folder = str(manifest.get("ask_folder") or folder.name)
        if not job_id or not attempt_id:
            return

        claim_manifest = read_json_file(folder / "claim_manifest.json")
        claim_file = dirs.get("claims", proxy_root / "Claims") / f"{ask_folder}.claim.json"
        sidecar_claim = read_json_file(claim_file) if claim_file.exists() else {}

        claimed_at = str(
            claim_manifest.get("claimed_at")
            or sidecar_claim.get("claimed_at")
            or manifest.get("created_at")
            or folder_mtime_iso(folder)
            or ""
        )

        existing = records.get(job_id)
        priority = {"CLAIMED": 3, "ASK": 2, "CLAIM": 1}
        if existing and priority.get(existing.get("state", ""), 0) >= priority.get(state, 0):
            return

        records[job_id] = {
            "job_id": job_id,
            "attempt_id": attempt_id,
            "ask_folder": ask_folder,
            "state": state,
            "worker_id": worker_id,
            "path": str(folder),
            "claimed_at": claimed_at,
            "claim_file": str(claim_file),
        }

    ask_root = dirs["ask"]
    if ask_root.exists():
        for folder in sorted(ask_root.iterdir()):
            if folder.is_dir() and folder.name.startswith("Ask_"):
                remember(folder, "ASK")

    claimed_root = dirs["claimed"]
    if claimed_root.exists():
        for folder in sorted(claimed_root.rglob("Ask_*")):
            if folder.is_dir() and (folder / "ask_manifest.json").exists():
                worker_id = ""
                try:
                    rel = folder.relative_to(claimed_root)
                    if len(rel.parts) >= 2:
                        worker_id = rel.parts[0]
                except Exception:
                    pass
                remember(folder, "CLAIMED", worker_id=worker_id)

    claims_root = dirs["claims"]
    if claims_root.exists() and ask_root.exists():
        for claim_file in sorted(claims_root.glob("Ask_*.claim.json")):
            claim = read_json_file(claim_file)
            ask_name = str(claim.get("ask_folder") or claim_file.name.replace(".claim.json", ""))
            ask_folder = ask_root / ask_name
            if ask_folder.exists():
                remember(ask_folder, "CLAIM", worker_id=str(claim.get("worker_id") or ""))

    return records


def unclaim_stale_claimed_record(record: dict[str, str], proxy_root: Path, dry_run: bool = False) -> bool:
    """
    Move a stale Claimed/<worker>/Ask_* folder back to Ask/ so another worker can
    claim the same attempt. Remove the sidecar claim so the returned Ask is visible.
    """
    if record.get("state") != "CLAIMED":
        return False

    dirs = ensure_proxy_dirs(proxy_root)
    claimed_path = Path(record.get("path", ""))
    ask_name = record.get("ask_folder", claimed_path.name)
    ask_dest = dirs["ask"] / ask_name

    if not claimed_path.exists() or not claimed_path.is_dir():
        return False

    print(f"Unclaiming stale claimed folder: {claimed_path} -> {ask_dest}")
    if dry_run:
        return True

    claim_file_value = record.get("claim_file", "")
    if claim_file_value:
        try:
            Path(claim_file_value).unlink(missing_ok=True)
        except Exception:
            pass
    try:
        (claimed_path / "claim_manifest.json").unlink(missing_ok=True)
    except Exception:
        pass

    if ask_dest.exists():
        move_to_unique(claimed_path, dirs["failed"])
        return True

    ask_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(claimed_path), str(ask_dest))
    return True



def reconcile_active_proxy_rows(rows: list[JobRow], proxy_root: Path, dry_run: bool = False) -> int:
    """
    If a job row says READY_FOR_AI but there is already an active Ask/Claimed folder
    for that job, restore the row to WAITING instead of staging a duplicate Ask.
    """
    active = active_proxy_records(proxy_root)
    changed = 0
    for row in rows:
        record = active.get(row.job)
        if not record:
            continue
        current_attempt = str(row.values.get("Ollama Attempt ID", "") or "")
        if row.status.upper() == OLLAMA_PROXY_STATUS and current_attempt == record["attempt_id"]:
            continue
        if row.status.upper() == "READY_FOR_AI" and row.next_actor.upper() in OLLAMA_PROXY_ACTORS:
            print(f"Reconciled active proxy work for {row.job}: {record['state']} {record['ask_folder']}")
            if not dry_run:
                row.values["Status"] = OLLAMA_PROXY_STATUS
                row.values["Next Actor"] = "OLLAMA_PROXY"
                row.values["Next Action"] = f"Waiting for Ollama file-proxy answer: {record['ask_folder']}"
                row.values["Ollama Attempt ID"] = record["attempt_id"]
                row.values["Ollama Ask Folder"] = record["ask_folder"]
                if not row.values.get("Ollama Assigned At", "").strip():
                    row.values["Ollama Assigned At"] = now_iso()
                clear_error_fields(row)
            changed += 1
    return changed



def reset_stale_waiting(rows: list[JobRow], proxy_root: Path, stale_minutes: int, dry_run: bool = False) -> int:
    reset_count = 0
    now = datetime.now()
    active = active_proxy_records(proxy_root)

    for row in rows:
        if row.status.upper() != OLLAMA_PROXY_STATUS:
            continue

        record = active.get(row.job)
        if record:
            assigned_at = parse_iso_datetime(row.values.get("Ollama Assigned At", ""))
            claimed_at = parse_iso_datetime(record.get("claimed_at", ""))
            age_base = claimed_at or assigned_at
            age_minutes = (now - age_base).total_seconds() / 60.0 if age_base else stale_minutes + 1

            if record.get("state") == "CLAIMED" and age_minutes > stale_minutes:
                old_attempt = row.values.get("Ollama Attempt ID", "")
                print(f"Unclaiming stale Ollama claim for {row.job}: age {age_minutes:.1f} minutes")
                append_stats(proxy_root, {
                    "event": "stale_claim_unclaimed",
                    "job_id": row.job,
                    "attempt_id": old_attempt,
                    "model": row.values.get("Ollama Model", ""),
                    "age_minutes": round(age_minutes, 2),
                    "ask_folder": record.get("ask_folder", ""),
                    "worker_id": record.get("worker_id", ""),
                })
                if not dry_run:
                    unclaim_stale_claimed_record(record, proxy_root, dry_run=False)
                    row.values["Status"] = OLLAMA_PROXY_STATUS
                    row.values["Next Actor"] = "OLLAMA_PROXY"
                    row.values["Next Action"] = f"Waiting for Ollama file-proxy answer: {record['ask_folder']}"
                    row.values["Ollama Attempt ID"] = record["attempt_id"]
                    row.values["Ollama Ask Folder"] = record["ask_folder"]
                    row.values["Ollama Assigned At"] = now_iso()
                    clear_error_fields(row)
                reset_count += 1
                continue

            if str(row.values.get("Ollama Attempt ID", "") or "") != record["attempt_id"]:
                print(f"Updating stale attempt metadata for active {row.job}: {record['ask_folder']}")
                if not dry_run:
                    row.values["Ollama Attempt ID"] = record["attempt_id"]
                    row.values["Ollama Ask Folder"] = record["ask_folder"]
                    row.values["Next Action"] = f"Waiting for Ollama file-proxy answer: {record['ask_folder']}"
                    row.values["Next Actor"] = "OLLAMA_PROXY"
                    clear_error_fields(row)
                reset_count += 1
            continue

        assigned_at = parse_iso_datetime(row.values.get("Ollama Assigned At", ""))
        if assigned_at is None:
            age_minutes = stale_minutes + 1
        else:
            age_minutes = (now - assigned_at).total_seconds() / 60.0
        if age_minutes <= stale_minutes:
            continue

        old_attempt = row.values.get("Ollama Attempt ID", "")
        print(f"Resetting stale Ollama ask for {row.job}: age {age_minutes:.1f} minutes; no active Ask/Claimed folder found")
        append_stats(proxy_root, {
            "event": "stale_reset",
            "job_id": row.job,
            "attempt_id": old_attempt,
            "model": row.values.get("Ollama Model", ""),
            "age_minutes": round(age_minutes, 2),
        })
        if not dry_run:
            row.values["Status"] = "READY_FOR_AI"
            row.values["Next Actor"] = "OLLAMA"
            clear_ollama_attempt(row)
        reset_count += 1
    return reset_count


def default_stage_action_for_job(job: JobRow, output_name: str) -> str:
    """Return a sane action when a row was reset from WAITING but kept stale waiting text."""
    task = job.task
    lower = output_name.lower()

    if lower == "render_packet.md":
        if task == "head-fitment":
            return (
                "Create Render_Packet.md from Character_Specification.md for the specified "
                "head-fitment image-edit task and view. Use only active head-fitment modules. "
                "Preserve face, hair, ear, Modest Technical Fitment Shell body-fitment context, "
                "view, source-image, and avoid constraints. Do not create the final image prompt. "
                "Copy the Protected Job Metadata block exactly into Render_Packet.md and treat it as authoritative."
            )
        if task == "body-reference":
            return (
                "Create Render_Packet.md from Character_Specification.md for the specified "
                "body-reference task and view. Create a Modest Technical Fitment Shell body-reference packet. "
                "Preserve body proportions, fitment shell requirements, view, and avoid constraints. "
                "Do not create the final image prompt. Copy the Protected Job Metadata block exactly into Render_Packet.md and treat it as authoritative."
            )
        if task == "character-assembly":
            return (
                "Create Render_Packet.md from Character_Specification.md for the specified "
                "character-assembly task and view. Preserve body-reference image, head-fitment image, "
                "head/body alignment, identity, Modest Technical Fitment Shell context, view, scale, and avoid constraints. "
                "Do not create the final image prompt. Copy the Protected Job Metadata block exactly into Render_Packet.md and treat it as authoritative."
            )
        if task == "costume-fitment":
            return (
                "Create Render_Packet.md from Character_Specification.md for the specified "
                "costume-fitment task and view. Preserve body proportions, costume construction, equipment placement, "
                "view, and avoid constraints. Do not create the final image prompt. Copy the Protected Job Metadata block exactly into Render_Packet.md and treat it as authoritative."
            )
        return (
            "Create Render_Packet.md from Character_Specification.md for the specified task and view. "
            "Preserve protected metadata and constraints. Do not create the final image prompt."
        )

    if lower == "final_image_prompt.md":
        if task == "head-fitment":
            return (
                "Create Final_Image_Prompt.md from Render_Packet.md and Character_Specification.md for the specified "
                "head-fitment image-edit task. Preserve face, hair, ears, Modest Technical Fitment Shell body-fitment context, "
                "source-image, protected view metadata, prompt overlays, and avoid constraints. Do not render yet."
            )
        if task == "body-reference":
            return (
                "Create Final_Image_Prompt.md from Render_Packet.md and Character_Specification.md for the specified "
                "body-reference task. Create a Modest Technical Fitment Shell body reference. Preserve body, fitment shell, "
                "protected view metadata, and avoid constraints. Do not render yet."
            )
        if task == "character-assembly":
            return (
                "Create Final_Image_Prompt.md from Render_Packet.md and Character_Specification.md for the specified "
                "character-assembly task. Preserve body source, head-fitment source, Modest Technical Fitment Shell, "
                "protected view metadata, scale, alignment, and avoid constraints. Do not render yet."
            )
        if task == "costume-fitment":
            return (
                "Create Final_Image_Prompt.md from Render_Packet.md and Character_Specification.md for the specified "
                "costume-fitment task. Preserve body proportions, costume construction, equipment placement, protected view metadata, "
                "and avoid constraints. Do not render yet."
            )
        return (
            "Create Final_Image_Prompt.md from Render_Packet.md and Character_Specification.md. "
            "Preserve protected metadata and constraints. Do not render yet."
        )

    return job.next_action or f"Create {output_name} for {job.job}."


def normalize_stageable_row_before_ask(job: JobRow, output_name: str) -> None:
    """
    Repair READY_FOR_AI rows left behind by stale resets or validation failures.

    In those cases the job may be READY_FOR_AI/OLLAMA but still have:
    - Next Action: "Waiting for Ollama file-proxy answer..."
    - Error State: ERROR

    If it is being staged again, make the prompt instruction sane and clear the
    stale error/attempt fields.
    """
    if job.next_action.lower().startswith("waiting for ollama file-proxy answer"):
        job.values["Next Action"] = default_stage_action_for_job(job, output_name)
    if is_error_paused(job):
        clear_error_fields(job)
    clear_ollama_attempt(job)


def stage_job_as_ask(job: JobRow, proxy_root: Path, args: argparse.Namespace) -> None:
    output_name = job.expected_output or args.default_output
    if output_name.lower() in {"human review", "none", "n/a"}:
        print(f"Skipping {job.job}: Expected Output is not a file: {output_name}")
        return

    active = active_proxy_records(proxy_root).get(job.job)
    if active:
        print(f"Skipping {job.job}: active proxy work already exists: {active['state']} {active['ask_folder']}")
        job.values["Status"] = OLLAMA_PROXY_STATUS
        job.values["Next Actor"] = "OLLAMA_PROXY"
        job.values["Next Action"] = f"Waiting for Ollama file-proxy answer: {active['ask_folder']}"
        job.values["Ollama Attempt ID"] = active["attempt_id"]
        job.values["Ollama Ask Folder"] = active["ask_folder"]
        if not job.values.get("Ollama Assigned At", "").strip():
            job.values["Ollama Assigned At"] = now_iso()
        clear_error_fields(job)
        return

    normalize_stageable_row_before_ask(job, output_name)
    spec_text, manifest = load_job_inputs(job)
    module_rules = build_module_rules(job.task)
    selected_model = ollama_model_for_job(manifest, job.task, output_name, args.model)
    prompt = build_prompt(job, spec_text, manifest, output_name, module_rules)

    prompt_filename = ollama_prompt_filename(output_name)
    prompt_path = job.folder / prompt_filename
    prompt_path.write_text(prompt, encoding="utf-8")

    attempt_id = new_attempt_id()
    ask_folder_name = f"Ask_{sanitize_name(job.job)}__{attempt_id}"
    dirs = ensure_proxy_dirs(proxy_root)
    ask_dest = dirs["ask"] / ask_folder_name
    if ask_dest.exists():
        raise FileExistsError(f"Ask folder already exists: {ask_dest}")

    shutil.copytree(job.folder, ask_dest, ignore=shutil.ignore_patterns(".DS_Store", "__pycache__"))
    ask_manifest = {
        "version": 1,
        "ask_folder": ask_folder_name,
        "job_id": job.job,
        "ollama_attempt_id": attempt_id,
        "job_folder": str(job.folder),
        "job_list_path": str(args.job_list_path),
        "asset_id": job.values.get("Asset ID", ""),
        "character": job.values.get("Character", ""),
        "phase": job.values.get("Phase", ""),
        "task": job.task,
        "body_view": job.values.get("Body View", ""),
        "head_view": job.values.get("Head View", ""),
        "expected_output": output_name,
        "final_expected_image": job.final_expected_image,
        "ollama_prompt_file": prompt_filename,
        "ollama_model": selected_model,
        "temperature": args.temperature,
        "num_ctx": args.num_ctx,
        "created_at": now_iso(),
    }
    (ask_dest / "ask_manifest.json").write_text(json.dumps(ask_manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (job.folder / "ollama_ask_manifest.json").write_text(json.dumps(ask_manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    job.values["Status"] = OLLAMA_PROXY_STATUS
    job.values["Next Actor"] = "OLLAMA_PROXY"
    job.values["Next Action"] = f"Waiting for Ollama file-proxy answer: {ask_folder_name}"
    job.values["Ollama Attempt ID"] = attempt_id
    job.values["Ollama Ask Folder"] = ask_folder_name
    job.values["Ollama Assigned At"] = now_iso()
    job.values["Ollama Model"] = selected_model
    clear_error_fields(job)
    append_stats(proxy_root, {"event": "staged", "job_id": job.job, "attempt_id": attempt_id, "model": selected_model, "expected_output": output_name})
    print(f"Staged {job.job} -> {ask_dest}")


def select_stageable_jobs(rows: Iterable[JobRow], status: str, only_job: str | None) -> list[JobRow]:
    selected = []
    for row in rows:
        if only_job and row.job != only_job:
            continue
        if row.status.strip().upper() != status.upper():
            continue
        if row.next_actor.strip().upper() not in OLLAMA_PROXY_ACTORS:
            continue

        # Status is the gate. If a row is explicitly READY_FOR_AI and assigned to
        # OLLAMA/OLLAMA_PROXY, it should be stageable even if a previous validation
        # left Error State = ERROR. The staging step clears stale error fields.
        selected.append(row)
    return selected


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage and harvest filesystem-backed Ollama proxy jobs. This script never calls Ollama directly.")
    parser.add_argument("--queue-dir", default="Queue", help="Path to Queue folder. Default: ./Queue")
    parser.add_argument("--job-list", default=None, help="Path to Job_List.json. Default: <queue-dir>/Job_List.json")
    parser.add_argument("--proxy-root", default=None, help="Ollama file proxy root. Default: <queue-dir>/Ollama_File_Proxy")
    parser.add_argument("--model", default=None, help="Override Ollama model name for newly staged asks.")
    parser.add_argument("--status", default="READY_FOR_AI", help="Status to stage. Default: READY_FOR_AI")
    parser.add_argument("--only-job", default=None, help="Stage/harvest/reset only one job id where applicable.")
    parser.add_argument("--max-jobs", type=int, default=None, help="Maximum new asks to stage after harvest/reset. 0 or omitted means unlimited.")
    parser.add_argument("--temperature", type=float, default=0.1, help="Temperature recorded for workers. Default: 0.1")
    parser.add_argument("--num-ctx", type=int, default=None, help="Optional Ollama context window recorded for workers.")
    parser.add_argument("--stale-minutes", type=int, default=DEFAULT_STALE_MINUTES, help="Minutes before stale Claimed work is returned to Ask, or WAITING work with no active proxy folder is restaged. Active non-stale proxy work is not duplicated. Default: 360")
    parser.add_argument("--dry-run", action="store_true", help="Show harvest/reset/stage actions but do not change files.")
    parser.add_argument("--default-output", default="Render_Packet.md", help="Used if job row has no Expected Output. Default: Render_Packet.md")
    args = parser.parse_args(argv)

    queue_dir = Path(args.queue_dir).expanduser().resolve()
    job_list_path = Path(args.job_list).expanduser().resolve() if args.job_list else queue_dir / "Job_List.json"
    proxy_root = Path(args.proxy_root).expanduser().resolve() if args.proxy_root else queue_dir / DEFAULT_PROXY_ROOT
    args.job_list_path = job_list_path

    try:
        rows = read_job_list(job_list_path)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"Using job list: {job_list_path}")
    print(f"Using Ollama proxy root: {proxy_root}")
    ensure_proxy_dirs(proxy_root)

    # Always harvest, reconcile active proxy folders, reset only truly missing stale
    # attempts, then stage new work. Reconciliation prevents duplicate Ask folders.
    harvested = harvest_answers(rows, job_list_path, proxy_root, dry_run=args.dry_run)
    reconciled = reconcile_active_proxy_rows(rows, proxy_root, dry_run=args.dry_run)
    reset_count = reset_stale_waiting(rows, proxy_root, args.stale_minutes, dry_run=args.dry_run)
    compiled_count = compile_ready_body_reference_jobs(rows, args.only_job, dry_run=args.dry_run)

    selected = select_stageable_jobs(rows, args.status, args.only_job)

    # --max-jobs semantics:
    #   omitted / None = unlimited
    #   0 or negative   = unlimited
    #   positive N      = stage at most N new asks
    if args.max_jobs is not None and args.max_jobs > 0:
        selected = selected[: args.max_jobs]

    print(f"Harvested answers: {harvested}")
    print(f"Reconciled active proxy rows: {reconciled}")
    print(f"Reset stale asks: {reset_count}")
    print(f"Compiled body-reference jobs: {compiled_count}")
    print(f"Stageable jobs: {len(selected)}")

    for job in selected:
        try:
            if args.dry_run:
                print(f"DRY RUN: would stage {job.job} -> {job.expected_output or args.default_output}")
            else:
                stage_job_as_ask(job, proxy_root, args)
        except Exception as exc:
            print(f"ERROR staging {job.job}: {exc}", file=sys.stderr)
            if not args.dry_run:
                set_error_fields(job, "Stage_Ollama_Jobs.py", exc)
            continue

    if not args.dry_run:
        write_job_list(job_list_path, rows)
        print(f"Updated {job_list_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
