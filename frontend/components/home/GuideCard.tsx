"use client";

import Link from "next/link";
import { useState } from "react";
import ImportHelper from "@/components/home/ImportHelper";
import type { AgentsOverview } from "@/lib/api";

// "Your profile is 60 % complete": what is still missing for the product to
// work at full strength, and why each step matters.
export default function GuideCard({ guide }: { guide: NonNullable<AgentsOverview["guide"]> }) {
  const [helper, setHelper] = useState<string | null>(null);
  if (guide.percent >= 100) return null;
  const next = guide.steps.slice(0, 3);
  return (
    <section className="rounded-[20px] border border-border bg-surface p-6 shadow-card">
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-[14px] font-semibold text-text">Votre logiciel est configuré à {guide.percent} %</p>
        <span className="text-[12px] text-text-faint">{guide.steps.length} étape{guide.steps.length > 1 ? "s" : ""} restante{guide.steps.length > 1 ? "s" : ""}</span>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-surface-sunken">
        <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${guide.percent}%` }} />
      </div>
      <ul className="mt-4 space-y-3">
        {next.map((s) => (
          <li key={s.title} className="flex items-start gap-3">
            <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-accent" />
            <div className="min-w-0 flex-1">
              {s.import_kind ? (
                <button type="button" onClick={() => setHelper(s.import_kind ?? null)} className="text-left text-[13.5px] font-semibold text-text hover:text-accent-strong hover:underline">{s.title}</button>
              ) : (
                <Link href={s.href} className="text-[13.5px] font-semibold text-text hover:text-accent-strong hover:underline">{s.title}</Link>
              )}
              <p className="text-[12.5px] text-text-soft">{s.why}</p>
            </div>
          </li>
        ))}
      </ul>
      {helper && <ImportHelper kind={helper} onClose={() => setHelper(null)} />}
    </section>
  );
}
