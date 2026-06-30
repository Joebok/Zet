#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import json
import re


def load_checklist(project_root: Path, checklist_name: str) -> dict:
    path = project_root / "Config" / "Prompt_Review_Checklists.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    checklists = data.get("checklists", data)
    return dict(checklists.get(checklist_name, {}))


def review_prompt_text(prompt_text: str, checklist: dict) -> list[str]:
    findings: list[str] = []
    lower = prompt_text.lower()
    for phrase in checklist.get("required_phrases", []):
        if str(phrase).lower() in lower:
            findings.append(f"PASS required phrase present: {phrase}")
        else:
            findings.append(f"FAIL required phrase missing: {phrase}")
    for phrase in checklist.get("forbidden_phrases", []):
        if str(phrase).lower() in lower:
            findings.append(f"FAIL forbidden phrase present: {phrase}")
        else:
            findings.append(f"PASS forbidden phrase absent: {phrase}")
    if checklist.get("fail_on_unresolved_placeholders", False):
        findings.append("FAIL unresolved placeholders remain" if re.search(r"\{\{.*?\}\}", prompt_text) else "PASS no unresolved placeholders")
    if checklist.get("fail_on_zet_markers", False):
        findings.append("FAIL ZET markers remain" if "<!-- ZET:" in prompt_text else "PASS no ZET markers")
    return findings


def format_static_findings(findings: list[str]) -> str:
    return "\n".join(f"- {finding}" for finding in findings)

