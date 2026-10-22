"""Compose repository-owned guidance once, before publishing a new text request."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from zet.services.atomic_file_service import write_json_atomic
from zet.services.llm_role_service import get_role, skill_modules, validate_provider


SKILL_ROOT = Path(__file__).resolve().parents[2] / "Config" / "LLM_Skills" / "qwen-image-2.1"


def compose_request(staging: Path, config=None, *, skill_root: Path | None = None) -> None:
    path = staging / "ai_request.json"
    request = json.loads(path.read_text(encoding="utf-8"))
    if request.get("provider") not in {"codex", "ollama"}:
        return
    # Frozen requests, including recovered attempts, never pick up changed guidance.
    if request.get("llm_guidance"):
        return
    ask_path = staging / "ask_manifest.json"
    ask = json.loads(ask_path.read_text(encoding="utf-8"))
    role = get_role(ask.get("llm_role"))
    validate_provider(role, request["model"])
    context = ask.get("llm_context", {})
    if not isinstance(context, dict):
        raise ValueError("LLM render context must be an object.")
    provenance = {"version": 1, "role": role.key, "application": role.skill,
                  "context": context, "modules": [], "hashes": {}}
    if role.skill != "off" and role.status != "retired":
        modules = skill_modules(role, context.get("operation"))
        root = skill_root or SKILL_ROOT
        try:
            manifest_bytes = (root / "manifest.json").read_bytes()
            manifest = json.loads(manifest_bytes)
            if not isinstance(manifest.get("integration_version"), int):
                raise ValueError("manifest.json needs an integer integration_version")
            contents = [(name, (root / name).read_bytes()) for name in modules]
        except (OSError, ValueError) as exc:
            raise ValueError(f"Cannot prepare {role.label}: repair the Qwen skill package at {root}: {exc}") from exc
        provenance.update(skill="qwen-image-2.1", integration_version=manifest["integration_version"], modules=modules,
                          manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
                          hashes={name: hashlib.sha256(data).hexdigest() for name, data in contents})
        guidance = "\n\n".join(f"--- {name} ---\n{data.decode('utf-8-sig')}" for name, data in contents)
        guidance += ("\n\nZet task routing (authoritative application contract):\n"
                     + json.dumps({"role": role.key, "application": role.skill,
                                   "prompt_fields": role.prompt_fields, **context}, ensure_ascii=False)
                     + "\nReturn the task's original response schema, not the source skill's example JSON. "
                       "Zet adapters override source presentation and routing rules only; the skill controls prompt writing.")
        request["system"] = request.get("system", "") + "\n\n" + guidance
        # Keep the actual effective instructions inventoried with the request.
        (staging / "llm_instructions.md").write_text(request["system"], encoding="utf-8")
    provenance["system_sha256"] = hashlib.sha256(request.get("system", "").encode()).hexdigest()
    provenance["prompt_sha256"] = hashlib.sha256(request["prompt"].encode()).hexdigest()
    request["llm_guidance"] = provenance
    ask["llm_guidance"] = provenance
    write_json_atomic(path, request)
    write_json_atomic(ask_path, ask)
