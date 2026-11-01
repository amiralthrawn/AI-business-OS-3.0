"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import Button from "@/components/ui/Button";
import { type CalendarItem, type CalendarResponse, createCalendarEvent, deleteCalendarEvent, getCalendar } from "@/lib/api";

const GROUPS: { key: CalendarItem["group"]; label: string; dot: string }[] = [
  { key: "money", label: "Ventes, achats, paiements", dot: "bg-accent" },
  { key: "operations", label: "Livraisons, échéances, relances", dot: "bg-warning" },
  { key: "ai", label: "Détecté par l'IA", dot: "bg-danger" },
  { key: "mine", label: "Mes événements", dot: "bg-success" },
];
const MANUAL = [
  ["meeting", "Rendez-vous"],
  ["trade_show", "Salon / événement"],
  ["deadline", "Échéance"],
  ["other", "Autre"],
];
const MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"];
const DAYS = ["lun", "mar", "mer", "jeu", "ven", "sam", "dim"];
const eur = (n: number) => new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(n);
const pad = (n: number) => String(n).padStart(2, "0");
const dayKey = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
// Events are stored at midnight UTC for a whole day: read their date in UTC so it never shifts.
const eventDay = (e: CalendarItem) => (e.all_day ? e.at.slice(0, 10) : dayKey(new Date(e.at)));

const compact = (n: number) => new Intl.NumberFormat("fr-FR", { notation: "compact", maximumFractionDigits: 1 }).format(n) + " €";
function chip(e: CalendarItem) {
  return (e.kind === "sale" || e.kind === "purchase") && e.amount !== null ? `${e.kind_label} ${compact(e.amount)}` : e.title;
}

function href(e: CalendarItem): string | null {
  if (!e.entity_id) return null;
  if (e.entity_type === "risk") return `/intelligence/risks/${e.entity_id}`;
  if (e.entity_type === "opportunity") return `/intelligence/opportunities/${e.entity_id}`;
  if (e.entity_type === "commercial_document") return `/documents/${e.entity_id}`;
  if (e.entity_type === "task") return "/actions/tasks";
  if (e.entity_type === "transaction") return "/data/transactions";
  return null;
}

