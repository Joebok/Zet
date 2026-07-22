import json
from pathlib import Path
from collections.abc import Iterator

from zet.models.ai_proxy import AIProxyAnswerManifest, AIProxyAskManifest, AIProxyPaths
from zet.services.config_service import Config


class AIProxyPathService:
    def __init__(self, config: Config):
        self.config = config

    def proxy_root(self) -> Path:
        return Path(self.config.base_ai_queue_path) / "Ollama_Proxy"

    @staticmethod
    def normalize_proxy_root(path: Path) -> Path:
        if path.name == "Ollama_Proxy":
            return path
        if path.name == "AI_Queue" or (path / "Ollama_Proxy").exists():
            return path / "Ollama_Proxy"
        return path

    @classmethod
    def worker_paths(cls, proxy_root: Path, worker_id: str) -> dict[str, Path]:
        root = cls.normalize_proxy_root(proxy_root)
        return {
            "ask": root / "Ask",
            "claims": root / "Claims",
            "claimed": root / "Claimed" / worker_id,
            "answer": root / "Answer",
            "failed": root / "Failed" / worker_id,
            "control": root / "Control",
            "monitor_requests": root / "Monitor" / "Requests",
            "monitor_responses": root / "Monitor" / "Responses" / worker_id,
        }

    def ask_root(self) -> Path:
        return self.proxy_root() / "Ask"

    def claims_root(self) -> Path:
        return self.proxy_root() / "Claims"

    def claimed_root(self) -> Path:
        return self.proxy_root() / "Claimed"

    def answer_root(self) -> Path:
        return self.proxy_root() / "Answer"

    def failed_root(self) -> Path:
        return self.proxy_root() / "Failed"

    def archive_root(self) -> Path:
        """Return the AI proxy archive root."""
        return self.proxy_root() / "Archive"

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

    def task_paths(self, *states: str) -> Iterator[Path]:
        """Yield task folders for queue states, flattening worker-owned states."""
        roots = {
            "ask": (self.ask_root(), False),
            "answer": (self.answer_root(), False),
            "claimed": (self.claimed_root(), True),
            "failed": (self.failed_root(), True),
        }
        for state in states:
            if state not in roots:
                raise ValueError(f"Unknown AI proxy queue state: {state}")
            root, worker_owned = roots[state]
            if not root.exists():
                continue
            parents = sorted(path for path in root.iterdir() if path.is_dir()) if worker_owned else (root,)
            for parent in parents:
                yield from sorted(path for path in parent.iterdir() if path.is_dir())

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
