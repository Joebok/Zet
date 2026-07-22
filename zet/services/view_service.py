import json
import re
from pathlib import Path


class UnknownViewError(ValueError):
    pass


class ViewService:
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)

    def load_view_options(self) -> dict:
        data = self._load_json("Prompt_View_Text.json")
        return data.get("views", data)

    def load_view_data(self, view_token: str) -> dict:
        views = self.load_view_options()
        view = views.get(view_token) if isinstance(views, dict) else None
        if not isinstance(view, dict):
            raise UnknownViewError(f"No view text configured for token: {view_token}")
        return {**view, "_view_token": view_token}

    def normalize_token(self, raw_view: str) -> str:
        value = str(raw_view or "").strip()
        aliases_data = self._load_json("Prompt_View_Aliases.json")
        aliases = aliases_data.get("aliases", aliases_data)
        normalized = re.sub(r"\s+", " ", value).strip().lower()
        candidates = [
            value,
            value.lower(),
            normalized,
            normalized.replace("_", "-"),
            normalized.replace(" ", "-"),
        ]
        for candidate in candidates:
            token = aliases.get(candidate) if isinstance(aliases, dict) else None
            if isinstance(token, str) and token.strip():
                return token.strip()
        raise UnknownViewError(f"Unknown view: {value}")

    def folder_name(self, raw_view: str) -> str:
        value = str(raw_view)
        views = self.load_view_options()
        for view in views.values():
            if not isinstance(view, dict):
                continue
            if raw_view in {view.get("folder_name"), view.get("output_name_fragment")}:
                return str(view.get("folder_name"))
        return self.fallback_folder_name(value)

    def folder_name_tolerant(self, raw_view: str) -> str:
        try:
            return self.folder_name(raw_view)
        except Exception:
            return self.fallback_folder_name(raw_view)

    @staticmethod
    def fallback_folder_name(raw_view: str) -> str:
        return str(raw_view).replace("-", "_")

    def _load_json(self, name: str) -> dict:
        path = self.project_root / "Config" / name
        return json.loads(path.read_text(encoding="utf-8"))
