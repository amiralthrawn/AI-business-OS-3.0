import type { AgentsOverview } from "@/lib/api";

function ago(iso: string | null): string {
  if (!iso) return "pas encore";
  const min = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (min < 2) return "à l'instant";
  if (min < 60) return `il y a ${min} min`;
  if (min < 1440) return `il y a ${Math.round(min / 60)} h`;
  return `il y a ${Math.round(min / 1440)} j`;
}

// The product is alive: what each AI did last, and that they keep going.
export default function LivePulse({ agents, open }: { agents: AgentsOverview["agents"]; open: number }) {
  const working = agents.filter((a) => a.configured && ["directeur", "veilleur", "analyste", "guide"].includes(a.key));
  if (working.length === 0) return null;
  return (
    <section className="rounded-[20px] border border-border bg-surface p-5 shadow-card">
      <div className="flex items-center gap-2.5">
        <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-success" />
        <p className="text-[14px] font-semibold text-text">Votre IA travaille pour vous, en continu</p>
      </div>
      <ul className="mt-3 space-y-1.5 text-[13px] text-text-soft">
        {working.map((a) => (
          <li key={a.key}>
            <span className="font-semibold text-text">{a.label}</span> · dernière activité {ago(a.last_run_at)}
            {a.last_message ? ` — ${a.last_message.slice(0, 110)}` : ""}
          </li>
        ))}
      </ul>
      {open > 0 && <p className="mt-3 text-[12.5px] text-text-soft">{open} point{open > 1 ? "s" : ""} attendent votre avis plus bas : l&rsquo;IA s&rsquo;en sert pour mieux vous connaître.</p>}
    </section>
  );
}
