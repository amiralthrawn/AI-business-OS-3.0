"""Who is calling, and may they.

V3, `AUTH_MODE=required` (the default): identity comes from a signed access
token (`Authorization: Bearer ...`, app.auth). The profile must still exist,
be active, have an account and belong to the company named in the token.
The request's database session is then scoped to that company
(app.core.tenant_scope): nothing from another company can be read or written.
No token, or an invalid one -> 401.

`AUTH_MODE=legacy` (the bundled demo and the test suite): the V2 behavior.
Identity comes from the `X-User-Id` header naming a UserProfile -- a
*declared* identity, not an authenticated one -- and no header means the
single-operator mode with full director rights, reported as `profile=None`.
"""

import uuid
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.auth.security import decode_access_token
from app.config import get_settings
from app.core.tenant_scope import scope_session

from app.core.i18n import tx
from app.access.policy import can_approve_with, effective_permissions, profile_permissions
from app.core.entities import Role, UserProfile
from app.database import get_db


@dataclass(frozen=True)
class CurrentUser:
    role: Role
    profile: UserProfile | None

    @property
    def permissions(self) -> frozenset[str]:
        # Role defaults + the director's custom grants/revokes for this profile.
        if self.profile is None:
            return effective_permissions(self.role)
        return profile_permissions(self.profile)

    def can(self, permission: str) -> bool:
        return permission in self.permissions

    def can_approve(self, task_domain: str | None) -> bool:
        return can_approve_with(self.role, self.permissions, task_domain)


LEGACY_OPERATOR = CurrentUser(role=Role.DIRECTOR, profile=None)


def _unauthenticated() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=tx("Veuillez vous connecter.", "Please sign in."),
        headers={"WWW-Authenticate": "Bearer"},
    )


def _authenticated_user(authorization: str | None, db: Session) -> CurrentUser:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _unauthenticated()
    claims = decode_access_token(token.strip())
    if claims is None:
        raise _unauthenticated()
    profile_id, company_id = claims
    profile = db.get(UserProfile, profile_id)
    if profile is None or not profile.is_active or not profile.password_hash or profile.company_id != company_id:
        raise _unauthenticated()
    scope_session(db, company_id)
    return CurrentUser(role=profile.role, profile=profile)


def get_current_user(
    x_user_id: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> CurrentUser:
    if get_settings().auth_mode != "legacy":
        return _authenticated_user(authorization, db)
    if not x_user_id:
        return LEGACY_OPERATOR
    try:
        user_id = uuid.UUID(x_user_id)
    except ValueError:
        raise HTTPException(status_code=401, detail=tx("Profil utilisateur inconnu", "Unknown user profile"))
    profile = db.get(UserProfile, user_id)
    if profile is None or not profile.is_active:
        raise HTTPException(status_code=401, detail=tx("Profil utilisateur inconnu", "Unknown user profile"))
    return CurrentUser(role=profile.role, profile=profile)


def require(permission: str):
    """FastAPI dependency factory: 403 unless the caller's effective permissions include `permission`."""

    def dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not user.can(permission):
            raise HTTPException(status_code=403, detail=tx(f"Votre profil n'a pas accès à cette partie du logiciel ({permission}).", f"Your profile does not have access to this part of the software ({permission})."))
        return user

    return dependency
