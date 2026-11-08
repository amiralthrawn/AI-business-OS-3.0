"""The AI browser: a browser the AI drives for the company while the person
watches, and can take over (login, 2FA, captcha) and hand back.

Each task runs in its own thread with its own browser (a cloud browser in
production, a local Chromium in development). State lives in memory: a task
is short-lived (minutes) and a restart simply ends it. What the person types
while in control goes straight to the page: it is never sent to a model and
never written in the log.
"""

import base64
import json
import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

from app.agents import perplexity, veilleur_agent
from app.config import get_settings

VIEW = {"width": 1280, "height": 800}
MAX_STEPS = 30
MAX_SECONDS = 600
MAX_DOWNLOAD = 25 * 1024 * 1024
BB = "https://api.browserbase.com/v1"


@dataclass
class Task:
    id: str
    company_id: uuid.UUID
    goal: str
    status: str = "starting"  # starting | running | human | needs_human | done | failed | cancelled
    steps: list[dict] = field(default_factory=list)
    shot: bytes | None = None
    live_url: str | None = None
    summary: str = ""
    reason: str = ""
    downloads: list[dict] = field(default_factory=list)  # {name, content}
    inbox: "queue.Queue[dict]" = field(default_factory=queue.Queue)
    started: float = field(default_factory=time.time)
    provider: str = ""

    def log(self, text: str) -> None:
        self.steps.append({"at": datetime.now(timezone.utc).isoformat(), "text": text[:300]})

    def public(self) -> dict:
        return {
            "id": self.id, "goal": self.goal, "status": self.status, "steps": self.steps[-40:], "summary": self.summary, "reason": self.reason,
            "live_url": self.live_url, "provider": self.provider, "has_shot": self.shot is not None, "view": VIEW,
            "downloads": [{"index": i, "name": d["name"], "size": len(d["content"])} for i, d in enumerate(self.downloads)],
        }


TASKS: dict[str, Task] = {}
_LOCK = threading.Lock()
ACTIVE = ("starting", "running", "human", "needs_human")


def provider() -> str | None:
    s = get_settings()
    if (s.browserbase_api_key or "").strip() and (s.browserbase_project_id or "").strip():
        return "cloud"
    if s.browser_local:
        return "local"
    return None


def available() -> bool:
    return provider() is not None and veilleur_agent.enabled()


def start(company_id: uuid.UUID, goal: str, start_url: str | None = None) -> Task:
    with _LOCK:
        for t in TASKS.values():
            if t.company_id == company_id and t.status in ACTIVE:
                raise RuntimeError("Une tâche de navigateur est déjà en cours : terminez-la ou arrêtez-la d'abord.")
        task = Task(id=uuid.uuid4().hex[:12], company_id=company_id, goal=goal.strip()[:1500], provider=provider() or "")
        TASKS[task.id] = task
        for old in [k for k, v in TASKS.items() if v.status not in ACTIVE and time.time() - v.started > 3600]:
            TASKS.pop(old, None)
    threading.Thread(target=_run, args=(task, start_url), daemon=True).start()
    return task


def get(company_id: uuid.UUID, task_id: str) -> Task | None:
    task = TASKS.get(task_id)
    return task if task and task.company_id == company_id else None


# --- the browser ---------------------------------------------------------------------

def _open_cloud(task: Task):
    s = get_settings()
    headers = {"x-bb-api-key": s.browserbase_api_key.strip(), "Content-Type": "application/json"}
    body = {"projectId": s.browserbase_project_id.strip(), "browserSettings": {"viewport": VIEW}, "timeout": MAX_SECONDS + 120}
    res = httpx.post(f"{BB}/sessions", headers=headers, json=body, timeout=30)
    if res.status_code >= 300:
        raise RuntimeError(f"Navigateur cloud indisponible ({res.status_code}) : {res.text[:200]}")
    data = res.json()
    try:
        live = httpx.get(f"{BB}/sessions/{data['id']}/debug", headers=headers, timeout=15).json()
        task.live_url = live.get("debuggerFullscreenUrl")
    except (httpx.HTTPError, ValueError, KeyError):
        task.live_url = None

    def release() -> None:
        try:
            httpx.post(f"{BB}/sessions/{data['id']}", headers=headers, json={"projectId": body["projectId"], "status": "REQUEST_RELEASE"}, timeout=15)
        except httpx.HTTPError:
            pass

    return data["connectUrl"], release


