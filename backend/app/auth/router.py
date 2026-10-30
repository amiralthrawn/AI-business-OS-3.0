"""Sign-up, sign-in and invitation acceptance (V3).

These are the only API routes reachable without a token. Sign-up creates a
new company with its director account; everyone else joins a company through
an invitation link created by someone with `write:settings`
(POST /users/{id}/invite).
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.security import (
    MIN_PASSWORD_LENGTH,
    burn_password_check,
    create_access_token,
    hash_invite_token,
    hash_password,
    normalize_email,
    verify_password,
)
from app.config import get_settings
from app.core.entities import BusinessContext, Company, Role, UserProfile
from app.core.i18n import tx
from app.database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=3, max_length=255)
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class AcceptInviteRequest(BaseModel):
    password: str
    name: str | None = None


class SessionRead(BaseModel):
    access_token: str
    token_type: str = "bearer"
    profile_id: uuid.UUID
    company_id: uuid.UUID
    name: str
    role: Role


class InvitationRead(BaseModel):
    name: str
    email: str | None
    company_name: str
    job_title: str | None


def _check_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=tx(
                f"Le mot de passe doit contenir au moins {MIN_PASSWORD_LENGTH} caractères.",
                f"The password must be at least {MIN_PASSWORD_LENGTH} characters long.",
            ),
        )


def _valid_email(email: str | None) -> str:
    if not email or "@" not in email or email.startswith("@") or email.endswith("@"):
        raise HTTPException(status_code=400, detail=tx("Adresse e-mail invalide.", "Invalid email address."))
    return email


def _session_for(profile: UserProfile, db: Session) -> SessionRead:
    profile.last_login_at = datetime.now(timezone.utc)
    db.commit()
    return SessionRead(
        access_token=create_access_token(profile.id, profile.company_id),
        profile_id=profile.id,
        company_id=profile.company_id,
        name=profile.name,
        role=profile.role,
    )


@router.post("/signup", response_model=SessionRead, status_code=201)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> SessionRead:
    if not get_settings().signup_enabled:
        raise HTTPException(status_code=403, detail=tx("La création de compte est fermée.", "Sign-up is closed."))
    email = _valid_email(normalize_email(payload.email))
    _check_password(payload.password)
    if db.query(UserProfile.id).filter_by(email=email).first() is not None:
        raise HTTPException(status_code=409, detail=tx("Un compte existe déjà avec cette adresse.", "An account already exists with this email."))

    company = Company(name=payload.company_name.strip())
    db.add(company)
    db.flush()
    db.add(BusinessContext(company_id=company.id))
    director = UserProfile(
        company_id=company.id,
        name=payload.name.strip(),
        email=email,
        role=Role.DIRECTOR,
        access_grants=[],
        access_revokes=[],
        password_hash=hash_password(payload.password),
    )
    db.add(director)
    db.flush()
    return _session_for(director, db)


@router.post("/login", response_model=SessionRead)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> SessionRead:
    email = normalize_email(payload.email)
    profile = db.query(UserProfile).filter_by(email=email).first() if email else None
    if profile is None or not profile.password_hash:
        burn_password_check(payload.password)
        profile = None
    elif not verify_password(payload.password, profile.password_hash):
        profile = None
    if profile is None or not profile.is_active:
        raise HTTPException(status_code=401, detail=tx("E-mail ou mot de passe incorrect.", "Incorrect email or password."))
    return _session_for(profile, db)


def _pending_invitation(token: str, db: Session) -> UserProfile:
    profile = db.query(UserProfile).filter_by(invite_token_hash=hash_invite_token(token)).first()
    expires = profile.invite_expires_at if profile else None
    if expires is not None and expires.tzinfo is None:  # SQLite returns naive datetimes
        expires = expires.replace(tzinfo=timezone.utc)
    if profile is None or not profile.is_active or expires is None or expires < datetime.now(timezone.utc):
        raise HTTPException(status_code=404, detail=tx("Invitation invalide ou expirée.", "Invalid or expired invitation."))
    return profile


@router.get("/invitations/{token}", response_model=InvitationRead)
def read_invitation(token: str, db: Session = Depends(get_db)) -> InvitationRead:
    profile = _pending_invitation(token, db)
    company = db.get(Company, profile.company_id)
    return InvitationRead(name=profile.name, email=profile.email, company_name=company.name if company else "", job_title=profile.job_title)


@router.post("/invitations/{token}/accept", response_model=SessionRead)
def accept_invitation(token: str, payload: AcceptInviteRequest, db: Session = Depends(get_db)) -> SessionRead:
    profile = _pending_invitation(token, db)
    _check_password(payload.password)
    profile.password_hash = hash_password(payload.password)
    profile.invite_token_hash = None
    profile.invite_expires_at = None
    if payload.name and payload.name.strip():
        profile.name = payload.name.strip()
    return _session_for(profile, db)
