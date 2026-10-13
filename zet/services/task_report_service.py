"""Validate explicit public captures and render the exact issue preview."""
import json
import re
from urllib.parse import urlsplit

from zet.services.github_client import TaskServiceError


REPORT_FIELDS = {"type", "title", "description", "expected_behavior", "actual_behavior", "reproduction_steps", "success_criteria"}
CONTEXT_FIELDS = {"version", "page_id", "page_name", "source_url", "universe_id", "selections", "captured_at", "zet_revision", "viewport", "selected_control", "workflow_status"}
COMPONENTS = {"narrative": "COMPONENTS/NARRATIVE.md", "scene-candidates": "COMPONENTS/NARRATIVE.md",
              "local-body-reference": "COMPONENTS/LOCAL_CHARACTERS.md", "local-head-image": "COMPONENTS/LOCAL_CHARACTERS.md",
              "local-character-assembly": "COMPONENTS/LOCAL_CHARACTERS.md", "local-costume-dressing": "COMPONENTS/LOCAL_CHARACTERS.md",
              "local-character-overview": "COMPONENTS/LOCAL_CHARACTERS.md", "gate-test-rig": "COMPONENTS/LOCAL_CHARACTERS.md",
              "gate-test-data": "COMPONENTS/LOCAL_CHARACTERS.md", "zine": "ARCHITECTURE.md"}


def validate_repository(value):
    if not isinstance(value, str) or (value and (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]+", value) or value.split("/")[1] in {".", ".."})):
        raise TaskServiceError("GitHub.Repository must be owner/name or empty.", 422)
    return value


def request_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
        raise TaskServiceError("A stable request_id containing letters, digits, underscores or hyphens is required.", 422)
    return value


def validate_report(payload, repository):
    allowed = REPORT_FIELDS | {"request_id", "repository", "start_codex", "context", "attachment_ids"}
    if not isinstance(payload, dict) or set(payload) - allowed:
        raise TaskServiceError("Expected supported GitHub report fields.", 422)
    request_id(payload.get("request_id"))
    if payload.get("repository", repository) != repository:
        raise TaskServiceError("The saved draft belongs to a different repository.", 409)
    if not isinstance(payload.get("type"), str) or payload["type"] not in {"bug", "improvement", "feature"}:
        raise TaskServiceError("Choose Bug, Improvement or Feature.", 422)
    report = dict(payload, repository=repository)
    for field in REPORT_FIELDS:
        value = report.get(field, "")
        if not isinstance(value, str) or len(value) > (240 if field == "title" else 20000):
            raise TaskServiceError(f"Invalid {field}.", 422)
        report[field] = value
    if not report["title"].strip() or type(report.get("start_codex", True)) is not bool:
        raise TaskServiceError("A title and boolean Start Codex work setting are required.", 422)
    report["start_codex"] = report.get("start_codex", True)
    context = report.get("context")
    if not isinstance(context, dict) or type(context.get("version")) is not int or context["version"] != 1 or set(context) - CONTEXT_FIELDS:
        raise TaskServiceError("A supported frozen context-v1 snapshot is required.", 422)
    for field in ("page_id", "page_name", "source_url", "captured_at"):
        if not isinstance(context.get(field), str) or not context[field] or len(context[field]) > 4096:
            raise TaskServiceError(f"Captured {field} is required.", 422)
    source = urlsplit(context["source_url"])
    if source.scheme not in {"http", "https"} or not source.hostname or source.username or source.password:
        raise TaskServiceError("Return to Zet must be an HTTP(S) URL without credentials.", 422)
    selections = context.get("selections", {})
    for name in ("selected_control", "workflow_status", "universe_id", "zet_revision"):
        if context.get(name) is not None and (not isinstance(context[name], str) or len(context[name]) > 1024):
            raise TaskServiceError(f"Captured {name} must be a bounded identifier or status.", 422)
    try:
        context_size = len(json.dumps(context, allow_nan=False))
    except (ValueError, TypeError) as exc:
        raise TaskServiceError("Captured context must contain finite JSON values.", 422) from exc
    if not isinstance(selections, dict) or context_size > 20000:
        raise TaskServiceError("Captured selections are invalid or too large.", 422)
    # Providers supply identifiers, labels and state; arbitrary record contents are rejected.
    for name, selection in selections.items():
        if not re.fullmatch(r"[a-z_]+", name) or not isinstance(selection, dict):
            raise TaskServiceError("Captured selections must be explicit identifiers.", 422)
        if set(selection) - {"state", "id", "label", "key"}:
            raise TaskServiceError("Captured selections contain unsupported record fields.", 422)
        if any(not isinstance(value, (str, int)) or isinstance(value, bool) or len(str(value)) > 1024 for value in selection.values()):
            raise TaskServiceError("Captured selections may contain only bounded identifiers, labels and states.", 422)
    attachments = report.get("attachment_ids", [])
    if not isinstance(attachments, list) or len(attachments) > 4 or any(not isinstance(x, str) or not re.fullmatch(r"attachment-[0-9a-f]{32}", x) for x in attachments) or len(set(attachments)) != len(attachments):
        raise TaskServiceError("Use up to four unique screenshot receipts.", 422)
    report["attachment_ids"] = attachments
    return report


def marker(report):
    return f"<!-- zet-capture:{report['request_id']} -->"


def format_report(report, evidence=()):
    context = report["context"]
    sections = [("Reported problem", report["description"]), ("Expected behavior", report["expected_behavior"]),
                ("Actual behavior", report["actual_behavior"]), ("Reproduction steps", report["reproduction_steps"]),
                ("Success criteria", report["success_criteria"] or "Unspecified — verify the original reported problem; do not silently narrow its intent.")]
    text = "\n\n".join(f"## {heading}\n\n{content}" for heading, content in sections if content)
    text += "\n\n## Captured context\n\n```json\n" + json.dumps(context, ensure_ascii=False, indent=2) + "\n```"
    text += f"\n\n[Return to Zet]({context['source_url']})"
    revision = context.get("zet_revision") or "main"
    if not re.fullmatch(r"[0-9a-f]{40}|main", revision):
        revision = "main"
    base = f"https://github.com/{report['repository']}/blob/{revision}/Docs/"
    docs = ["CODE_MAP.md", COMPONENTS.get(context["page_id"], "ARCHITECTURE.md")]
    text += "\n\n## Implementation navigation\n\n" + "\n".join(f"- [{path}]({base}{path})" for path in dict.fromkeys(docs))
    if evidence:
        text += "\n\n## Screenshots\n\n" + "\n\n".join(f"![Screenshot {index + 1}]({item['url']})\n\nSHA-256: `{item['sha256']}`" for index, item in enumerate(evidence))
    text += "\n\n## Authorization\n\n" + ("Approved for scoped Codex implementation and PR delivery. Joe owns merge and deployment." if report["start_codex"] else "Saved for later. Implementation requires codex-ready authorization.")
    return text + "\n\n" + marker(report)
