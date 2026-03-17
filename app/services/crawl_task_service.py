from copy import deepcopy
from datetime import datetime
from threading import Lock
from uuid import uuid4


class CrawlTaskService:
    def __init__(self):
        self._tasks = {}
        self._lock = Lock()

    def create_task(self, company_link_ids: list[int]) -> str:
        task_id = uuid4().hex
        with self._lock:
            self._tasks[task_id] = {
                "task_id": task_id,
                "status": "pending",
                "total": len(company_link_ids),
                "completed": 0,
                "success_count": 0,
                "failure_count": 0,
                "current_company_link_id": None,
                "current_company_name": None,
                "results": [],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
        return task_id

    def get_task(self, task_id: str):
        with self._lock:
            task = self._tasks.get(task_id)
            return deepcopy(task) if task else None

    def mark_running(self, task_id: str) -> None:
        self._update(task_id, status="running")

    def mark_company_started(self, task_id: str, company_link_id: int, company_name: str) -> None:
        self._update(
            task_id,
            current_company_link_id=company_link_id,
            current_company_name=company_name,
        )

    def update_live_steps(self, task_id: str, company_link_id: int, company_name: str, debug_steps: list[str]) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return
            existing = None
            for item in task["results"]:
                if item["company_link_id"] == company_link_id:
                    existing = item
                    break
            if existing is None:
                existing = {
                    "company_link_id": company_link_id,
                    "company_name": company_name,
                    "success": False,
                    "inserted": 0,
                    "updated": 0,
                    "message": "Running",
                    "debug_steps": [],
                    "page_text_preview": None,
                    "llm_raw_response": None,
                    "extracted_positions": [],
                    "status": "running",
                }
                task["results"].append(existing)
            existing["debug_steps"] = list(debug_steps)
            existing["status"] = "running"
            task["updated_at"] = datetime.now().isoformat()

    def append_result(self, task_id: str, result: dict) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return
            task["results"] = [
                item for item in task["results"] if item["company_link_id"] != result["company_link_id"]
            ]
            task["results"].append(result)
            task["completed"] += 1
            if result.get("success"):
                task["success_count"] += 1
            else:
                task["failure_count"] += 1
            task["updated_at"] = datetime.now().isoformat()

    def mark_finished(self, task_id: str) -> None:
        self._update(
            task_id,
            status="completed",
            current_company_link_id=None,
            current_company_name=None,
        )

    def mark_failed(self, task_id: str, message: str) -> None:
        self._update(
            task_id,
            status="failed",
            current_company_link_id=None,
            current_company_name=None,
            error_message=message,
        )

    def _update(self, task_id: str, **kwargs) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return
            task.update(kwargs)
            task["updated_at"] = datetime.now().isoformat()


crawl_task_service = CrawlTaskService()
