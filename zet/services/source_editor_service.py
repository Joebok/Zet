from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any


class SourceEditorService:
    def __init__(self, zet_app: Any, project_root: str | Path):
        self.zet_app = zet_app
        self.project_root = Path(project_root).resolve()

    def _editor_tools(self):
        scripts_path = self.project_root / "Scripts"
        if str(scripts_path) not in sys.path:
            sys.path.insert(0, str(scripts_path))
        from Compile_Character_Template import MARKER_RE
        from Template_Section_Editor import save_template_sections

        return MARKER_RE, save_template_sections

    def resolve_path(self, path: str) -> Path:
        requested = self.zet_app.path_service.resolve_path(path)
        if not requested.is_absolute():
            requested = self.project_root / requested
        resolved = requested.resolve()
        library_root = Path(self.zet_app.config.base_library_path).resolve()
        try:
            if not resolved.is_relative_to(library_root):
                resolved.relative_to(self.project_root)
        except ValueError as exc:
            raise ValueError("Source path must be inside the Zet project or configured library.") from exc
        if not resolved.is_file():
            raise FileNotFoundError(f"Source file not found: {path}")
        return resolved

    @staticmethod
    def _pointer_parts(pointer: str) -> list[str]:
        raw = str(pointer or "").strip()
        if not raw.startswith("/"):
            raise ValueError("JSON pointer must start with '/'.")
        return [part.replace("~1", "/").replace("~0", "~") for part in raw.split("/")[1:]]

    def _get_pointer(self, data: Any, pointer: str) -> Any:
        item = data
        for part in self._pointer_parts(pointer):
            item = item[int(part)] if isinstance(item, list) else item[part]
        return item

    def _set_pointer(self, data: Any, pointer: str, value: Any) -> None:
        parts = self._pointer_parts(pointer)
        if not parts:
            raise ValueError("Cannot replace the whole JSON document here.")
        item = data
        for part in parts[:-1]:
            item = item[int(part)] if isinstance(item, list) else item[part]
        last = parts[-1]
        if isinstance(item, list):
            item[int(last)] = value
        elif isinstance(item, dict):
            item[last] = value
        else:
            raise ValueError("JSON pointer does not reference an editable field.")

    def _extract_section(self, path: Path, section_name: str) -> tuple[str, int | None, int | None]:
        marker_re, _ = self._editor_tools()
        text = path.read_text(encoding="utf-8")
        open_name = None
        content_start = 0
        start_line = None
        for marker in marker_re.finditer(text):
            kind, name = marker.group(1), marker.group(2)
            if kind == "BEGIN":
                open_name = name
                content_start = marker.end()
                start_line = text.count("\n", 0, content_start) + 1
                continue
            if open_name == section_name and kind == "END" and name == section_name:
                end_line = text.count("\n", 0, marker.start()) + 1
                return text[content_start:marker.start()].strip("\n"), start_line, end_line
            open_name = None
        raise FileNotFoundError(f"Section not found: {section_name}")

    def load(self, source: dict[str, Any]) -> dict[str, Any]:
        kind = str(source.get("source_kind") or "")
        path = self.resolve_path(str(source.get("source_path") or ""))
        section = str(source.get("section_name") or "")
        pointer = str(source.get("json_pointer") or "")
        warning = "Shared template edits can affect multiple characters and phases." if kind == "shared_template_section" else ""
        if section:
            text, start_line, end_line = self._extract_section(path, section)
            editor_type = "markdown_section"
        elif pointer:
            data = json.loads(path.read_text(encoding="utf-8"))
            text = self._get_pointer(data, pointer)
            if isinstance(text, (list, dict)):
                text = json.dumps(text, indent=2, ensure_ascii=False)
            editor_type = "json_field"
            start_line = end_line = None
        else:
            text = path.read_text(encoding="utf-8")
            editor_type = "markdown_file"
            start_line = end_line = None
        return {
            "source": source,
            "editor_type": editor_type,
            "path": str(path),
            "section_name": section or None,
            "json_pointer": pointer or None,
            "text": str(text),
            "start_line": start_line,
            "end_line": end_line,
            "warning": warning,
        }

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        path = self.resolve_path(str(payload.get("path") or ""))
        editor_type = str(payload.get("editor_type") or "")
        text = str(payload.get("text") or "")
        if editor_type == "markdown_section":
            section = str(payload.get("section_name") or "")
            if not section:
                raise ValueError("Missing section name.")
            _, save_template_sections = self._editor_tools()
            save_template_sections(path, {section: text}, [section])
        elif editor_type == "json_field":
            pointer = str(payload.get("json_pointer") or "")
            data = json.loads(path.read_text(encoding="utf-8"))
            current = self._get_pointer(data, pointer)
            value: Any = text
            if isinstance(current, list):
                value = [line.strip() for line in text.splitlines() if line.strip()]
            elif isinstance(current, (int, float, bool, dict)):
                value = json.loads(text)
            self._set_pointer(data, pointer, value)
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        elif editor_type == "markdown_file":
            path.write_text(text, encoding="utf-8")
        else:
            raise ValueError(f"Unsupported editor type: {editor_type}")
        result = {"status": "SAVED", "path": str(path), "editor_type": editor_type}
        self._record(payload, result)
        return result

    def _record(self, payload: dict[str, Any], result: dict[str, Any]) -> None:
        log_dir = self.project_root / "Logs"
        log_dir.mkdir(exist_ok=True)
        entry = {
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "path": result.get("path"),
            "editor_type": result.get("editor_type"),
            "section_name": payload.get("section_name"),
            "json_pointer": payload.get("json_pointer"),
            "text_length": len(str(payload.get("text") or "")),
        }
        with (log_dir / "Source_Edits.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
