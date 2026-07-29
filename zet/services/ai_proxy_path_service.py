import json
from pathlib import Path
from collections.abc import Iterator

from zet.models.ai_proxy import AIProxyAnswerManifest, AIProxyAskManifest, AIProxyPaths
from zet.services.config_service import Config
from zet.services.file_proxy_client import FileProxyClient


class AIProxyPathService:
    def __init__(self, config: Config):
        self.config = config
        self.file_proxy_client = FileProxyClient(config.base_ai_queue_path)

    def proxy_root(self) -> Path:
        return self.file_proxy_client.root

    @staticmethod
    def normalize_proxy_root(path: Path) -> Path:
        if path.name == "File_Proxy":
            return path
        if path.name == "AI_Queue" or (path / "File_Proxy").exists():
            return path / "File_Proxy"
        return path

    @classmethod
    def worker_paths(cls, proxy_root: Path, worker_id: str) -> dict[str, Path]:
        root = cls.normalize_proxy_root(proxy_root)
        return {
            "ask": root / "Ask" / "zet",
            "claimed": root / "Running" / "zet",
            "answer": root / "Answer" / "zet",
            "control": root / "Control",
        }

    def ask_root(self) -> Path:
        return self.file_proxy_client.ask_root

    def manual_root(self) -> Path:
        return Path(self.config.base_ai_queue_path) / "Manual_Render_Queue"

    def manual_ask_root(self) -> Path:
        return self.manual_root() / "Ask"

    def manual_answer_root(self) -> Path:
        return self.manual_root() / "Answer"

    def claims_root(self) -> Path:
        return self.proxy_root() / "Control"

    def claimed_root(self) -> Path:
        return self.file_proxy_client.running_root

    def answer_root(self) -> Path:
        return self.file_proxy_client.answer_root

    def failed_root(self) -> Path:
        return self.file_proxy_client.answer_root

    def archive_root(self) -> Path:
        """Return the AI proxy archive root."""
        return Path(self.config.base_ai_queue_path) / "Zet_File_Proxy_State" / "Archive"

    def harvested_archive_root(self) -> Path:
        """Return the harvested-answer archive root."""
        return self.archive_root() / "Harvested"

    def control_root(self) -> Path:
        return self.proxy_root() / "Control"

    def stop_manifest_path(self) -> Path:
        return self.control_root() / "stop.json"

    def monitor_root(self) -> Path:
        return self.proxy_root() / "Monitor"

    def monitor_requests_root(self) -> Path:
        return self.monitor_root() / "Requests"

    def monitor_responses_root(self) -> Path:
        return self.monitor_root() / "Responses"

    def monitor_request_path(self, test_id: str) -> Path:
        return self.monitor_requests_root() / test_id

    def monitor_response_path(self, worker_id: str, test_id: str) -> Path:
        return self.monitor_responses_root() / worker_id / f"{test_id}.json"

    def ask_path(self, ask_id: str) -> Path:
        return self.ask_root() / ask_id

    def manual_ask_path(self, ask_id: str) -> Path:
        return self.manual_ask_root() / ask_id

    def task_paths(self, *states: str) -> Iterator[Path]:
        """Yield Zet task folders from the new proxy and manual workflow."""
        roots = {
            "ask": (self.ask_root(), self.manual_ask_root()),
            "answer": (self.answer_root(), self.manual_answer_root()),
            "claimed": (self.claimed_root(),),
            "failed": (self.answer_root(),),
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

    def all_paths(self) -> AIProxyPaths:
        return AIProxyPaths(
            proxy_root=self.proxy_root(),
            ask_root=self.ask_root(),
            claims_root=self.claims_root(),
            claimed_root=self.claimed_root(),
            answer_root=self.answer_root(),
            failed_root=self.failed_root(),
            archive_root=self.archive_root(),
            control_root=self.control_root(),
            monitor_root=self.monitor_root(),
            monitor_requests_root=self.monitor_requests_root(),
            monitor_responses_root=self.monitor_responses_root(),
        )
