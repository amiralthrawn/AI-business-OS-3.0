"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { AUTH_REQUIRED, setSelectedProfile, setSessionToken } from "@/lib/api";
import { useLocale } from "@/lib/i18n";
import { ROLE_LABEL } from "@/lib/objects";
import type { MeRead, UserProfileRead } from "@/lib/types";

// Who am I using the OS as. V3 (sign-in required): the signed-in person,
// with a link to the team settings and sign-out. Legacy demo mode (V2
// roles): selecting a profile stores its id in a cookie read by every API
// call (lib/api.ts) -- a declared profile, not an authentication
// (brain/permissions.md).
export default function ProfileSwitcher({ me, users, fallbackLabel }: { me: MeRead | null; users: UserProfileRead[]; fallbackLabel: string }) {
  const router = useRouter();
  const { t } = useLocale();
  const [open, setOpen] = useState(false);
  const name = me?.profile?.name ?? fallbackLabel;
  const initials = name
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  function signOut() {
    setSessionToken(null);
    window.location.assign("/login");
  }

  function choose(id: string | null) {
    setSelectedProfile(id);
    setOpen(false);
    router.refresh();
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 rounded-full"
        aria-label={t("topbar.profile")}
        title={me?.profile ? `${me.profile.name} · ${me.role_label}` : t("topbar.no_profile")}
      >
        <span className="flex h-[34px] w-[34px] items-center justify-center rounded-full bg-accent text-[12px] font-semibold text-white">{initials || "OS"}</span>
        <span className="hidden text-left leading-tight lg:block">
          <span className="block text-[12.5px] font-semibold text-text">{me?.profile?.name ?? t("topbar.profile")}</span>
          <span className="block text-[11px] text-text-faint">{me?.profile ? (me.profile.custom_role_name ?? me.role_label) : t("topbar.no_profile")}</span>
        </span>
      </button>
      {open && AUTH_REQUIRED && (
        <div className="animate-pop absolute right-0 z-50 mt-2 w-64 rounded-xl border border-border bg-surface p-1.5 shadow-card">
          <div className="px-3 py-2">
            <p className="truncate text-[13px] font-semibold text-text">{me?.profile?.name}</p>
            <p className="truncate text-[11.5px] text-text-faint">{me?.profile?.email}</p>
          </div>
          <a href="/settings#profils" className="block rounded-lg px-3 py-2 text-[12.5px] text-accent-strong hover:bg-surface-sunken">
            Équipe et accès
          </a>
          <button type="button" onClick={signOut} className="w-full rounded-lg px-3 py-2 text-left text-[12.5px] text-text-soft hover:bg-surface-sunken">
            Se déconnecter
          </button>
        </div>
      )}
      {open && !AUTH_REQUIRED && (
        <div className="animate-pop absolute right-0 z-50 mt-2 w-64 rounded-xl border border-border bg-surface p-1.5 shadow-card">
          {users.map((u) => (
            <button
              key={u.id}
              type="button"
              onClick={() => choose(u.id)}
              className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-[13px] hover:bg-surface-sunken ${me?.profile?.id === u.id ? "font-semibold text-accent-strong" : "text-text"}`}
            >
              <span className="truncate">{u.name}</span>
              <span className="text-[11.5px] text-text-faint">{ROLE_LABEL[u.role]}</span>
            </button>
          ))}
          <button type="button" onClick={() => choose(null)} className="mt-1 w-full rounded-lg px-3 py-2 text-left text-[12.5px] text-text-soft hover:bg-surface-sunken">
            {t("topbar.no_profile")}
          </button>
          <a href="/settings#profils" className="block rounded-lg px-3 py-2 text-[12.5px] text-accent-strong hover:bg-surface-sunken">
            Gérer les profils et rôles
          </a>
        </div>
      )}
    </div>
  );
}
