from pathlib import Path

from zet.models.ai_proxy import AIProxyPaths
from zet.services.config_service import Config


class AIProxyPathService:
    def __init__(self, config: Config):
        self.config = config

    def proxy_root(self) -> Path:
        return Path(self.config.base_ai_queue_path) / "Ollama_Proxy"

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

    def all_paths(self) -> AIProxyPaths:
        return AIProxyPaths(
            proxy_root=self.proxy_root(),
            ask_root=self.ask_root(),
            claims_root=self.claims_root(),
            claimed_root=self.claimed_root(),
            answer_root=self.answer_root(),
            failed_root=self.failed_root(),
            control_root=self.control_root(),
            monitor_root=self.monitor_root(),
            monitor_requests_root=self.monitor_requests_root(),
            monitor_responses_root=self.monitor_responses_root(),
        )
