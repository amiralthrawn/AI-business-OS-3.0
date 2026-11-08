"use client";

import AIProgressDock from "@/components/layout/AIProgressDock";
import { useEffect, useRef, useState } from "react";
import MobileTabBar from "@/components/layout/MobileTabBar";
import Sidebar from "@/components/layout/Sidebar";
import Topbar from "@/components/layout/Topbar";
import { LocaleProvider } from "@/lib/i18n";
import type { MeRead, UserProfileRead } from "@/lib/types";

export default function AppShell({
  children,
  companyName,
  pendingCount,
  me,
  users,
}: {
  children: React.ReactNode;
  companyName: string | null;
  pendingCount: number;
  me: MeRead | null;
  users: UserProfileRead[];
}) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const scroller = useRef<HTMLDivElement>(null);
  const [showTop, setShowTop] = useState(false);
  useEffect(() => {
    const el = scroller.current;
    if (!el) return;
    const on = () => setShowTop(el.scrollTop > 700);
    el.addEventListener("scroll", on, { passive: true });
    return () => el.removeEventListener("scroll", on);
  }, []);

  return (
    <LocaleProvider>
      <div className="flex min-h-full">
        {mobileOpen && (
          <button
            aria-label="Fermer le menu"
            className="fixed inset-0 z-30 bg-text/30 md:hidden"
            onClick={() => setMobileOpen(false)}
          />
        )}
        <div
          className={`fixed inset-y-0 left-0 z-40 transform transition-transform duration-200 ease-out md:static md:translate-x-0 ${
            mobileOpen ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          <Sidebar companyName={companyName} permissions={me?.permissions ?? null} onNavigate={() => setMobileOpen(false)} />
        </div>
        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar companyName={companyName} pendingCount={pendingCount} me={me} users={users} onMenuClick={() => setMobileOpen(true)} />
          <div ref={scroller} className="min-w-0 flex-1 overflow-y-auto pb-[calc(70px+env(safe-area-inset-bottom))] md:pb-0">{children}</div>
          {showTop && (
            <button
              type="button"
              onClick={() => scroller.current?.scrollTo({ top: 0, behavior: "smooth" })}
              className="fixed bottom-[calc(80px+env(safe-area-inset-bottom))] left-3 z-30 rounded-full border border-border bg-surface px-3.5 py-2 text-[12.5px] font-semibold text-text-soft shadow-card hover:text-accent-strong md:bottom-5 md:left-[17rem]"
            >
              ↑ Haut de page
            </button>
          )}
          <AIProgressDock />
        </div>
      </div>
      <MobileTabBar permissions={me?.permissions ?? null} />
    </LocaleProvider>
  );
}
