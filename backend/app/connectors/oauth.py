"""Real mailbox connections (Gmail, Outlook / Microsoft 365) by OAuth, read-only.

The person clicks "Authorize", signs in on the provider's own page and grants
read access; we only ever hold a refresh token, encrypted at rest. Messages are
fetched and normalised into the same `ExternalEmail` the rest of the product
already reads. Nothing is ever sent from here.
"""

import base64
import hashlib
import re
import uuid
from datetime import datetime, timedelta, timezone
from email.utils import getaddresses, parsedate_to_datetime
from urllib.parse import urlencode

import httpx
import jwt
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.business_context.service import BusinessContextService
from app.config import get_settings
from app.configuration import service as config_service
from app.connectors.models import ExternalEmail

PROVIDERS = {
    "google": {
        "tool": "gmail", "label": "Gmail / Google Workspace",
        "auth": "https://accounts.google.com/o/oauth2/v2/auth", "token": "https://oauth2.googleapis.com/token",
        "scope": "openid email https://www.googleapis.com/auth/gmail.readonly",
        "extra": {"access_type": "offline", "prompt": "consent"},
    },
    "microsoft": {
        "tool": "outlook", "label": "Outlook / Microsoft 365",
        "auth": "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize", "token": "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
        "scope": "offline_access User.Read Mail.Read",
        "extra": {"prompt": "select_account"},
    },
}
MAX_MESSAGES = 40


class OAuthError(RuntimeError):
    pass


def _creds(provider: str) -> tuple[str, str]:
    s = get_settings()
    if provider == "google":
        return (s.google_oauth_client_id or "").strip(), (s.google_oauth_client_secret or "").strip()
    return (s.microsoft_oauth_client_id or "").strip(), (s.microsoft_oauth_client_secret or "").strip()


def configured(provider: str) -> bool:
    return provider in PROVIDERS and all(_creds(provider))


def _urls(provider: str) -> dict:
    info = PROVIDERS[provider]
    tenant = get_settings().microsoft_oauth_tenant
    return {"auth": info["auth"].format(tenant=tenant), "token": info["token"].format(tenant=tenant)}


def redirect_uri(provider: str, fallback_base: str) -> str:
    base = (get_settings().api_public_url or fallback_base).rstrip("/")
    return f"{base}/oauth/{provider}/callback"


def _fernet() -> Fernet:
    secret = get_settings().auth_secret_key or "dev-only-key"
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()))


