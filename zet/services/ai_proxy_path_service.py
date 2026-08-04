import json
from pathlib import Path
from collections.abc import Iterator

from zet.models.ai_proxy import AIProxyAnswerManifest, AIProxyAskManifest
from zet.services.config_service import Config
from zet.services.file_proxy_client import FileProxyClient


class AIProxyPathService:
    def __init__(self, config: Config):
        self.config = config
        self.file_proxy_client = FileProxyClient(config.base_ai_queue_path)

    def ask_root(self) -> Path:
        return self.file_proxy_client.ask_root

    def manual_root(self) -> Path:
        return Path(self.config.base_ai_queue_path) / "Manual_Render_Queue"

    def manual_ask_root(self) -> Path:
        return self.manual_root() / "Ask"

    def manual_answer_root(self) -> Path:
        return self.manual_root() / "Answer"

    def running_root(self) -> Path:
        return self.file_proxy_client.running_root

    def answer_root(self) -> Path:
        return self.file_proxy_client.answer_root

    def archive_root(self) -> Path:
        """Return the AI proxy archive root."""
        return Path(self.config.base_ai_queue_path) / "Zet_File_Proxy_State" / "Archive"

    def harvested_archive_root(self) -> Path:
        """Return the harvested-answer archive root."""
        return self.archive_root() / "Harvested"

    def manual_ask_path(self, ask_id: str) -> Path:
        return self.manual_ask_root() / ask_id

    def task_paths(self, *states: str) -> Iterator[Path]:
        """Yield Zet task folders from the new proxy and manual workflow."""
        roots = {
            "ask": (self.ask_root(), self.manual_ask_root()),
            "answer": (self.answer_root(), self.manual_answer_root()),
            "running": (self.running_root(),),
        }
        for state in states:
            if state not in roots:
                raise ValueError(f"Unknown AI proxy queue state: {state}")
            for root in roots[state]:
                if not root.exists():
                    continue
                paths = sorted(
                    path for path in root.iterdir()
                    if path.is_dir() and not path.name.startswith(".")
                )
                if state == "answer" and root == self.answer_root():
                    paths = [
                        path
                        for path in paths
                        if self.file_proxy_client.answer_is_ready(path)
                    ]
                yield from paths

    @staticmethod
    def read_ask_manifest(task_path: Path) -> AIProxyAskManifest:
        manifest_path = task_path / "ask_manifest.json"
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid ask manifest at {manifest_path}: {exc}") from exc
        return AIProxyAskManifest.from_dict(payload)

    @staticmethod
    def read_answer_manifest(task_path: Path) -> AIProxyAnswerManifest:
        manifest_path = task_path / "answer_manifest.json"
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid answer manifest at {manifest_path}: {exc}") from exc
        return AIProxyAnswerManifest.from_dict(payload)
