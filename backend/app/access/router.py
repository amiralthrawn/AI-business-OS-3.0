import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.i18n import tx
from app.access.deps import CurrentUser, get_current_user
from app.access.policy import (
    ACCESS_CATALOG,
    ALL_PERMISSIONS,
    WRITE_SETTINGS,
    custom_role_permissions,
    profile_permissions,
    role_defaults,
    role_label,
)
from app.auth.security import new_invite_token, normalize_email
from app.config import get_settings
from app.core.entities import Company, CustomRole, Role, UserProfile
from app.core.tenancy import current_company
from app.database import get_db

router = APIRouter(prefix="/users", tags=["users"])


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str | None
    role: Role
    is_active: bool
    access_grants: list[str]
    access_revokes: list[str]
    permissions: list[str] = []
    # V3
    job_title: str | None = None
    custom_role_id: uuid.UUID | None = None
    custom_role_name: str | None = None
    account_status: str = "no_access"
    last_login_at: datetime | None = None

    @classmethod
    def of(cls, profile: UserProfile) -> "UserRead":
        data = cls.model_validate(profile)
        data.permissions = sorted(profile_permissions(profile))
        data.custom_role_name = profile.custom_role.name if profile.custom_role else None
        return data


class UserCreate(BaseModel):
    name: str
    email: str | None = None
    role: Role = Role.EMPLOYEE
    job_title: str | None = None
    custom_role_id: uuid.UUID | None = None


class UserUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    role: Role | None = None
    is_active: bool | None = None
    access_grants: list[str] | None = None
    access_revokes: list[str] | None = None
    job_title: str | None = None
    custom_role_id: uuid.UUID | None = None


class InviteRead(BaseModel):
    invite_url: str
    expires_at: datetime


class CustomRoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    base_role: Role
    access_grants: list[str]
    access_revokes: list[str]
    permissions: list[str] = []
    members: int = 0


class CustomRoleWrite(BaseModel):
    name: str | None = None
    description: str | None = None
    base_role: Role | None = None
    access_grants: list[str] | None = None
    access_revokes: list[str] | None = None


class RoleRead(BaseModel):
    role: Role
    label: str
    permissions: list[str]


class MeRead(BaseModel):
    profile: UserRead | None
    role: Role
    role_label: str
    permissions: list[str]


@router.get("/roles", response_model=list[RoleRead])
def list_roles() -> list[RoleRead]:
    return [RoleRead(role=r, label=role_label(r), permissions=sorted(role_defaults(r))) for r in Role]


@router.get("/access-catalog")
def access_catalog() -> dict:
    """Everything a director can tick/untick per profile, and each role's defaults."""

    return {
        "items": [{"permission": i.permission, "label": i.label, "group": i.group, "sensitive": i.sensitive} for i in ACCESS_CATALOG],
        "role_defaults": {r.value: sorted(role_defaults(r)) for r in Role},
    }


def _require_settings(user: CurrentUser) -> None:
    if not user.can(WRITE_SETTINGS):
        raise HTTPException(status_code=403, detail=tx("Votre profil ne permet pas de gérer les utilisateurs.", "Your profile does not allow managing users."))


def _clean_permissions(changes: dict) -> None:
    for key in ("access_grants", "access_revokes"):
        if key in changes:
            unknown = set(changes[key] or []) - ALL_PERMISSIONS
            if unknown:
                raise HTTPException(status_code=400, detail=tx(f"Permission inconnue : {', '.join(sorted(unknown))}", f"Unknown permission: {', '.join(sorted(unknown))}"))
            changes[key] = sorted(set(changes[key] or []))


def _custom_role_read(role: CustomRole, db: Session) -> CustomRoleRead:
    data = CustomRoleRead.model_validate(role)
    data.permissions = sorted(custom_role_permissions(role))
    data.members = db.query(UserProfile.id).filter_by(custom_role_id=role.id).count()
    return data


def _custom_role(role_id: uuid.UUID, db: Session, company: Company) -> CustomRole:
    role = db.get(CustomRole, role_id)
    if role is None or role.company_id != company.id:
        raise HTTPException(status_code=404, detail=tx("Rôle introuvable", "Role not found"))
    return role


