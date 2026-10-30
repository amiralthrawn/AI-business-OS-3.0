# Permissions (V2 / V2.1 / V3)

```
BASE ROLE               → default permissions      (app/access/policy.py)
+ COMPANY ROLE (V3)     → grants / revokes          (CustomRole.access_grants / access_revokes)
+ CUSTOM PROFILE ACCESS → grants / revokes          (UserProfile.access_grants / access_revokes)
= EFFECTIVE PERMISSIONS → enforced by the backend, reflected by the UI
```

Base roles: director, sales, procurement, operations, hr, employee and (V3)
accountant. A director creates the company's own roles ("Assistante ADV",
"Responsable logistique") on top of a base role; a profile holding one gets
`role = custom_role.base_role` (approval scope follows the base role).

## Vocabulary

- `view:*` — what a profile sees (navigation **and** read APIs): sales, procurement, catalog, communications, people, finance, intelligence, actions, compliance, settings, and the sensitive **employee_costs**, **treasury**, **ownership**.
- `write:*` — what it can edit: sales, procurement, operations, finance, catalog, communications, people, treasury, compliance, settings.
- `action:*` — submit_email, approve, ask_ai.

`ACCESS_CATALOG` lists every permission once with a label, a group and a
sensitive flag; Settings → Profils et rôles renders it as checkboxes.

## Defaults

Director: everything. Sales, Procurement, Operations, HR, Employee: see the
matrix in `policy.py`. **Treasury, ownership and employee costs are
director-only by default**; a director can grant them to a profile.

## Enforcement

- Every workspace router carries `Depends(require(view:…))` (`app/main.py`).
- Writes check their `write:*` permission; document kinds map to permissions (`KIND_WRITE_PERMISSION`).
- Object context and search check the object's view permission and hide related groups the profile cannot open.
- HITL approval is domain-scoped (`can_approve_with`): sales approves sales/marketing, procurement approves procurement/operations; **people decisions, compliance, website changes, finance and tasks without domain: director only**.
- Salary data never leaves the API without `view:employee_costs` (the employee page returns `cost: null`; a raise proposal requires cost access).

## Administration rules

- Only a profile with `write:settings` changes roles, activation or access.
- **Nobody edits their own role, activation or access** (backend refuses; UI shows read-only) — no self-granting.
- Unknown permission names are rejected (400) and ignored if ever stored.
- Deactivated profiles are refused (401).

## Identity and companies (V3)

- **Accounts.** A profile with a `password_hash` is a sign-in account
  (scrypt, `app/auth/security.py`). The director gets one at `/auth/signup`,
  which also creates the company. Everyone else joins through an invitation:
  `POST /users/{id}/invite` (write:settings) returns a single-use link valid 7
  days; only its SHA-256 is stored. Emails are unique and lower-cased.
- **Tokens.** Sign-in returns a JWT (HS256, `AUTH_SECRET_KEY`, 12 h) naming
  the profile and its company. Each request re-checks that the profile still
  exists, is active and belongs to that company, so deactivating someone
  cuts access at once. The frontend keeps the token in the `aibos_session`
  cookie and sends it as `Authorization: Bearer`.
- **Company isolation.** `get_current_user` scopes the request's session to
  the token's company (`app/core/tenant_scope.py`): every ORM SELECT /
  UPDATE / DELETE is filtered on `company_id` (and `Company.id`), including
  `session.get` and relationship loads, so another company's id is simply
  "not found"; a flush writing a row for another company raises. The Event
  Log carries `company_id` too, filled from the publishing request
  (`app/core/events/tenant.py`), so timelines and decisions never cross.
- **Public routes:** `/auth/*` and `/health` only.
- **Legacy mode.** `AUTH_MODE=legacy` keeps the V2 behavior below (declared
  identity via `X-User-Id`, no isolation) for the bundled demo and the V2
  test suite. Never for real customers.
- **Not yet:** single sign-on, password reset by email, sign-in rate
  limiting, PostgreSQL row-level security as a second barrier, and an
  httpOnly session cookie (the token is readable by the page's JavaScript
  because client components call the API directly).

## Identity in legacy mode (V2)


There is no authentication in this MVP: the selected profile id is sent as
`X-User-Id` (cookie `aibos_user`). This is an authorization model enforced
server-side, **not** a security boundary until a real auth layer produces the
same `CurrentUser` from a verified token. No header = legacy single-operator
mode with director rights (kept for V1 clients and tests).
