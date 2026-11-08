from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.access import policy as access
from app.access.deps import CurrentUser, require
from app.config import get_settings
from app.agents import followup
from app.connectors import oauth
from app.connectors.email.base import EmailProvider
from app.connectors.ingestion import ingest_email
from app.core.entities import Company
from app.core.i18n import tx
from app.core.tenancy import current_company
from app.core.tenant_scope import scope_session
from app.database import get_db

router = APIRouter(prefix="/oauth", tags=["oauth"])
public_router = APIRouter(prefix="/oauth", tags=["oauth"])  # the provider's redirect arrives without our session


class _Fetched(EmailProvider):
    def __init__(self, messages): self._m = messages
    def list_messages(self): return self._m
    def get_message(self, external_id): return next((m for m in self._m if m.external_id == external_id), None)
    def search_messages(self, query): return [m for m in self._m if query.lower() in (m.subject + m.body).lower()]
    def send_message(self, **kwargs): raise NotImplementedError("Read-only connection: nothing is ever sent from here.")


def sync(db: Session, company: Company, provider: str) -> dict:
    messages = oauth.fetch(db, company.id, provider)
    result = ingest_email(db, _Fetched(messages), company.id, source=f"oauth_{provider}")
    oauth.mark_synced(db, company.id, provider)
    return {"fetched": result.fetched, "created": result.created, "skipped": result.skipped}


@router.get("/status")
def status(db: Session = Depends(get_db), company: Company = Depends(current_company)) -> list[dict]:
    return oauth.status(db, company.id)


@router.get("/{provider}/start")
def start(provider: str, request: Request, db: Session = Depends(get_db), company: Company = Depends(current_company), _u: CurrentUser = Depends(require(access.WRITE_SETTINGS))) -> dict:
    if provider not in oauth.PROVIDERS:
        raise HTTPException(status_code=404, detail="unknown provider")
    try:
        url = oauth.start_url(provider, company.id, str(request.base_url))
        followup.track(db, company.id, f"oauth:{provider}", f"Connexion de la messagerie ({oauth.PROVIDERS[provider]['tool']})", "in_progress", kind="connection", agent="guide", href="/?service=mail")
        return {"url": url}
    except oauth.OAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{provider}/sync")
def sync_now(provider: str, db: Session = Depends(get_db), company: Company = Depends(current_company), _u: CurrentUser = Depends(require(access.WRITE_SETTINGS))) -> dict:
    if provider not in oauth.PROVIDERS:
        raise HTTPException(status_code=404, detail="unknown provider")
    try:
        return sync(db, company, provider)
    except oauth.OAuthError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.delete("/{provider}", status_code=204)
def disconnect(provider: str, db: Session = Depends(get_db), company: Company = Depends(current_company), _u: CurrentUser = Depends(require(access.WRITE_SETTINGS))) -> None:
    if provider not in oauth.PROVIDERS:
        raise HTTPException(status_code=404, detail=tx("Fournisseur inconnu.", "Unknown provider."))
    oauth.disconnect(db, company.id, provider)


@public_router.get("/{provider}/callback")
def callback(provider: str, request: Request, code: str | None = None, state: str | None = None, error: str | None = None, db: Session = Depends(get_db)) -> RedirectResponse:
    front = get_settings().frontend_url.rstrip("/")

    def back(**params: str) -> RedirectResponse:
        return RedirectResponse(f"{front}/?{urlencode(params)}", status_code=302)

    if provider not in oauth.PROVIDERS:
        return back(oauth_error="Fournisseur inconnu.")
    if error or not code or not state:
        return back(oauth_error="Autorisation refusée ou annulée.")
    try:
        company_id = oauth.read_state(state, provider)
        scope_session(db, company_id)
        company = db.query(Company).first()
        oauth.finish(db, company_id, provider, code, str(request.base_url))
        followup.track(db, company_id, f"oauth:{provider}", f"Connexion de la messagerie ({oauth.PROVIDERS[provider]['tool']})", "done", kind="connection", agent="guide")
        try:
            sync(db, company, provider)
        except oauth.OAuthError:
            db.rollback()
        return back(connected=oauth.PROVIDERS[provider]["tool"])
    except oauth.OAuthError as exc:
        return back(oauth_error=str(exc)[:200])
