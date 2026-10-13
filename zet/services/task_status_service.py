"""Cached GitHub attention and worker health; browser reads never start agents."""
import threading
import time


class TaskStatusService:
    def __init__(self, task_service, usage, trusted_users=("Joebok",)):
        self.task = task_service
        self.usage = usage
        self.trusted_users = trusted_users
        self.stop_event = threading.Event()
        self.thread = None

    def refresh(self):
        self.task.store.put("settings", self.task.repository, {"reserve_percent": self.usage.reserve,
                            "trusted_users": list(self.trusted_users)})
        previous = self.task.store.get("status", "github", {})
        try:
            issues = self.task.github.issues()
            pulls = self.task.github.pulls()
            items = []
            for issue in issues:
                names = {label["name"] for label in issue.get("labels", [])}
                if "needs-input" in names or "needs-review" in names:
                    items.append({"id": f"issue-{issue['number']}", "kind": "question" if "needs-input" in names else "review",
                                  "title": issue["title"], "url": issue["html_url"], "number": issue["number"]})
            for pr in pulls:
                if not pr.get("draft") and not any(item["url"] == pr["html_url"] for item in items):
                    items.append({"id": f"pr-{pr['number']}", "kind": "review", "title": pr["title"], "url": pr["html_url"]})
            status = {"checked_at": time.time(), "items": items, "error": None,
                      "issue_count": len(issues), "main_revision": self.task.github.repo_api("/commits/main")["sha"]}
        except Exception as exc:
            status = dict(previous, error=str(exc)[:300], attempted_at=time.time())
        self.task.store.put("status", "github", status)
        quota = self.task.store.get("status", "usage", {})
        if time.time() - quota.get("checked_at", 0) > 300:
            self.usage.refresh()

    def snapshot(self):
        if not self.task.repository:
            return {"configured": False, "items": [], "usage": None, "worker": None}
        status = self.task.store.get("status", "github", {})
        worker = self.task.store.get("status", "worker", {})
        claim = self.task.store.get("worker", self.task.repository)
        items = list(status.get("items", []))
        if status.get("error"):
            items.append({"id": "github-error", "kind": "failure", "title": status["error"]})
        if time.time() - status.get("checked_at", 0) > 180:
            items.append({"id": "github-stale", "kind": "unavailable", "title": "GitHub status is stale or still loading."})
        if time.time() - worker.get("checked_at", 0) > 4200:
            items.append({"id": "worker-stale", "kind": "unavailable", "title": "Worker unavailable or not yet scheduled. Issues remain queued."})
        if claim and claim.get("state") == "in-progress" and time.time() - claim.get("updated_at", 0) > 3600:
            items.append({"id": "claim-stale", "kind": "failure", "title": f"Issue #{claim['issue_number']} retains an interrupted claim; inspect before recovery."})
        if worker.get("error"):
            items.append({"id": "worker-error", "kind": "failure", "title": worker["error"]})
        usage = self.task.store.get("status", "usage", {})
        if not usage.get("known") or time.time() - usage.get("checked_at", 0) > 600:
            items.append({"id": "usage-unknown", "kind": "usage", "title": "Usage limits unknown; new work waits for a fresh reading."})
        elif not usage.get("allowed"):
            items.append({"id": "usage-wait", "kind": "usage", "title": "Codex capacity is below the configured reserve; work is retained."})
        return {"configured": True, "items": items, "worker": worker, "usage": usage,
                "checked_at": status.get("checked_at"), "main_revision": status.get("main_revision"), "issue_count": status.get("issue_count")}

    def start(self):
        if not self.task.repository or self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        def run():
            while not self.stop_event.is_set():
                try:
                    self.refresh()
                except Exception:
                    pass  # Snapshot freshness exposes inability to refresh.
                self.stop_event.wait(60)
        self.thread = threading.Thread(target=run, name="zet-github-status", daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