def _decide(task: Task, shot: bytes, page_text: str | None) -> dict:
    """One step of the model: looks at the screen, picks one tool."""

    recent = "\n".join(f"- {s['text']}" for s in task.steps[-8:]) or "(rien encore)"
    content = [
        {"type": "text", "text": f"Objectif : {task.goal}\n\nActions déjà faites :\n{recent}\n" + (f"\nTexte de la page :\n{page_text}\n" if page_text else "") + "\nVoici l'écran. Choisis la prochaine action."},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(shot).decode()}},
    ]
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": content}]
    message = veilleur_agent._chat(messages, TOOLS, required=True)
    calls = message.get("tool_calls") or []
    if not calls:
        return {"name": "wait", "args": {"seconds": 1}}
    try:
        args = json.loads(calls[0]["function"].get("arguments") or "{}")
    except ValueError:
        args = {}
    return {"name": calls[0]["function"]["name"], "args": args}


def _apply_human(page, cmd: dict) -> None:
    kind = cmd.get("type")
    if kind == "click":
        page.mouse.click(max(0, min(VIEW["width"], float(cmd["x"]))), max(0, min(VIEW["height"], float(cmd["y"]))))
    elif kind == "type":
        page.keyboard.type(str(cmd.get("text", ""))[:500])  # never logged: may be a password
    elif kind == "key":
        page.keyboard.press(str(cmd.get("key", "Enter"))[:30])
    elif kind == "scroll":
        page.mouse.wheel(0, 600 if cmd.get("direction") != "up" else -600)


def _run(task: Task, start_url: str | None) -> None:
    from playwright.sync_api import sync_playwright

    release = None
    try:
        with sync_playwright() as pw:
            if provider() == "cloud":
                cdp, release = _open_cloud(task)
                browser = pw.chromium.connect_over_cdp(cdp)
                ctx = browser.contexts[0] if browser.contexts else browser.new_context()
            else:
                s = get_settings()
                browser = pw.chromium.launch(headless=True, executable_path=s.browser_local_executable or None, args=["--no-sandbox"])
                ctx = browser.new_context(viewport=VIEW, accept_downloads=True, locale="fr-FR")
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.set_viewport_size(VIEW)

            def on_download(download) -> None:
                try:
                    path = download.path()
                    content = open(path, "rb").read(MAX_DOWNLOAD + 1) if path else b""
                except Exception:
                    return
                if content and len(content) <= MAX_DOWNLOAD:
                    task.downloads.append({"name": download.suggested_filename or "fichier", "content": content})
                    task.log(f"Fichier reçu : {download.suggested_filename} ({len(content)} octets)")

            page.on("download", on_download)
            if start_url:
                _goto(page, task, start_url)
            task.status = "running"
            task.log("Navigateur ouvert : l'IA commence.")
            while task.status in ACTIVE and time.time() - task.started < MAX_SECONDS and len([s for s in task.steps]) < MAX_STEPS * 3:
                while not task.inbox.empty():
                    try:
                        _apply_human(page, task.inbox.get_nowait())
                    except Exception:
                        pass
                try:
                    task.shot = page.screenshot(type="jpeg", quality=60)
                except Exception:
                    time.sleep(0.5)
                    continue
                if task.status in ("human", "needs_human"):
                    time.sleep(0.4)
                    continue
                decision = _decide(task, task.shot, None)
                if task.status != "running":
                    continue
                if _act(page, task, decision):
                    break
                time.sleep(0.6)
            if task.status in ACTIVE:
                task.status, task.summary = "failed", task.summary or "Temps ou nombre d'étapes dépassé sans terminer."
            browser.close()
    except Exception as exc:  # the thread must always end in a visible state
        task.status = "failed"
        task.summary = f"Le navigateur s'est arrêté : {str(exc)[:200]}"
    finally:
        if release:
            release()
        _book(task)


def _goto(page, task: Task, url: str) -> bool:
    from urllib.parse import urlparse

    parsed = urlparse(url if "://" in url else f"https://{url}")
    if parsed.scheme not in ("http", "https") or not parsed.hostname or (provider() != "local" and not veilleur_agent._public_host(parsed.hostname)):
        task.log(f"Adresse refusée : {url[:80]}")
        return False
    try:
        page.goto(parsed.geturl(), wait_until="domcontentloaded", timeout=25000)
        task.log(f"Ouvre {parsed.hostname}")
        return True
    except Exception as exc:
        task.log(f"Page non chargée ({str(exc)[:80]})")
        return False


