"use client";

import { useState } from "react";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import { type AgentsOverview, agentsCall } from "@/lib/api";

const ACTIONS: { key: string; label: string; hint: string }[] = [
  { key: "calendar_event", label: "Ajouter une date au calendrier", hint: "Salon, fête, échéance, jour férié trouvés par le Veilleur." },
  { key: "task", label: "Créer une tâche de suivi", hint: "Par exemple : demander des avis clients si votre note Google est basse." },
];
const STATUS: Record<string, string> = { ok: "À jour", not_configured: "Clé manquante", error: "Erreur" };

export default function AgentsPanel({ overview }: { overview: AgentsOverview }) {
  const [settings, setSettings] = useState(overview.settings ?? { enabled: true, autonomy: {} });
  const [agents, setAgents] = useState(overview.agents);
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  async function save(next: typeof settings) {
    setSettings(next);
    try {
      await agentsCall("/settings", "PUT", next);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Échec");
    }
  }
  async function run(key: string) {
    setBusy(key);
    setMsg(null);
    try {
      const res = await agentsCall<{ status: string; message: string }>(`/${key}/run`);
      setMsg(res.message);
      const fresh = await agentsCall<AgentsOverview>("/overview", "GET");
      setAgents(fresh.agents);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Échec");
    } finally {
      setBusy(null);
    }
  }

  return (
    <Card className="space-y-6 p-6">
      <div>
        <p className="text-[15px] font-semibold text-text">L&rsquo;IA qui travaille pour vous, 24h/24</p>
        <p className="mt-1 text-[13px] text-text-soft">
          Deux agents tournent en continu, plus souvent en journée (toutes les {overview.cadence_hours} h maintenant) et plus lentement la nuit. Leurs trouvailles arrivent sur l&rsquo;accueil et dans le calendrier.
        </p>
      </div>

      {agents.map((a) => (
        <div key={a.key} className="rounded-xl bg-surface-sunken p-4">
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-[14px] font-semibold text-text">{a.label}</p>
            <span className={`rounded-full px-2.5 py-0.5 text-[11.5px] font-semibold ${a.configured ? "bg-success-soft text-success" : "bg-warning-soft text-warning"}`}>
              {a.configured ? (a.last_status ? STATUS[a.last_status] ?? a.last_status : "Pas encore lancé") : "Clé Perplexity requise"}
            </span>
            <Button variant="ghost" loading={busy === a.key} onClick={() => run(a.key)} className="ml-auto" disabled={!a.configured}>Lancer maintenant</Button>
          </div>
          <p className="mt-1.5 text-[12.5px] text-text-soft">{a.description}</p>
          {a.last_message && <p className="mt-1 text-[12px] text-text-faint">Dernier passage : {a.last_message}{a.last_run_at ? ` · ${new Date(a.last_run_at).toLocaleString("fr-FR")}` : ""}</p>}
          {!a.configured && (
            <p className="mt-2 text-[12.5px] text-text-soft">
              Pour l&rsquo;activer : créez une clé sur perplexity.ai (API) puis ajoutez la ligne <code className="rounded bg-surface px-1">PERPLEXITY_API_KEY=votre_clé</code> dans le fichier <code className="rounded bg-surface px-1">.env</code> à la racine du projet, et relancez.
            </p>
          )}
        </div>
      ))}

      <div>
        <p className="text-[13.5px] font-semibold text-text">Que peut-il faire sans vous demander ?</p>
        <p className="mt-1 text-[12.5px] text-text-soft">Chaque action faite seule est signalée sur l&rsquo;accueil, avec un bouton Annuler. Les e-mails et messages ne partent jamais seuls : l&rsquo;IA les prépare, vous les validez.</p>
        <ul className="mt-3 space-y-3">
          {ACTIONS.map((a) => {
            const auto = settings.autonomy[a.key] === "auto";
            return (
              <li key={a.key} className="flex items-center gap-4">
                <div className="flex-1">
                  <p className="text-[13px] font-medium text-text">{a.label}</p>
                  <p className="text-[12px] text-text-faint">{a.hint}</p>
                </div>
                <div className="flex overflow-hidden rounded-lg border border-border-strong text-[12.5px] font-semibold">
                  <button onClick={() => save({ ...settings, autonomy: { ...settings.autonomy, [a.key]: "ask" } })} className={`px-3 py-1.5 ${!auto ? "bg-text text-surface" : "text-text-soft"}`}>Me demander</button>
                  <button onClick={() => save({ ...settings, autonomy: { ...settings.autonomy, [a.key]: "auto" } })} className={`px-3 py-1.5 ${auto ? "bg-text text-surface" : "text-text-soft"}`}>Agir seul</button>
                </div>
              </li>
            );
          })}
        </ul>
        <label className="mt-4 flex items-center gap-2 text-[12.5px] text-text-soft">
          <input type="checkbox" checked={settings.enabled} onChange={(e) => save({ ...settings, enabled: e.target.checked })} />
          Agents actifs en continu
        </label>
      </div>
      {msg && <p className="text-[12.5px] text-text-soft">{msg}</p>}
    </Card>
  );
}
