"""Frozen target intent shared by reconstruction hosts; no rendering or HTTP."""
from __future__ import annotations

import hashlib
import json
import re


CATEGORIES = ("drift", "requested_change_missing", "intentional_change_satisfied",
              "style_or_view_issue", "not_evaluable")
CORRECTABLE = {"drift", "requested_change_missing", "style_or_view_issue"}


def fingerprint(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def text(value, label: str, limit: int = 24000) -> str:
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError(f"{label} must be text of at most {limit} characters.")
    return value.strip()


def target_brief(payload: dict, style: dict, sources: list[dict]) -> dict:
    preserve = text(payload.get("preserve", "Preserve stable identity and visible design except the explicit changes."), "Preserve instructions")
    changes = text(payload.get("changes", ""), "Change instructions")
    decisions = []
    for index, line in enumerate(changes.splitlines()):
        if not line.strip():
            continue
        line = line.strip()
        match = re.match(r"(add|remove|replace|modify)\b\s*(.*)", line, re.I)
        decisions.append({"id": fingerprint([index, line])[:16],
                          "action": match[1].lower() if match else "modify",
                          "subject": match[2] if match else line, "result": line})
    return {"version": 2, "preserve": preserve, "changes": decisions,
            "change_text": changes, "notes": text(payload.get("notes", ""), "Notes"),
            "style_mode": "universe", "style": style, "sources": sources,
            "description": "", "identity": "", "proposals": [], "questions": [],
            "context": text(payload.get("context", ""), "Task context")}


def target_instructions(target: dict) -> str:
    return ("TARGET CONTRACT: explicit changes override conflicting source observations and generated anchors. "
            "Preserve all unaffected identity and design. Destination style controls rendering, not identity. "
            "Never restore a removed feature while correcting another. Source pose/background yield to task view. "
            "Do not resolve contradictory explicit instructions silently; ask a focused question.\n"
            + json.dumps(target, ensure_ascii=False))


def validate_draft(draft: dict) -> dict:
    for key in ("content_prompt", "identity"):
        if not text(draft.get(key), key):
            raise ValueError(f"The analysis returned empty {key}.")
    for key in ("observations", "proposals", "questions", "uncertainties"):
        values = draft.get(key)
        if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
            raise ValueError(f"The analysis returned invalid {key}.")
    return draft


def validate_report(reply: dict) -> dict:
    if not isinstance(reply.get("summary"), str) or not isinstance(reply.get("items"), list):
        raise ValueError("The comparison model returned an invalid report.")
    for item in reply["items"]:
        if not isinstance(item, dict) or item.get("category") not in CATEGORIES:
            raise ValueError("The comparison returned an invalid finding category.")
        for key in ("feature", "evidence", "expected", "observed", "correction"):
            text(item.get(key), key)
        if item.get("visibility") not in {"visible", "occluded", "uncertain"}:
            raise ValueError("The comparison returned invalid visibility.")
        if item.get("severity") not in {"minor", "major", "info"}:
            raise ValueError("The comparison returned invalid severity.")
        item["id"] = fingerprint(item)[:16]
        if item["category"] not in CORRECTABLE or item["visibility"] != "visible":
            item["correction"] = ""
    return reply


def correction_items(report, item_ids, instructions):
    if not isinstance(item_ids, list) or any(not isinstance(i, str) for i in item_ids):
        raise ValueError("Choose correction item IDs from the current comparison.")
    items = [item for item in report["items"] if item["id"] in item_ids]
    if len({item["id"] for item in items}) != len(set(item_ids)):
        raise ValueError("The selected comparison findings are no longer available.")
    if any(i["category"] not in CORRECTABLE or not i["correction"] for i in items):
        raise ValueError("Only visible discrepancies can be selected for correction.")
    if not items and not instructions.strip():
        raise ValueError("Choose a correction or enter refinement instructions.")
    return items