@router.get("/custom-roles", response_model=list[CustomRoleRead])
def list_custom_roles(db: Session = Depends(get_db), company: Company = Depends(current_company)) -> list[CustomRoleRead]:
    roles = db.query(CustomRole).filter_by(company_id=company.id).order_by(CustomRole.name).all()
    return [_custom_role_read(r, db) for r in roles]


@router.post("/custom-roles", response_model=CustomRoleRead, status_code=201)
def create_custom_role(
    payload: CustomRoleWrite,
    db: Session = Depends(get_db),
    company: Company = Depends(current_company),
    user: CurrentUser = Depends(get_current_user),
) -> CustomRoleRead:
    _require_settings(user)
    changes = payload.model_dump(exclude_unset=True)
    if not (changes.get("name") or "").strip() or changes.get("base_role") is None:
        raise HTTPException(status_code=400, detail=tx("Un rôle a besoin d'un nom et d'un rôle de base.", "A role needs a name and a base role."))
    _clean_permissions(changes)
    role = CustomRole(
        company_id=company.id,
        name=changes["name"].strip(),
        description=changes.get("description"),
        base_role=changes["base_role"],
        access_grants=changes.get("access_grants", []),
        access_revokes=changes.get("access_revokes", []),
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    return _custom_role_read(role, db)


@router.patch("/custom-roles/{role_id}", response_model=CustomRoleRead)
def update_custom_role(
    role_id: uuid.UUID,
    payload: CustomRoleWrite,
    db: Session = Depends(get_db),
    company: Company = Depends(current_company),
    user: CurrentUser = Depends(get_current_user),
) -> CustomRoleRead:
    _require_settings(user)
    role = _custom_role(role_id, db, company)
    changes = payload.model_dump(exclude_unset=True)
    _clean_permissions(changes)
    if "name" in changes:
        if not (changes["name"] or "").strip():
            raise HTTPException(status_code=400, detail=tx("Un rôle a besoin d'un nom.", "A role needs a name."))
        changes["name"] = changes["name"].strip()
    for field, value in changes.items():
        if value is not None or field == "description":
            setattr(role, field, value)
    if "base_role" in changes and changes["base_role"] is not None:
        # Holders' role mirrors the custom role's base (approval scope, labels).
        for member in db.query(UserProfile).filter_by(custom_role_id=role.id).all():
            member.role = role.base_role
    db.commit()
    db.refresh(role)
    return _custom_role_read(role, db)


@router.delete("/custom-roles/{role_id}", status_code=204)
def delete_custom_role(
    role_id: uuid.UUID,
    db: Session = Depends(get_db),
    company: Company = Depends(current_company),
    user: CurrentUser = Depends(get_current_user),
) -> None:
    _require_settings(user)
    role = _custom_role(role_id, db, company)
    if db.query(UserProfile.id).filter_by(custom_role_id=role.id).first() is not None:
        raise HTTPException(status_code=409, detail=tx("Ce rôle est encore attribué à des personnes.", "This role is still assigned to people."))
    db.delete(role)
    db.commit()


@router.get("/me", response_model=MeRead)
def me(user: CurrentUser = Depends(get_current_user)) -> MeRead:
    return MeRead(
        profile=UserRead.of(user.profile) if user.profile else None,
        role=user.role,
        role_label=role_label(user.role),
        permissions=sorted(user.permissions),
    )


@router.get("", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db), company: Company = Depends(current_company)) -> list[UserRead]:
    return [UserRead.of(u) for u in db.query(UserProfile).filter_by(company_id=company.id).order_by(UserProfile.created_at).all()]