def _act(page, task: Task, decision: dict) -> bool:
    """Runs one decided action. True when the task is over."""

    name, args = decision["name"], decision["args"]
    try:
        if name == "goto":
            _goto(page, task, str(args.get("url", "")))
        elif name == "click":
            page.mouse.click(float(args["x"]), float(args["y"]))
            task.log(f"Clique ({int(args['x'])}, {int(args['y'])}){' : ' + str(args['why'])[:80] if args.get('why') else ''}")
        elif name == "type":
            page.keyboard.type(str(args.get("text", ""))[:500])
            if args.get("enter"):
                page.keyboard.press("Enter")
            task.log(f"Saisit « {str(args.get('text', ''))[:60]} »")
        elif name == "press":
            page.keyboard.press(str(args.get("key", "Enter"))[:30])
            task.log(f"Touche {args.get('key')}")
        elif name == "scroll":
            page.mouse.wheel(0, 600 if args.get("direction") != "up" else -600)
            task.log("Fait défiler la page")
        elif name == "wait":
            time.sleep(min(float(args.get("seconds", 1)), 10))
        elif name == "ask_human":
            task.status, task.reason = "needs_human", str(args.get("reason", "L'IA a besoin de vous."))[:300]
            task.log(f"L'IA vous demande la main : {task.reason}")
        elif name == "done":
            task.status = "done" if args.get("success", True) else "failed"
            task.summary = str(args.get("summary", ""))[:1500]
            task.log("Terminé." if task.status == "done" else "Échec.")
            return True
    except Exception as exc:
        task.log(f"Action impossible ({name}) : {str(exc)[:80]}")
    return False


def _book(task: Task) -> None:
    """Tokens and cost go on the Exécutant, the run is logged."""

    from app.agents import service
    from app.core.tenant_scope import scope_session
    from app.database import SessionLocal

    try:
        with SessionLocal() as db:
            scope_session(db, task.company_id)
            service.log_run(db, task.company_id, "executant", "ok" if task.status == "done" else "error", f"Navigateur : {task.goal[:140]} ({task.status})", len(task.downloads))
    except Exception:
        pass


# --- human control -------------------------------------------------------------------

def take_over(task: Task) -> None:
    if task.status == "running":
        task.status = "human"
        task.log("Vous avez pris la main.")


def hand_back(task: Task) -> None:
    if task.status in ("human", "needs_human"):
        task.status, task.reason = "running", ""
        task.log("Vous rendez la main à l'IA.")


def cancel(task: Task) -> None:
    if task.status in ACTIVE:
        task.status = "cancelled"
        task.log("Arrêté par vous.")


SYSTEM = (
    "Tu pilotes un navigateur web pour le compte d'une PME, sous les yeux de son dirigeant, afin d'accomplir un objectif précis (exporter un fichier, lire une information, configurer un accès). "
    "À chaque étape tu vois une capture de l'écran (1280x800) et tu choisis UNE action avec un outil. "
    "Règles : ne saisis JAMAIS de mot de passe, de code de sécurité ni de donnée de paiement : utilise ask_human pour que la personne se connecte ou valide elle-même, puis continue quand elle te rend la main. "
    "Utilise ask_human aussi pour un captcha ou une confirmation qui engage l'entreprise. N'achète rien, ne supprime rien, ne publie rien. Reste sur les sites utiles à l'objectif. "
    "Quand l'objectif est atteint (ou impossible), appelle done avec un résumé factuel de ce que tu as fait ou observé."
)
_P = lambda **props: {"type": "object", "properties": props}
TOOLS = [
    {"type": "function", "function": {"name": "goto", "description": "Ouvre une adresse.", "parameters": {**_P(url={"type": "string"}), "required": ["url"]}}},
    {"type": "function", "function": {"name": "click", "description": "Clique à la position (x, y) de la capture.", "parameters": {**_P(x={"type": "number"}, y={"type": "number"}, why={"type": "string"}), "required": ["x", "y"]}}},
    {"type": "function", "function": {"name": "type", "description": "Tape du texte dans le champ actif (jamais de mot de passe).", "parameters": {**_P(text={"type": "string"}, enter={"type": "boolean"}), "required": ["text"]}}},
    {"type": "function", "function": {"name": "press", "description": "Appuie sur une touche (Enter, Tab, Escape, PageDown…).", "parameters": {**_P(key={"type": "string"}), "required": ["key"]}}},
    {"type": "function", "function": {"name": "scroll", "description": "Fait défiler la page.", "parameters": {**_P(direction={"type": "string", "enum": ["up", "down"]})}}},
    {"type": "function", "function": {"name": "wait", "description": "Attend que la page charge.", "parameters": _P(seconds={"type": "number"})}},
    {"type": "function", "function": {"name": "ask_human", "description": "Demande à la personne de reprendre la main (connexion, code, captcha, validation).", "parameters": {**_P(reason={"type": "string"}), "required": ["reason"]}}},
    {"type": "function", "function": {"name": "done", "description": "Termine la tâche.", "parameters": {**_P(summary={"type": "string"}, success={"type": "boolean"}), "required": ["summary", "success"]}}},
]
