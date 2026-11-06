"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { type LabelKey, useLocale } from "@/lib/i18n";

// Phone navigation: the four things people do every day, one thumb tap away
// at the bottom of the screen. The full menu stays behind the top-left button.
type Tab = { href: string; label: LabelKey; permission: string; match: string[]; icon: React.ReactNode };

const stroke = { fill: "none", stroke: "currentColor", strokeWidth: 1.9, strokeLinecap: "round", strokeLinejoin: "round" } as const;
const DATA_MATCH = ["/data", "/business", "/communications", "/people", "/intelligence", "/actions", "/direction", "/documents"];

const TABS: Tab[] = [
  { href: "/", label: "nav.decisions", permission: "", match: ["/"], icon: <svg width="22" height="22" viewBox="0 0 24 24" {...stroke}><path d="M4 12.5 12 5l8 7.5" /><path d="M6.5 11v8h11v-8" /></svg> },
  { href: "/data", label: "nav.data_group", permission: "", match: DATA_MATCH, icon: <svg width="22" height="22" viewBox="0 0 24 24" {...stroke}><ellipse cx="12" cy="6" rx="7" ry="3" /><path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6" /><path d="M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" /></svg> },
  { href: "/calendar", label: "nav.calendar", permission: "", match: ["/calendar"], icon: <svg width="22" height="22" viewBox="0 0 24 24" {...stroke}><rect x="4" y="5.5" width="16" height="14" rx="2" /><path d="M8 3.5v4M16 3.5v4M4 10h16" /></svg> },
  { href: "/ai/ask-ai", label: "nav.ask_ai", permission: "action:ask_ai", match: ["/ai"], icon: <svg width="22" height="22" viewBox="0 0 24 24" {...stroke}><path d="M5 6.5A2.5 2.5 0 0 1 7.5 4h9A2.5 2.5 0 0 1 19 6.5v7a2.5 2.5 0 0 1-2.5 2.5H11l-4 3.5V16h-.5A1.5 1.5 0 0 1 5 14.5Z" /></svg> },
  { href: "/agents", label: "nav.agents", permission: "", match: ["/agents"], icon: <svg width="22" height="22" viewBox="0 0 24 24" {...stroke}><rect x="5" y="8" width="14" height="10" rx="3" /><path d="M12 8V5M9.5 12.5h.01M14.5 12.5h.01M9.5 15.5h5" /></svg> },
];

export default function MobileTabBar({ permissions }: { permissions: string[] | null }) {
  const pathname = usePathname();
  const { t } = useLocale();
  const visible = TABS.filter((tab) => !tab.permission || permissions === null || permissions.includes(tab.permission));
  const matches = (prefix: string) => (prefix === "/" ? pathname === "/" : pathname === prefix || pathname.startsWith(`${prefix}/`));
  const active = visible
    .map((tab) => ({ href: tab.href, score: Math.max(-1, ...tab.match.filter(matches).map((m) => m.length)) }))
    .filter((x) => x.score >= 0)
    .sort((a, b) => b.score - a.score)[0]?.href;

  return (
    <nav aria-label="Navigation principale" className="fixed inset-x-0 bottom-0 z-20 border-t border-border bg-surface/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden">
      <ul className="mx-auto flex max-w-xl">
        {visible.map((tab) => {
          const on = tab.href === active;
          return (
            <li key={tab.href} className="min-w-0 flex-1">
              <Link href={tab.href} className={`flex h-[58px] flex-col items-center justify-center gap-0.5 px-1 text-[10.5px] font-semibold ${on ? "text-accent-strong" : "text-text-faint"}`}>
                {tab.icon}
                <span className="max-w-full truncate">{t(tab.label)}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
