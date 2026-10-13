"""Loopback client for sandboxed helpers; GitHub credentials never leave Zet."""
import json
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from urllib.parse import urlsplit

from zet.services.github_client import GitHubClient, TaskServiceError


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class WorkerBridgeClient(GitHubClient):
    def __init__(self, repository, store, registry):
        super().__init__(repository)
        self.store, self.registry = store, registry
        self.claim_token = None
        self.opener = build_opener(ProxyHandler({}), NoRedirect())
        address = urlsplit(registry["url"])
        if address.scheme != "http" or address.hostname != "127.0.0.1" or address.path or address.username or address.password:
            raise TaskServiceError("The worker bridge must be a plain loopback HTTP origin.", 403)

    @classmethod
    def discover(cls, repository, store):
        path = store.root / "worker-bridge.json"
        if not path.exists():
            return None
        registry = json.loads(path.read_text(encoding="utf-8"))
        return cls(repository, store, registry) if registry["repository"] == repository else None

    def request(self, action, payload=None):
        request = Request(self.registry["url"] + "/api/tasks/worker/" + action,
                          data=json.dumps(payload or {}).encode(), headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.registry["token"]})
        try:
            with self.opener.open(request, timeout=150) as response:
                return json.load(response)
        except HTTPError as exc:
            try:
                detail = json.load(exc).get("detail", "Worker bridge rejected the action.")
            except ValueError:
                detail = "Worker bridge rejected the action."
            raise TaskServiceError(str(detail), exc.code) from exc
        except (OSError, URLError) as exc:
            raise TaskServiceError("The local Zet worker bridge is unavailable. Start the configured Zet server; work is retained.") from exc

    def repo_api(self, suffix="", **kwargs):
        token = self.claim_token
        if not token and kwargs.get("method", "GET") != "GET":
            # The initial claim is committed before its first GitHub label transition.
            import sqlite3
            with sqlite3.connect(self.store.path) as db:
                row = db.execute("SELECT payload FROM records WHERE scope='worker' AND key=?", (self.repository,)).fetchone()
            token = json.loads(row[0])["token"] if row else None
        return self.request("github", {"path": suffix, "claim_token": token, **kwargs})