def _seal(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def _open(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise OAuthError("Connexion illisible : reconnectez la messagerie.") from exc


def _secret() -> str:
    return get_settings().auth_secret_key or "dev-only-key"


def start_url(provider: str, company_id: uuid.UUID, base: str) -> str:
    if not configured(provider):
        raise OAuthError("Cette connexion n'est pas encore activée sur ce serveur (identifiants OAuth à renseigner).")
    state = jwt.encode({"c": str(company_id), "p": provider, "exp": datetime.now(timezone.utc) + timedelta(minutes=15)}, _secret(), algorithm="HS256")
    client_id, _ = _creds(provider)
    params = {"client_id": client_id, "redirect_uri": redirect_uri(provider, base), "response_type": "code", "scope": PROVIDERS[provider]["scope"], "state": state, **PROVIDERS[provider]["extra"]}
    return f"{_urls(provider)['auth']}?{urlencode(params)}"


def read_state(state: str, provider: str) -> uuid.UUID:
    try:
        data = jwt.decode(state, _secret(), algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise OAuthError("La demande a expiré : recommencez la connexion.") from exc
    if data.get("p") != provider:
        raise OAuthError("Demande de connexion invalide.")
    return uuid.UUID(data["c"])


def _token_call(provider: str, data: dict) -> dict:
    client_id, client_secret = _creds(provider)
    try:
        res = httpx.post(_urls(provider)["token"], data={"client_id": client_id, "client_secret": client_secret, **data}, timeout=20)
    except httpx.HTTPError as exc:
        raise OAuthError(f"Le fournisseur est injoignable : {exc}") from exc
    if res.status_code != 200:
        raise OAuthError(f"Le fournisseur a refusé la connexion ({res.status_code}) : {res.text[:200]}")
    return res.json()


def finish(session: Session, company_id: uuid.UUID, provider: str, code: str, base: str) -> dict:
    token = _token_call(provider, {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri(provider, base)})
    refresh = token.get("refresh_token")
    if not refresh:
        raise OAuthError("Le fournisseur n'a pas donné d'accès durable : retirez l'autorisation précédente et recommencez.")
    access = token["access_token"]
    try:
        if provider == "google":
            who = httpx.get("https://www.googleapis.com/oauth2/v2/userinfo", headers={"Authorization": f"Bearer {access}"}, timeout=15).json().get("email")
        else:
            me = httpx.get("https://graph.microsoft.com/v1.0/me", headers={"Authorization": f"Bearer {access}"}, timeout=15).json()
            who = me.get("mail") or me.get("userPrincipalName")
    except (httpx.HTTPError, ValueError):
        who = None
    context = BusinessContextService(session).get_or_create(company_id)
    config = dict(context.configuration or {})
    oauth = dict(config.get("oauth") or {})
    oauth[provider] = {"refresh": _seal(refresh), "account": who, "connected_at": datetime.now(timezone.utc).isoformat()}
    config["oauth"] = oauth
    tools = dict(config.get("tools") or {})
    state = dict(tools.get(PROVIDERS[provider]["tool"]) or {})
    state["connection"] = "connected"
    tools[PROVIDERS[provider]["tool"]] = state
    config["tools"] = tools
    context.configuration = config
    session.commit()
    return {"account": who}


def disconnect(session: Session, company_id: uuid.UUID, provider: str) -> None:
    context = BusinessContextService(session).get_or_create(company_id)
    config = dict(context.configuration or {})
    oauth = dict(config.get("oauth") or {})
    oauth.pop(provider, None)
    config["oauth"] = oauth
    tools = dict(config.get("tools") or {})
    key = PROVIDERS[provider]["tool"]
    if key in tools:
        tools[key] = {k: v for k, v in tools[key].items() if k != "connection"}
    config["tools"] = tools
    context.configuration = config
    session.commit()


def status(session: Session, company_id: uuid.UUID) -> list[dict]:
    saved = (config_service.get_configuration(session, company_id).get("oauth")) or {}
    return [
        {"provider": p, "label": info["label"], "tool": info["tool"], "enabled": configured(p), "connected": p in saved, "account": (saved.get(p) or {}).get("account"), "connected_at": (saved.get(p) or {}).get("connected_at"), "last_sync": (saved.get(p) or {}).get("last_sync")}
        for p, info in PROVIDERS.items()
    ]


# --- reading the mailbox -----------------------------------------------------------

def _access_token(session: Session, company_id: uuid.UUID, provider: str) -> str:
    saved = ((config_service.get_configuration(session, company_id).get("oauth")) or {}).get(provider)
    if not saved:
        raise OAuthError("Messagerie non connectée.")
    return _token_call(provider, {"grant_type": "refresh_token", "refresh_token": _open(saved["refresh"])})["access_token"]


def _plain(text: str) -> str:
    return re.sub(r"\s+\n", "\n", re.sub(r"<[^>]+>", " ", text or "")).strip()[:8000]


def _gmail_body(payload: dict) -> str:
    def walk(part: dict) -> str:
        mime = part.get("mimeType", "")
        data = (part.get("body") or {}).get("data")
        if mime == "text/plain" and data:
            return base64.urlsafe_b64decode(data + "==").decode("utf-8", "replace")
        for sub in part.get("parts") or []:
            found = walk(sub)
            if found:
                return found
        if mime == "text/html" and data:
            return _plain(base64.urlsafe_b64decode(data + "==").decode("utf-8", "replace"))
        return ""

    return walk(payload)[:8000]


def fetch_google(token: str) -> list[ExternalEmail]:
    headers = {"Authorization": f"Bearer {token}"}
    base = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
    listing = httpx.get(base, headers=headers, params={"maxResults": MAX_MESSAGES, "q": "newer_than:60d -category:promotions -category:social"}, timeout=30)
    if listing.status_code != 200:
        raise OAuthError(f"Gmail a refusé la lecture ({listing.status_code}) : {listing.text[:200]}")
    out: list[ExternalEmail] = []
    for ref in listing.json().get("messages") or []:
        res = httpx.get(f"{base}/{ref['id']}", headers=headers, params={"format": "full"}, timeout=30)
        if res.status_code != 200:
            continue
        m = res.json()
        head = {h["name"].lower(): h["value"] for h in (m.get("payload") or {}).get("headers") or []}
        try:
            when = parsedate_to_datetime(head["date"])
        except (KeyError, TypeError, ValueError):
            when = datetime.fromtimestamp(int(m.get("internalDate", "0")) / 1000, tz=timezone.utc)
        sender = (getaddresses([head.get("from", "")])[0][1] if head.get("from") else "") or "inconnu"
        sent = "SENT" in (m.get("labelIds") or [])
        out.append(ExternalEmail(
            external_id=m["id"], thread_id=m.get("threadId", m["id"]), sender=sender, recipients=[a for _, a in getaddresses([head.get("to", "")]) if a],
            subject=head.get("subject", "(sans objet)")[:255], body=_gmail_body(m.get("payload") or {}) or m.get("snippet", ""),
            timestamp=when if when.tzinfo else when.replace(tzinfo=timezone.utc), direction="outbound" if sent else "inbound", status="sent" if sent else ("unread" if "UNREAD" in (m.get("labelIds") or []) else "read"),
        ))
    return out


def fetch_microsoft(token: str) -> list[ExternalEmail]:
    headers = {"Authorization": f"Bearer {token}", "Prefer": 'outlook.body-content-type="text"'}
    res = httpx.get("https://graph.microsoft.com/v1.0/me/messages", headers=headers, params={"$top": MAX_MESSAGES, "$orderby": "receivedDateTime desc", "$select": "id,conversationId,subject,from,toRecipients,body,receivedDateTime,isRead,isDraft"}, timeout=30)
    if res.status_code != 200:
        raise OAuthError(f"Outlook a refusé la lecture ({res.status_code}) : {res.text[:200]}")
    out: list[ExternalEmail] = []
    for m in res.json().get("value") or []:
        if m.get("isDraft"):
            continue
        when = datetime.fromisoformat((m.get("receivedDateTime") or "").replace("Z", "+00:00")) if m.get("receivedDateTime") else datetime.now(timezone.utc)
        out.append(ExternalEmail(
            external_id=m["id"], thread_id=m.get("conversationId") or m["id"], sender=((m.get("from") or {}).get("emailAddress") or {}).get("address", "inconnu"),
            recipients=[(r.get("emailAddress") or {}).get("address", "") for r in m.get("toRecipients") or []], subject=(m.get("subject") or "(sans objet)")[:255],
            body=((m.get("body") or {}).get("content") or "")[:8000], timestamp=when, direction="inbound", status="read" if m.get("isRead") else "unread",
        ))
    return out


def fetch(session: Session, company_id: uuid.UUID, provider: str) -> list[ExternalEmail]:
    token = _access_token(session, company_id, provider)
    return fetch_google(token) if provider == "google" else fetch_microsoft(token)


def mark_synced(session: Session, company_id: uuid.UUID, provider: str) -> None:
    context = BusinessContextService(session).get_or_create(company_id)
    config = dict(context.configuration or {})
    oauth = dict(config.get("oauth") or {})
    if provider in oauth:
        oauth[provider] = {**oauth[provider], "last_sync": datetime.now(timezone.utc).isoformat()}
        config["oauth"] = oauth
        context.configuration = config
        session.commit()
