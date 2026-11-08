"""What each AI is doing right now, for the live progress shown in the app.

In memory and per company: a job is a long piece of work (the Analyste's
analysis, the Veilleur's watch, the check that follows an import) that runs on
the server, so it goes on whatever the person does in the app. The front end
polls this to show where it stands, and can ask to stop it.
"""

import threading
import time
import uuid

_LOCK = threading.Lock()
JOBS: dict[tuple[uuid.UUID, str], dict] = {}
KEEP_SECONDS = 600  # a finished job stays visible for a while, then goes


class Cancelled(Exception):
    pass


def start(company_id: uuid.UUID, agent: str, label: str) -> None:
    with _LOCK:
        JOBS[(company_id, agent)] = {"agent": agent, "label": label, "status": "running", "percent": 0, "steps": [], "started": time.time(), "updated": time.time(), "cancel": False}


def running(company_id: uuid.UUID, agent: str) -> bool:
    job = JOBS.get((company_id, agent))
    return bool(job and job["status"] == "running")


def step(company_id: uuid.UUID, agent: str, text: str, percent: int | None = None) -> None:
    """Report where the work is; raises Cancelled if the person asked to stop."""

    job = JOBS.get((company_id, agent))
    if job is None:
        return
    with _LOCK:
        job["label"] = text
        if percent is not None:
            job["percent"] = max(0, min(99, percent))
        if not job["steps"] or job["steps"][-1]["text"] != text:
            job["steps"].append({"at": time.time(), "text": text})
            job["steps"] = job["steps"][-30:]
        job["updated"] = time.time()
    if job["cancel"]:
        raise Cancelled()


def finish(company_id: uuid.UUID, agent: str, status: str = "done", text: str | None = None) -> None:
    job = JOBS.get((company_id, agent))
    if job is None:
        return
    with _LOCK:
        job.update(status=status, percent=100 if status == "done" else job["percent"], updated=time.time())
        if text:
            job["label"] = text
            job["steps"].append({"at": time.time(), "text": text})


def cancel(company_id: uuid.UUID, agent: str) -> bool:
    job = JOBS.get((company_id, agent))
    if job and job["status"] == "running":
        job["cancel"] = True
        return True
    return False


def snapshot(company_id: uuid.UUID) -> list[dict]:
    now = time.time()
    out = []
    for (cid, _agent), job in list(JOBS.items()):
        if cid != company_id:
            continue
        if job["status"] != "running" and now - job["updated"] > KEEP_SECONDS:
            JOBS.pop((cid, _agent), None)
            continue
        out.append({k: job[k] for k in ("agent", "label", "status", "percent")} | {"steps": [s["text"] for s in job["steps"][-6:]], "elapsed": int(now - job["started"]), "started": int(job["started"]), "cancelling": job["cancel"]})
    return out
