from __future__ import annotations

import json
import logging
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _atomic_write(path: Path, data: Any) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")
    tmp.replace(path)


LOGGER = logging.getLogger(__name__)


class RoutineEngine:
    VALID_SCHEDULES = {"daily", "manual"}
    VALID_STEP_TYPES = {"watch", "agenda"}

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.routines_path = repo_root / "Runtime" / "routines" / "routines.json"
        self.routines_dir = repo_root / "Runtime" / "routines"
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._thread_lock = threading.Lock()
        self._running_routines: set[str] = set()
        self._running_lock = threading.Lock()

        self.routines_dir.mkdir(parents=True, exist_ok=True)
        if not self.routines_path.exists():
            self.routines_path.write_text("[]", encoding="utf-8")

    # ------------------------------------------------------------------
    # Scheduler
    # ------------------------------------------------------------------

    def start_background_thread(self) -> None:
        with self._thread_lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._scheduler_loop, daemon=True, name="RoutineScheduler")
            self._thread.start()

    def _scheduler_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                for routine in self.list_routines():
                    if routine.get("enabled", True) and self._is_due(routine):
                        routine_id = str(routine.get("id", ""))
                        with self._running_lock:
                            if routine_id in self._running_routines:
                                continue
                            self._running_routines.add(routine_id)
                        threading.Thread(
                            target=self._run_routine_safe,
                            args=(routine,),
                            daemon=True,
                            name=f"RoutineRun-{routine_id[:8]}",
                        ).start()
            except Exception:
                LOGGER.exception("Routine scheduler loop failed.")
            self._stop_event.wait(60)

    def _is_due(self, routine: dict) -> bool:
        schedule = str(routine.get("schedule", "manual")).strip().lower()
        if schedule == "manual":
            return False
        last_run_raw = str(routine.get("last_run_at", "")).strip()
        now = _now_utc()
        if not last_run_raw:
            if schedule == "daily":
                hour = int(routine.get("schedule_hour", 7))
                return now.hour >= hour
            return False

        try:
            last_run = datetime.fromisoformat(last_run_raw.replace("Z", "+00:00"))
        except ValueError:
            return True

        if schedule == "daily":
            hour = int(routine.get("schedule_hour", 7))
            today_run = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            return now >= today_run and last_run < today_run

        return False

    def _run_routine_safe(self, routine: dict) -> None:
        routine_id = str(routine.get("id", ""))
        try:
            self._run_routine(routine)
        except Exception:
            LOGGER.exception("Routine execution failed for %s.", routine_id)
        finally:
            with self._running_lock:
                self._running_routines.discard(routine_id)

    def _run_routine(self, routine: dict) -> None:
        routine_id = str(routine.get("id", ""))
        steps = [s for s in routine.get("steps", []) if isinstance(s, dict)]

        source = self.repo_root / "SourceCode"
        if str(source) not in sys.path:
            sys.path.insert(0, str(source))

        for step in steps:
            step_type = str(step.get("type", "")).strip().lower()
            try:
                if step_type == "watch":
                    self._exec_watch_step(step)
                elif step_type == "agenda":
                    self._exec_agenda_step(routine_id)
            except Exception:
                LOGGER.exception("Routine step failed for routine %s and step %s.", routine_id, step_type)

        self._update_last_run(routine_id)

    def _exec_watch_step(self, step: dict) -> None:
        from shared_tools.watchtower import WatchtowerEngine
        watch_id = str(step.get("watch_id", "")).strip()
        if not watch_id:
            return
        wt = WatchtowerEngine(self.repo_root)
        watches = wt.list_watches()
        target = next((w for w in watches if str(w.get("id", "")) == watch_id), None)
        if target:
            wt._run_watch(target)

    def _exec_agenda_step(self, routine_id: str) -> None:
        today = _now_utc().date().isoformat()

        content = (
            f"# Agenda — {today}\n\n"
            "Personal assistant lane is not available in this build.\n"
            "Use chat, project, research, and library workflows instead.\n"
        )
        out_path = self.routines_dir / f"{routine_id}_agenda.md"
        out_path.write_text(content, encoding="utf-8")

    def _update_last_run(self, routine_id: str) -> None:
        with self._lock:
            routines = self._load_routines()
            for r in routines:
                if str(r.get("id", "")) == routine_id:
                    r["last_run_at"] = _now_iso()
                    break
            self._save_routines(routines)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def _load_routines(self) -> list[dict]:
        try:
            data = json.loads(self.routines_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        return [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []

    def _save_routines(self, routines: list[dict]) -> None:
        _atomic_write(self.routines_path, routines)

    def list_routines(self) -> list[dict]:
        with self._lock:
            return self._load_routines()

    def add_routine(
        self,
        name: str,
        steps: list[dict],
        schedule: str = "manual",
        schedule_hour: int = 7,
    ) -> dict:
        name = name.strip()
        if not name:
            raise ValueError("Routine name cannot be empty.")
        schedule = schedule.strip().lower()
        if schedule not in self.VALID_SCHEDULES:
            schedule = "manual"
        schedule_hour = max(0, min(23, int(schedule_hour)))
        clean_steps = []
        for s in steps:
            if not isinstance(s, dict):
                continue
            t = str(s.get("type", "")).strip().lower()
            if t not in self.VALID_STEP_TYPES:
                continue
            step: dict[str, Any] = {"type": t}
            if t == "watch":
                step["watch_id"] = str(s.get("watch_id", "")).strip()
            clean_steps.append(step)

        routine: dict[str, Any] = {
            "id": f"routine_{uuid.uuid4().hex[:10]}",
            "name": name,
            "steps": clean_steps,
            "enabled": True,
            "schedule": schedule,
            "schedule_hour": schedule_hour,
            "last_run_at": "",
            "created_at": _now_iso(),
        }
        with self._lock:
            routines = self._load_routines()
            routines.append(routine)
            self._save_routines(routines)
        return routine

    def update_routine(self, routine_id: str, **fields: Any) -> dict | None:
        key = routine_id.strip()
        allowed = {"name", "steps", "schedule", "schedule_hour", "enabled"}
        with self._lock:
            routines = self._load_routines()
            hit: dict | None = None
            for r in routines:
                if str(r.get("id", "")) != key:
                    continue
                for field, value in fields.items():
                    if field not in allowed:
                        continue
                    if field == "name":
                        value = str(value).strip()
                    elif field == "schedule":
                        value = str(value).strip().lower()
                        if value not in self.VALID_SCHEDULES:
                            value = "manual"
                    elif field == "schedule_hour":
                        value = max(0, min(23, int(value)))
                    elif field == "enabled":
                        value = bool(value)
                    r[field] = value
                r["updated_at"] = _now_iso()
                hit = r
                break
            if hit is None:
                return None
            self._save_routines(routines)
        return hit

    def delete_routine(self, routine_id: str) -> bool:
        key = routine_id.strip()
        with self._lock:
            routines = self._load_routines()
            new_routines = [r for r in routines if str(r.get("id", "")) != key]
            if len(new_routines) == len(routines):
                return False
            self._save_routines(new_routines)
        return True

    def trigger_routine(self, routine_id: str) -> dict:
        routines = self.list_routines()
        target = next((r for r in routines if str(r.get("id", "")) == routine_id.strip()), None)
        if target is None:
            raise ValueError(f"Routine not found: {routine_id}")
        with self._running_lock:
            if routine_id in self._running_routines:
                return {**target, "status": "already_running"}
            self._running_routines.add(routine_id)
        threading.Thread(
            target=self._run_routine_safe,
            args=(target,),
            daemon=True,
            name=f"RoutineTrigger-{routine_id[:8]}",
        ).start()
        return {**target, "status": "triggered"}
