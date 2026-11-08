"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { type ActivityItem, type ActivityState, dismissActivity, getActivity } from "@/lib/api";
import Card from "@/components/ui/Card";

const LABEL: Record<ActivityItem["status"], { text: string; cls: string }> = {
  in_progress: { text: "En cours", cls: "bg-accent-soft text-accent-strong" },
  stopped: { text: "Arrêtée", cls: "bg-danger-soft text-danger" },
  done: { text: "Terminée", cls: "bg-success-soft text-success" },
};

// What the AI started for you: in progress, stopped, finished. What was left
// unfinished stays here, in the decisions, until it is done or you drop it.
export default function ActivityPanel() {
  const [data, setData] = useState<ActivityState | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let alive = true;
    const load = () => getActivity().then((d) => alive && setData(d)).catch(() => undefined);
    void load();
    const timer = setInterval(load, 15000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);

  if (!data || data.items.length === 0) return null;
  const drop = (key: string) => dismissActivity(key).then(setData).catch(() => undefined);

  return (
    <section className="space-y-3">
      {data.unfinished.map((u) => (
        <Card key={u.key} className="border-l-4 border-l-accent p-4 sm:p-5">
          <p className="text-[13.5px] font-semibold text-text">Vous aviez commencé : {u.title}</p>
          <p className="mt-0.5 text-[12.5px] text-text-soft">Ce n&rsquo;est pas terminé. Voulez-vous le faire maintenant ?</p>
          <div className="mt-3 flex flex-wrap items-center gap-4">
            {u.href && <Link href={u.href} className="rounded-full bg-accent px-4 py-1.5 text-[13px] font-semibold text-white hover:opacity-90">Reprendre</Link>}
            <button type="button" onClick={() => void drop(u.key)} className="text-[13px] font-semibold text-text-soft hover:text-text">Plus maintenant</button>
          </div>
        </Card>
      ))}
      <div>
        <button type="button" onClick={() => setOpen(!open)} className="text-[12.5px] font-semibold text-accent-strong hover:underline">
          {open ? "Masquer" : "Voir"} les tâches de l&rsquo;IA ({data.items.filter((i) => i.status === "in_progress").length} en cours, {data.items.filter((i) => i.status === "stopped").length} arrêtée(s), {data.items.filter((i) => i.status === "done").length} terminée(s))
        </button>
        {open && (
          <ul className="mt-2 space-y-1.5">
            {data.items.map((i) => (
              <li key={i.key} className="flex items-center justify-between gap-3 rounded-xl border border-border px-3.5 py-2 text-[13px]">
                <span className="min-w-0 truncate text-text">{i.title}</span>
                <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-[11.5px] font-semibold ${LABEL[i.status].cls}`}>{LABEL[i.status].text}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
