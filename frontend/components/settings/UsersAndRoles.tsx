"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import { createCustomRole, createUser, deleteCustomRole, inviteUser, updateCustomRole, updateUser } from "@/lib/api";
import { ROLE_LABEL } from "@/lib/objects";
import type { AccessCatalog, CustomRoleRead, Role, RoleRead, UserProfileRead } from "@/lib/types";

// Team and access (V2.1 profiles + V3 accounts and company roles,
// brain/permissions.md). Three layers decide what a person sees:
// base role defaults -> the company role's changes -> this person's changes.
// The backend enforces the result; this screen only edits it. Nobody edits
// their own access (the backend refuses it too).

const ACCOUNT_BADGE: Record<UserProfileRead["account_status"], { label: string; tone: "success" | "accent" | "neutral" }> = {
  active: { label: "Compte actif", tone: "success" },
  invited: { label: "Invitation envoyée", tone: "accent" },
  no_access: { label: "Sans compte", tone: "neutral" },
};

const inputClass = "rounded-xl border-[1.5px] border-border-strong px-3.5 py-2.5 text-[13.5px] outline-none focus:border-accent";

/** "<base role>" or "custom:<id>": one select for both kinds of role. */
function roleValue(u: { role: Role; custom_role_id: string | null }): string {
  return u.custom_role_id ? `custom:${u.custom_role_id}` : u.role;
}

function rolePayload(value: string): { role?: Role; custom_role_id?: string } {
  return value.startsWith("custom:") ? { custom_role_id: value.slice(7) } : { role: value as Role };
}

function RoleSelect({ value, onChange, roles, customRoles, disabled }: { value: string; onChange: (v: string) => void; roles: RoleRead[]; customRoles: CustomRoleRead[]; disabled?: boolean }) {
  return (
    <select value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)} className={`${inputClass} py-1.5`}>
      {customRoles.length > 0 && (
        <optgroup label="Rôles de l'entreprise">
          {customRoles.map((r) => (
            <option key={r.id} value={`custom:${r.id}`}>
              {r.name}
            </option>
          ))}
        </optgroup>
      )}
      <optgroup label="Rôles de base">
        {roles.map((r) => (
          <option key={r.role} value={r.role}>
            {r.label}
          </option>
        ))}
      </optgroup>
    </select>
  );
}

/** The permission checklist, shared by people and company roles. */
function AccessChecklist({
  catalog,
  permissions,
  defaults,
  editable,
  busy,
  onToggle,
  changedLabel,
}: {
  catalog: AccessCatalog;
  permissions: string[];
  defaults: Set<string>;
  editable: boolean;
  busy: boolean;
  onToggle: (permission: string, on: boolean) => void;
  changedLabel: (on: boolean) => string;
}) {
  const groups = [...new Set(catalog.items.map((i) => i.group))];
  return (
    <div className="mt-4 grid gap-5 md:grid-cols-2">
      {groups.map((group) => (
        <div key={group}>
          <p className="mb-2 text-[11.5px] font-bold uppercase tracking-wide text-text-faint">{group}</p>
          <ul className="space-y-1.5">
            {catalog.items
              .filter((i) => i.group === group)
              .map((item) => {
                const on = permissions.includes(item.permission);
                const changed = on !== defaults.has(item.permission);
                return (
                  <li key={item.permission}>
                    <label className={`flex items-center gap-2.5 text-[13px] ${editable ? "cursor-pointer" : ""}`}>
                      <input
                        type="checkbox"
                        checked={on}
                        disabled={!editable || busy}
                        onChange={(e) => onToggle(item.permission, e.target.checked)}
                        className="h-4 w-4 accent-[var(--color-accent)]"
                      />
                      <span className={on ? "text-text" : "text-text-faint"}>{item.label}</span>
                      {item.sensitive && <Badge label="Sensible" tone="warning" />}
                      {changed && <span className="text-[11px] text-accent-strong">{changedLabel(on)}</span>}
                    </label>
                  </li>
                );
              })}
          </ul>
        </div>
      ))}
    </div>
  );
}

/** Grants / revokes so that `permission` ends up `on`, relative to `defaults`. */
function toggled(defaults: Set<string>, grantsIn: string[], revokesIn: string[], permission: string, on: boolean) {
  const grants = new Set(grantsIn);
  const revokes = new Set(revokesIn);
  grants.delete(permission);
  revokes.delete(permission);
  if (on && !defaults.has(permission)) grants.add(permission);
  if (!on && defaults.has(permission)) revokes.add(permission);
  return { access_grants: [...grants], access_revokes: [...revokes] };
}

