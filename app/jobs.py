"""Minimal in-memory background job queue for long-running conversions."""

import logging
import shutil
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import settings
from .files import new_workdir

log = logging.getLogger("toolbox")

class JobError(Exception):
    """Error whose message is safe to show to the user."""


@dataclass
class Job:
    id: str
    kind: str
    workdir: Path
    status: str = "queued"  # queued | running | done | error
    progress: float = 0.0
    message: str = ""
    result: Path | None = None
    created: float = field(default_factory=time.time)

    def public(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "status": self.status,
            "progress": round(self.progress, 1),
            "message": self.message,
            "filename": self.result.name if self.result else None,
        }


_jobs: dict[str, Job] = {}
_lock = threading.Lock()
_pool = ThreadPoolExecutor(max_workers=settings.MAX_CONCURRENT_JOBS, thread_name_prefix="job")


def submit(kind: str, fn: Callable[[Job], Path], workdir: Path | None = None) -> Job:
    job = Job(id=uuid.uuid4().hex, kind=kind, workdir=workdir or new_workdir())
    with _lock:
        _jobs[job.id] = job

    def run() -> None:
        job.status = "running"
        try:
            job.result = fn(job)
            job.progress = 100.0
            job.status = "done"
        except JobError as e:
            job.status, job.message = "error", str(e)
        except Exception as e:  # noqa: BLE001 - surface unexpected failures to the client
            job.status, job.message = "error", f"Interner Fehler: {type(e).__name__}"
            log.exception("job %s failed", job.id)

    _pool.submit(run)
    return job


def get(job_id: str) -> Job | None:
    with _lock:
        return _jobs.get(job_id)


def _sweep() -> None:
    ttl = settings.JOB_TTL_MIN * 60
    while True:
        time.sleep(60)
        cutoff = time.time() - ttl
        with _lock:
            for jid in [j for j, job in _jobs.items() if job.created < cutoff and job.status in ("done", "error")]:
                shutil.rmtree(_jobs.pop(jid).workdir, ignore_errors=True)
            active = {job.workdir for job in _jobs.values()}
        # Also remove leftovers from synchronous requests that failed midway.
        for d in settings.WORK_DIR.iterdir():
            try:
                if d not in active and d.stat().st_mtime < cutoff:
                    shutil.rmtree(d, ignore_errors=True)
            except FileNotFoundError:
                pass


threading.Thread(target=_sweep, daemon=True, name="job-sweeper").start()