export default function CalendarView() {
  const today = useMemo(() => new Date(), []);
  const [cursor, setCursor] = useState(() => new Date(today.getFullYear(), today.getMonth(), 1));
  const [data, setData] = useState<CalendarResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState<string>(dayKey(today));
  const [adding, setAdding] = useState(false);

  // The grid always shows 6 weeks starting on a Monday.
  const gridStart = useMemo(() => {
    const first = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
    const offset = (first.getDay() + 6) % 7;
    return new Date(first.getFullYear(), first.getMonth(), 1 - offset);
  }, [cursor]);
  const days = useMemo(() => Array.from({ length: 42 }, (_, i) => new Date(gridStart.getFullYear(), gridStart.getMonth(), gridStart.getDate() + i)), [gridStart]);

  const load = useCallback(async () => {
    const end = new Date(gridStart.getFullYear(), gridStart.getMonth(), gridStart.getDate() + 42);
    try {
      setError(null);
      setData(await getCalendar(`${dayKey(gridStart)}T00:00:00Z`, `${dayKey(end)}T00:00:00Z`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Calendrier indisponible");
    }
  }, [gridStart]);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  const byDay = useMemo(() => {
    const map = new Map<string, CalendarItem[]>();
    for (const e of data?.events ?? []) {
      if (hidden.has(e.group)) continue;
      const k = eventDay(e);
      map.set(k, [...(map.get(k) ?? []), e]);
    }
    return map;
  }, [data, hidden]);
  const dot = (g: string) => GROUPS.find((x) => x.key === g)?.dot ?? "bg-text-faint";
  const chosen = byDay.get(selected) ?? [];
  const upcoming = (data?.events ?? []).filter((e) => e.period === "upcoming" && !hidden.has(e.group)).slice(0, 6);

  return (
    <div className="space-y-5">
      {error && <p className="text-[13px] text-danger">{error}</p>}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1.5">
          <Button variant="ghost" onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1))} aria-label="Mois précédent">←</Button>
          <span className="min-w-40 text-center font-display text-[20px] italic capitalize">{MONTHS[cursor.getMonth()]} {cursor.getFullYear()}</span>
          <Button variant="ghost" onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1))} aria-label="Mois suivant">→</Button>
          <Button variant="ghost" onClick={() => { setCursor(new Date(today.getFullYear(), today.getMonth(), 1)); setSelected(dayKey(today)); }}>Aujourd&rsquo;hui</Button>
        </div>
        <div className="ml-auto flex flex-wrap gap-2">
          {GROUPS.map((g) => (
            <button
              key={g.key}
              onClick={() => setHidden((h) => { const n = new Set(h); if (n.has(g.key)) n.delete(g.key); else n.add(g.key); return n; })}
              className={`flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[12px] font-semibold ${hidden.has(g.key) ? "border-border text-text-faint line-through" : "border-border-strong text-text"}`}
            >
              <span className={`h-2 w-2 rounded-full ${g.dot}`} />
              {g.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-[1fr_20rem]">
        <div className="overflow-hidden rounded-2xl border border-border bg-surface">
          <div className="grid grid-cols-7 border-b border-border bg-surface-sunken text-center text-[11px] font-bold uppercase tracking-wide text-text-faint">
            {DAYS.map((d) => (<div key={d} className="py-2">{d}</div>))}
          </div>
          <div className="grid grid-cols-7">
            {days.map((d) => {
              const k = dayKey(d);
              const evs = byDay.get(k) ?? [];
              const out = d.getMonth() !== cursor.getMonth();
              const groups = Array.from(new Set(evs.map((e) => e.group)));
              return (
                <button
                  key={k}
                  onClick={() => setSelected(k)}
                  className={`min-h-20 border-b border-r border-border p-1.5 text-left align-top transition-colors hover:bg-surface-sunken ${out ? "bg-surface-alt/60 text-text-faint" : ""} ${selected === k ? "ring-2 ring-inset ring-accent" : ""}`}
                >
                  <span className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-[12px] font-semibold ${k === dayKey(today) ? "bg-accent text-white" : ""}`}>{d.getDate()}</span>
                  {evs.length > 0 && (
                    <div className="mt-1 space-y-0.5">
                      {evs.slice(0, 2).map((e) => (
                        <p key={e.id} className={`truncate rounded px-1 text-[10.5px] ${e.period === "past" ? "bg-surface-sunken text-text-soft" : "bg-accent-soft text-accent-strong"}`}>{chip(e)}</p>
                      ))}
                      {evs.length > 2 && (
                        <span className="flex items-center gap-0.5 px-1 text-[10.5px] text-text-faint">
                          +{evs.length - 2} {groups.map((g) => (<span key={g} className={`h-1.5 w-1.5 rounded-full ${dot(g)}`} />))}
                        </span>
                      )}
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        <aside className="space-y-5">
          <section className="rounded-2xl border border-border bg-surface p-5">
            <div className="flex items-center justify-between">
              <p className="text-[14px] font-semibold capitalize">
                {new Date(`${selected}T12:00:00`).toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" })}
              </p>
              <button onClick={() => setAdding(true)} className="text-[12.5px] font-semibold text-accent-strong hover:underline">+ Ajouter</button>
            </div>
            {chosen.length === 0 && <p className="mt-3 text-[13px] text-text-soft">Rien ce jour-là.</p>}
            <ul className="mt-3 space-y-3">
              {chosen.map((e) => (
                <li key={e.id} className="text-[13px]">
                  <div className="flex items-start gap-2">
                    <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${dot(e.group)}`} />
                    <div className="min-w-0 flex-1">
                      <p className="font-semibold text-text">{e.title}</p>
                      <p className="text-[12px] text-text-faint">
                        {e.kind_label} · {e.period === "past" ? "passé" : "à venir"} · {e.source === "manual" ? "ajouté par vous" : e.source === "veilleur" ? "placé par le Veilleur" : "placé par l'IA"}
                      </p>
                      {e.detail && <p className="text-[12.5px] text-text-soft">{e.detail}</p>}
                      {e.amount !== null && e.count === 1 && <p className="text-[12.5px] text-text-soft">{eur(e.amount)}</p>}
                      <div className="mt-1 flex gap-3 text-[12px] font-semibold">
                        {href(e) && <Link href={href(e)!} className="text-accent-strong hover:underline">Ouvrir →</Link>}
                        {(e.source === "manual" || e.source === "veilleur") && (
                          <button className="text-danger hover:underline" onClick={async () => { await deleteCalendarEvent(e.id); load(); }}>Supprimer</button>
                        )}
                      </div>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
            {adding && <AddEvent day={selected} onClose={() => setAdding(false)} onSaved={() => { setAdding(false); load(); }} />}
          </section>

          <section className="rounded-2xl border border-border bg-surface p-5">
            <p className="text-[14px] font-semibold">À venir</p>
            {upcoming.length === 0 && <p className="mt-3 text-[13px] text-text-soft">Rien de prévu dans cette période. Les échéances, livraisons et relances apparaissent dès qu&rsquo;elles sont dans vos données.</p>}
            <ul className="mt-3 space-y-2">
              {upcoming.map((e) => (
                <li key={e.id}>
                  <button onClick={() => { setSelected(eventDay(e)); }} className="text-left text-[13px] hover:underline">
                    <span className="text-text-faint">{new Date(e.at).toLocaleDateString("fr-FR", { day: "numeric", month: "short" })} · </span>
                    {e.title}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        </aside>
      </div>
    </div>
  );
}

function AddEvent({ day, onClose, onSaved }: { day: string; onClose: () => void; onSaved: () => void }) {
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState("meeting");
  const [date, setDate] = useState(day);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  return (
    <form
      className="mt-4 space-y-2.5 border-t border-border pt-4"
      onSubmit={async (ev) => {
        ev.preventDefault();
        setBusy(true);
        try {
          await createCalendarEvent({ title, kind, starts_at: `${date}T00:00:00Z`, notes: notes || null });
          onSaved();
        } catch (e) {
          setErr(e instanceof Error ? e.message : "Échec");
          setBusy(false);
        }
      }}
    >
      <input required value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Titre (ex. Salon Electronica)" className="w-full rounded-lg border border-border-strong bg-surface px-3 py-2 text-[13px]" />
      <div className="flex gap-2">
        <select value={kind} onChange={(e) => setKind(e.target.value)} className="flex-1 rounded-lg border border-border-strong bg-surface px-2 py-2 text-[13px]">
          {MANUAL.map(([k, l]) => (<option key={k} value={k}>{l}</option>))}
        </select>
        <input type="date" required value={date} onChange={(e) => setDate(e.target.value)} className="rounded-lg border border-border-strong bg-surface px-2 py-2 text-[13px]" />
      </div>
      <input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Note (facultatif)" className="w-full rounded-lg border border-border-strong bg-surface px-3 py-2 text-[13px]" />
      {err && <p className="text-[12px] text-danger">{err}</p>}
      <div className="flex gap-2">
        <Button type="submit" loading={busy}>Enregistrer</Button>
        <Button type="button" variant="ghost" onClick={onClose}>Annuler</Button>
      </div>
    </form>
  );
}