@router.post("", response_model=UserRead)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    company: Company = Depends(current_company),
    user: CurrentUser = Depends(get_current_user),
) -> UserRead:
    # The very first profile is created by onboarding, before anyone exists
    # to hold WRITE_SETTINGS; every later one needs it.
    has_any = db.query(UserProfile.id).filter_by(company_id=company.id).first() is not None
    if has_any and not user.can(WRITE_SETTINGS):
        raise HTTPException(status_code=403, detail=tx("Votre profil ne permet pas de gérer les utilisateurs.", "Your profile does not allow managing users."))
    email = _unique_email(payload.email, db)
    profile = UserProfile(
        company_id=company.id,
        name=payload.name.strip(),
        email=email,
        role=payload.role,
        job_title=(payload.job_title or "").strip() or None,
        access_grants=[],
        access_revokes=[],
    )
    if payload.custom_role_id is not None:
        role = _custom_role(payload.custom_role_id, db, company)
        profile.custom_role_id = role.id
        profile.role = role.base_role
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return UserRead.of(profile)


def _unique_email(email: str | None, db: Session, exclude: uuid.UUID | None = None) -> str | None:
    """Emails are sign-in identifiers (V3): normalized and unique across companies."""

    email = normalize_email(email)
    if email is None:
        return None
    if "@" not in email:
        raise HTTPException(status_code=400, detail=tx("Adresse e-mail invalide.", "Invalid email address."))
    taken = db.query(UserProfile.id).filter(UserProfile.email == email)
    if exclude is not None:
        taken = taken.filter(UserProfile.id != exclude)
    if taken.first() is not None:
        raise HTTPException(status_code=409, detail=tx("Cette adresse e-mail est déjà utilisée.", "This email address is already in use."))
    return email


_ADMIN_FIELDS = {"role", "is_active", "access_grants", "access_revokes", "custom_role_id", "job_title"}


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> UserRead:
    profile = db.get(UserProfile, user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=tx("Profil introuvable", "Profile not found"))
    changes = payload.model_dump(exclude_unset=True)
    editing_self = user.profile is not None and user.profile.id == profile.id
    admin_change = bool(_ADMIN_FIELDS & changes.keys())

    # Anyone may rename themselves. Access, role and activation are an
    # administrator's decision (write:settings) -- and never on one's own
    # profile: nobody grants themselves permissions (brain/permissions.md).
    if admin_change and editing_self:
        raise HTTPException(status_code=403, detail=tx("Vous ne pouvez pas modifier vos propres accès ou votre propre rôle.", "You cannot change your own access or your own role."))
    if (admin_change or not editing_self) and not user.can(WRITE_SETTINGS):
        raise HTTPException(status_code=403, detail=tx("Votre profil ne permet pas de gérer les utilisateurs.", "Your profile does not allow managing users."))
    _clean_permissions(changes)
    if "email" in changes:
        changes["email"] = _unique_email(changes["email"], db, exclude=profile.id)
    if "custom_role_id" in changes:
        if changes["custom_role_id"] is not None:
            role = _custom_role(changes["custom_role_id"], db, db.get(Company, profile.company_id))
            changes["role"] = role.base_role
    elif "role" in changes and profile.custom_role_id is not None:
        # Picking a base role directly leaves the custom role.
        changes["custom_role_id"] = None
    if "job_title" in changes:
        changes["job_title"] = (changes["job_title"] or "").strip() or None
    for field, value in changes.items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return UserRead.of(profile)


@router.post("/{user_id}/invite", response_model=InviteRead)
def invite_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> InviteRead:
    """Creates (or renews) a one-time sign-up link for this profile. The link
    is returned to the director to share; sending it by email comes with the
    real email connector."""

    _require_settings(user)
    profile = db.get(UserProfile, user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=tx("Profil introuvable", "Profile not found"))
    if not profile.email:
        raise HTTPException(status_code=400, detail=tx("Ajoutez d'abord une adresse e-mail à ce profil.", "Add an email address to this profile first."))
    if profile.password_hash:
        raise HTTPException(status_code=409, detail=tx("Cette personne a déjà un compte.", "This person already has an account."))
    token, token_hash = new_invite_token()
    settings = get_settings()
    profile.invite_token_hash = token_hash
    profile.invite_expires_at = datetime.now(timezone.utc) + timedelta(days=settings.invite_ttl_days)
    expires_at = profile.invite_expires_at
    db.commit()
    return InviteRead(invite_url=f"{settings.frontend_url.rstrip('/')}/invitation/{token}", expires_at=expires_at)
