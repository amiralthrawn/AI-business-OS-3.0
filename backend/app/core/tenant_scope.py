"""Company isolation for every ORM query of a signed-in request (V3).

Once `scope_session(session, company_id)` has run (app.access.deps does it
for every authenticated request), each ORM SELECT, UPDATE and DELETE on that
session is automatically filtered to that company:

- every model with a `company_id` column gets `company_id = <tenant>`;
- `Company` itself gets `id = <tenant>`, so the V1/V2 code that still does
  `db.query(Company).first()` resolves to the caller's own company.

This covers `session.get(...)`, relationship loads and the query API alike,
so an id from another company simply is "not found". New rows are checked at
flush: writing a row for another company raises instead of leaking.

Models without `company_id` (document lines, cost items, ...) are only
reachable through a parent that has one. A session that was never scoped
(seed scripts, background handlers that open their own session, the legacy
demo mode) is not filtered.
"""

import uuid

from sqlalchemy import event
from sqlalchemy.orm import Session, with_loader_criteria

from app.core.entities import Base, Company

TENANT_KEY = "tenant_company_id"


class CrossTenantWriteError(RuntimeError):
    pass


def scope_session(session: Session, company_id: uuid.UUID) -> None:
    session.info[TENANT_KEY] = company_id


def tenant_of(session: Session) -> uuid.UUID | None:
    return session.info.get(TENANT_KEY)


def _tenant_models() -> list[type]:
    return [
        mapper.class_
        for mapper in Base.registry.mappers
        if "company_id" in mapper.columns and mapper.class_ is not Company
    ]


@event.listens_for(Session, "do_orm_execute")
def _filter_to_tenant(state) -> None:
    company_id = state.session.info.get(TENANT_KEY)
    if company_id is None:
        return
    if not (state.is_select or state.is_update or state.is_delete):
        return
    if state.is_column_load:
        return
    options = [with_loader_criteria(Company, lambda cls: cls.id == company_id, include_aliases=True)]
    for model in _tenant_models():
        options.append(with_loader_criteria(model, lambda cls: cls.company_id == company_id, include_aliases=True))
    state.statement = state.statement.options(*options)


@event.listens_for(Session, "before_flush")
def _refuse_cross_tenant_writes(session: Session, flush_context, instances) -> None:
    company_id = session.info.get(TENANT_KEY)
    if company_id is None:
        return
    for obj in list(session.new) + list(session.dirty):
        if isinstance(obj, Company):
            if obj.id is not None and obj.id != company_id:
                raise CrossTenantWriteError("Write to another company refused")
            continue
        owner = getattr(obj, "company_id", None)
        if owner is not None and owner != company_id:
            raise CrossTenantWriteError("Write to another company refused")
