import hashlib
from typing import Any

import httpx

from app.core.config import Settings


class TaskApiClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def create_task(self, payload: dict[str, Any]) -> str:
        if not self.settings.task_api_base_url:
            return _stable_task_id(payload["source_email_id"], payload["thread_id"])

        response = self._client().post("/tasks", json=payload)
        response.raise_for_status()
        data = response.json()
        return data.get("id") or data.get("task_id")

    def update_task(self, task_id: str, payload: dict[str, Any]) -> str:
        if not self.settings.task_api_base_url:
            return task_id

        response = self._client().patch(f"/tasks/{task_id}", json=payload)
        response.raise_for_status()
        return task_id

    def find_existing_task(self, source_email_id: str, thread_id: str) -> str | None:
        if not self.settings.task_api_base_url:
            return None

        response = self._client().get("/tasks", params={"source_email_id": source_email_id, "thread_id": thread_id})
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list) and data:
            return data[0].get("id") or data[0].get("task_id")
        if isinstance(data, dict):
            items = data.get("items") or data.get("tasks") or []
            if items:
                return items[0].get("id") or items[0].get("task_id")
        return None

    def _client(self) -> httpx.Client:
        headers = {}
        if self.settings.task_api_token:
            headers["Authorization"] = f"Bearer {self.settings.task_api_token}"
        return httpx.Client(
            base_url=self.settings.task_api_base_url or "",
            headers=headers,
            timeout=self.settings.task_api_timeout_seconds,
        )


def _stable_task_id(source_email_id: str, thread_id: str) -> str:
    digest = hashlib.sha256(f"{thread_id}:{source_email_id}".encode()).hexdigest()[:12]
    return f"local-task-{digest}"