export default function UsersAndRoles({
  users,
  roles,
  customRoles,
  catalog,
  canManage,
  selfId,
}: {
  users: UserProfileRead[];
  roles: RoleRead[];
  customRoles: CustomRoleRead[];
  catalog: AccessCatalog | null;
  canManage: boolean;
  selfId: string | null;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [inviteLinks, setInviteLinks] = useState<Record<string, string>>({});
  // New person
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [newRole, setNewRole] = useState<string>("employee");
  // New company role
  const [roleName, setRoleName] = useState("");
  const [baseRole, setBaseRole] = useState<Role>("employee");

  async function run(fn: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Une erreur est survenue.");
    } finally {
      setBusy(false);
    }
  }

  function defaultsFor(u: UserProfileRead): Set<string> {
    const custom = customRoles.find((r) => r.id === u.custom_role_id);
    return new Set(custom ? custom.permissions : (catalog?.role_defaults[u.role] ?? []));
  }

  async function invite(u: UserProfileRead) {
    await run(async () => {
      const { invite_url } = await inviteUser(u.id);
      setInviteLinks((links) => ({ ...links, [u.id]: invite_url }));
      await navigator.clipboard?.writeText(invite_url).catch(() => undefined);
    });
  }

  return (
    <div className="space-y-8">
      <div className="space-y-5">
        <Card className="divide-y divide-border">
          {users.length === 0 && <p className="p-5 text-[13px] text-text-faint">Personne pour l&rsquo;instant.</p>}
          {users.map((u) => {
            const isSelf = u.id === selfId;
            const editable = canManage && !isSelf;
            const defaults = defaultsFor(u);
            const custom = u.access_grants.length + u.access_revokes.length;
            const account = ACCOUNT_BADGE[u.account_status];
            return (
              <div key={u.id} className="p-4 text-[13.5px]">
                <div className="flex flex-wrap items-center gap-3">
                  <span className="min-w-[180px] flex-1">
                    <span className="block font-medium text-text">
                      {u.name} {isSelf && <span className="text-[12px] font-normal text-text-faint">(vous)</span>}
                    </span>
                    <span className="block text-[12px] text-text-faint">{[u.job_title, u.email].filter(Boolean).join(" · ") || "Ni poste ni e-mail"}</span>
                  </span>
                  <Badge label={account.label} tone={account.tone} />
                  {!u.is_active && <Badge label="Désactivé" tone="neutral" />}
                  {custom > 0 && <Badge label={`Accès personnalisés (${custom})`} tone="accent" />}
                  {editable ? (
                    <RoleSelect value={roleValue(u)} roles={roles} customRoles={customRoles} disabled={busy} onChange={(v) => run(() => updateUser(u.id, rolePayload(v)))} />
                  ) : (
                    <Badge label={u.custom_role_name ?? ROLE_LABEL[u.role]} tone="accent" />
                  )}
                  {catalog && (
                    <button type="button" onClick={() => setOpen(open === u.id ? null : u.id)} className="text-[12.5px] font-medium text-accent-strong hover:underline">
                      {open === u.id ? "Fermer" : editable ? "Gérer les accès" : "Voir les accès"}
                    </button>
                  )}
                  {editable && u.account_status !== "active" && u.email && (
                    <button type="button" disabled={busy} onClick={() => invite(u)} className="text-[12.5px] font-medium text-accent-strong hover:underline">
                      {u.account_status === "invited" ? "Renvoyer l'invitation" : "Inviter"}
                    </button>
                  )}
                  {editable && (
                    <button type="button" disabled={busy} onClick={() => run(() => updateUser(u.id, { is_active: !u.is_active }))} className="text-[12.5px] text-text-faint hover:text-text">
                      {u.is_active ? "Désactiver" : "Réactiver"}
                    </button>
                  )}
                </div>
                {inviteLinks[u.id] && (
                  <p className="mt-3 rounded-lg bg-surface-sunken px-3 py-2 text-[12.5px] text-text-soft">
                    Lien d&rsquo;invitation copié, à envoyer à {u.name} (valable 7 jours) :{" "}
                    <span className="break-all font-mono text-[11.5px] text-text">{inviteLinks[u.id]}</span>
                  </p>
                )}
                {open === u.id && catalog && (
                  <>
                    {editable && (
                      <label className="mt-4 flex max-w-sm flex-col gap-1.5 text-[12.5px] text-text-soft">
                        Poste
                        <input
                          defaultValue={u.job_title ?? ""}
                          placeholder="ex. Responsable logistique"
                          onBlur={(e) => e.target.value !== (u.job_title ?? "") && run(() => updateUser(u.id, { job_title: e.target.value }))}
                          className={inputClass}
                        />
                      </label>
                    )}
                    <AccessChecklist
                      catalog={catalog}
                      permissions={u.permissions}
                      defaults={defaults}
                      editable={editable}
                      busy={busy}
                      onToggle={(p, on) => run(() => updateUser(u.id, toggled(defaults, u.access_grants, u.access_revokes, p, on)))}
                      changedLabel={(on) => (on ? "ajouté pour cette personne" : "retiré pour cette personne")}
                    />
                    {isSelf && <p className="mt-3 text-[12px] text-text-faint">Vous ne pouvez pas modifier vos propres accès : un autre profil Direction doit le faire.</p>}
                  </>
                )}
              </div>
            );
          })}
        </Card>

        {canManage && (
          <div className="flex flex-wrap items-center gap-2">
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Nom" className={inputClass} />
            <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="E-mail" type="email" className={inputClass} />
            <input value={jobTitle} onChange={(e) => setJobTitle(e.target.value)} placeholder="Poste" className={inputClass} />
            <RoleSelect value={newRole} roles={roles} customRoles={customRoles} onChange={setNewRole} />
            <Button
              disabled={!name.trim()}
              loading={busy}
              onClick={() =>
                run(async () => {
                  await createUser({ name: name.trim(), email: email.trim() || undefined, job_title: jobTitle.trim() || undefined, ...rolePayload(newRole) });
                  setName("");
                  setEmail("");
                  setJobTitle("");
                })
              }
            >
              Ajouter la personne
            </Button>
          </div>
        )}
      </div>

      <div className="space-y-4">
        <div>
          <p className="text-[14px] font-semibold text-text">Rôles de l&rsquo;entreprise</p>
          <p className="mt-1 text-[12.5px] text-text-soft">
            Créez vos propres rôles à partir d&rsquo;un rôle de base, puis choisissez ce qu&rsquo;ils voient. Modifier un rôle change les accès de toutes les personnes qui l&rsquo;ont.
          </p>
        </div>
        {customRoles.length > 0 && (
          <Card className="divide-y divide-border">
            {customRoles.map((r) => {
              const defaults = new Set(catalog?.role_defaults[r.base_role] ?? []);
              return (
                <div key={r.id} className="p-4 text-[13.5px]">
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="flex-1 font-medium text-text">{r.name}</span>
                    <span className="text-[12px] text-text-faint">
                      Basé sur {ROLE_LABEL[r.base_role]} · {r.members} personne{r.members > 1 ? "s" : ""}
                    </span>
                    {catalog && (
                      <button type="button" onClick={() => setOpen(open === r.id ? null : r.id)} className="text-[12.5px] font-medium text-accent-strong hover:underline">
                        {open === r.id ? "Fermer" : canManage ? "Gérer les accès" : "Voir les accès"}
                      </button>
                    )}
                    {canManage && r.members === 0 && (
                      <button type="button" disabled={busy} onClick={() => run(() => deleteCustomRole(r.id))} className="text-[12.5px] text-text-faint hover:text-danger">
                        Supprimer
                      </button>
                    )}
                  </div>
                  {open === r.id && catalog && (
                    <AccessChecklist
                      catalog={catalog}
                      permissions={r.permissions}
                      defaults={defaults}
                      editable={canManage}
                      busy={busy}
                      onToggle={(p, on) => run(() => updateCustomRole(r.id, toggled(defaults, r.access_grants, r.access_revokes, p, on)))}
                      changedLabel={(on) => (on ? "ajouté pour ce rôle" : "retiré pour ce rôle")}
                    />
                  )}
                </div>
              );
            })}
          </Card>
        )}
        {canManage && (
          <div className="flex flex-wrap items-center gap-2">
            <input value={roleName} onChange={(e) => setRoleName(e.target.value)} placeholder="Nom du rôle, ex. Assistante ADV" className={inputClass} />
            <select value={baseRole} onChange={(e) => setBaseRole(e.target.value as Role)} className={inputClass}>
              {roles.map((r) => (
                <option key={r.role} value={r.role}>
                  Basé sur : {r.label}
                </option>
              ))}
            </select>
            <Button
              variant="ghost"
              disabled={!roleName.trim()}
              loading={busy}
              onClick={() =>
                run(async () => {
                  await createCustomRole({ name: roleName.trim(), base_role: baseRole });
                  setRoleName("");
                })
              }
            >
              Créer le rôle
            </Button>
          </div>
        )}
      </div>

      {error && <p className="text-[12.5px] text-danger">{error}</p>}
      <p className="text-[11.5px] text-text-faint">
        Les accès sont contrôlés par le serveur, pas seulement masqués à l&rsquo;écran. Une personne ne voit que les données de votre entreprise.
      </p>
    </div>
  );
}
