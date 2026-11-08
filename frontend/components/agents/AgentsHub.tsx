"use client";

import DirecteurPanel from "@/components/agents/DirecteurPanel";
import Link from "next/link";
import { useEffect, useState } from "react";
import BrowserPanel from "@/components/agents/BrowserPanel";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import { type AgentsOverview, type AgentsUsage, agentsCall, askToolGuide, getIntegrationPlan } from "@/lib/api";

type Agent = AgentsOverview["agents"][number];
type ModelRequest = NonNullable<AgentsOverview["model_requests"]>[number];

const STATUS: Record<string, string> = { ok: "Terminé", no_sources: "Rien de fiable trouvé", not_configured: "Clé manquante", error: "Erreur" };
const MODEL_CHOICES: Record<string, string[]> = {
  veilleur: ["Perplexity Sonar Pro", "Perplexity Sonar", "Google Gemini", "Un autre modèle (précisez)"],
  guide: ["Perplexity Sonar Pro", "Perplexity Sonar", "Google Gemini", "Un autre modèle (précisez)"],
  analyste: ["Ajouter un modèle de langage (Claude, GPT…)", "Un autre modèle (précisez)"],
  directeur: ["Un modèle plus puissant pour mieux piloter", "Un modèle moins cher", "Un autre modèle (précisez)"],
  navigateur: ["Un modèle plus puissant pour les sites difficiles", "Un modèle moins cher", "Un autre modèle (précisez)"],
  executant: ["Un modèle plus puissant pour les tâches complexes", "Un modèle moins cher", "Un autre modèle (précisez)"],
};
const fmtNum = (n: number) => new Intl.NumberFormat("fr-FR").format(n);
const fmtUsd = (n: number) => `${n < 1 ? n.toFixed(n < 0.1 ? 4 : 3) : n.toFixed(2)} $`.replace(".", ",");
const fmtDate = (iso: string) => new Date(iso).toLocaleString("fr-FR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

// The three agents in one place: what powers each, its latest tasks, a direct
// way to ask each one something, and a request to change its model.
export default function AgentsHub({ overview, browserGoal }: { overview: AgentsOverview; browserGoal?: string }) {
  const [agents, setAgents] = useState(overview.agents);
  const [usage, setUsage] = useState(overview.usage ?? null);
  const [requests, setRequests] = useState<ModelRequest[]>(overview.model_requests ?? []);

  async function refresh() {
    const fresh = await agentsCall<AgentsOverview>("/overview", "GET");
    setAgents(fresh.agents);
    setRequests(fresh.model_requests ?? []);
    setUsage(fresh.usage ?? null);
  }

  return (
    <div className="space-y-6">
      {usage && <UsagePanel usage={usage} agents={agents} />}
      {agents.map((a) => (
        <AgentCard key={a.key} browserGoal={browserGoal} agent={a} usage={usage?.agents[a.key]} catalog={usage?.catalog ?? []} requests={requests.filter((r) => r.agent === a.key)} onChanged={refresh} />
      ))}
      <p className="text-center text-[12.5px] text-text-faint">
        Les réglages (agir seul ou demander, sujets suivis, activation) sont dans{" "}
        <Link href="/settings#agents" className="font-semibold text-accent-strong hover:underline">Configuration → Agents</Link>. L&rsquo;assistant « Demander à l&rsquo;IA » ne répond qu&rsquo;aux questions sur vos données.
      </p>
    </div>
  );
}

function AgentCard({ agent, requests, usage, catalog, onChanged, browserGoal }: { browserGoal?: string; agent: Agent; requests: ModelRequest[]; usage?: AgentsUsage["agents"][string]; catalog: AgentsUsage["catalog"]; onChanged: () => Promise<void> }) {
  const last = agent.recent_runs?.[0];
  const [showRuns, setShowRuns] = useState(false);
  return (
    <Card className="space-y-5 p-4 sm:p-6">
      <div className="flex flex-wrap items-start gap-x-3 gap-y-1">
        <h2 className="font-display text-[22px] italic">{agent.label}</h2>
        <span className={`mt-1.5 rounded-full px-2.5 py-0.5 text-[11.5px] font-semibold ${agent.configured ? "bg-success-soft text-success" : "bg-warning-soft text-warning"}`}>
          {agent.configured ? "Actif" : "Clé de recherche requise"}
        </span>
      </div>
      <p className="-mt-3 text-[13.5px] text-text-soft">{agent.description}</p>

      <div className="rounded-xl bg-surface-sunken p-4 text-[13px]">
        <p className="text-[11.5px] font-bold uppercase tracking-wide text-text-faint">Modèle utilisé</p>
        <p className="mt-1 font-semibold text-text">
          {agent.model.provider ?? "Aucun"}
          {agent.model.model ? ` · ${agent.model.model}` : ""}
        </p>
        <p className="mt-0.5 text-text-soft">{agent.model.note}</p>
        {usage && usage.calls > 0 && (
          <p className="mt-2 text-[12.5px] text-text-soft">
            Consommation : <span className="font-semibold text-text">{fmtNum(usage.tokens_in + usage.tokens_out)} tokens</span> · {usage.calls} appel{usage.calls > 1 ? "s" : ""} · <span className="font-semibold text-text">{fmtUsd(usage.usd)}</span>
          </p>
        )}
        <ModelRequestForm agent={agent} catalog={catalog} onSent={onChanged} />
        {requests.length > 0 && (
          <ul className="mt-3 space-y-1.5 text-[12.5px]">
            {requests.slice(-3).reverse().map((r) => (
              <li key={r.id} className="rounded-lg bg-surface px-3 py-2 text-text-soft">
                <span className="font-semibold text-text">Demande : {r.wanted}</span> · {fmtDate(r.at)} ·{" "}
                <span className="font-semibold text-accent-strong">{r.status === "requested" ? "Reçue : nous la traitons sous 24 h" : r.status}</span>
                {r.reason ? <span className="block text-text-faint">{r.reason}</span> : null}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <p className="text-[11.5px] font-bold uppercase tracking-wide text-text-faint">Dernière tâche</p>
        {last ? (
          <p className="mt-1 text-[13.5px] text-text">
            {last.message ?? "—"}
            <span className="block text-[12px] text-text-faint">
              {STATUS[last.status] ?? last.status} · {fmtDate(last.at)}
            </span>
          </p>
        ) : (
          <p className="mt-1 text-[13px] text-text-faint">Aucune tâche pour le moment.</p>
        )}
        {(agent.recent_runs?.length ?? 0) > 1 && (
          <>
            <button type="button" onClick={() => setShowRuns((v) => !v)} className="mt-1.5 text-[12.5px] font-semibold text-accent-strong hover:underline">
              {showRuns ? "Masquer l'historique" : "Voir les dernières tâches"}
            </button>
            {showRuns && (
              <ul className="mt-2 space-y-1.5">
                {agent.recent_runs!.map((r, i) => (
                  <li key={i} className="rounded-lg border border-border px-3 py-2 text-[12.5px] text-text-soft">
                    {r.message ?? "—"} <span className="text-text-faint">· {STATUS[r.status] ?? r.status} · {fmtDate(r.at)}</span>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </div>

      <MemoryLine agent={agent} onChanged={onChanged} />
      {agent.key === "navigateur" ? <BrowserPanel initialGoal={browserGoal ?? ""} embedded /> : agent.key === "directeur" ? <DirecteurPanel onDone={onChanged} /> : <DirectRequest agent={agent} onDone={onChanged} />}
    </Card>
  );
}

function ModelRequestForm({ agent, catalog, onSent }: { agent: Agent; catalog: AgentsUsage["catalog"]; onSent: () => Promise<void> }) {
  const [open, setOpen] = useState(false);
  const priced = agent.key === "analyste" || agent.key === "executant" || agent.key === "navigateur" ? [] : catalog.map((m) => `${m.label} · ${fmtUsd(m.usd_per_m_in)} / ${fmtUsd(m.usd_per_m_out)} par million de tokens (entrée / sortie)${m.usd_per_request ? ` + ${fmtUsd(m.usd_per_request)} par recherche` : ""}`);
  const choices = priced.length ? [...priced, "Un autre modèle (précisez)"] : MODEL_CHOICES[agent.key] ?? ["Un autre modèle (précisez)"];
  const [choice, setChoice] = useState(choices[0]);
  const [detail, setDetail] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const other = choice.startsWith("Un autre");

  async function send() {
    setBusy(true);
    setError(null);
    try {
      await agentsCall("/model-requests", "POST", { agent: agent.key, wanted: other ? detail.trim() : detail.trim() ? `${choice} (${detail.trim()})` : choice, reason: reason.trim() || null });
      setOpen(false);
      setDetail("");
      setReason("");
      await onSent();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Demande impossible.");
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className="mt-3 rounded-full border-[1.5px] border-border-strong bg-surface px-4 py-2 text-[12.5px] font-semibold text-text-soft hover:border-accent hover:text-accent">
        Demander un changement de modèle
      </button>
    );
  }
  return (
    <div className="mt-3 space-y-2.5 rounded-xl bg-surface p-3.5">
      <label className="block text-[12px] font-semibold text-text-soft">
        Je voudrais
        <select value={choice} onChange={(e) => setChoice(e.target.value)} className="mt-1 w-full rounded-lg border-[1.5px] border-border-strong bg-surface px-3 py-2 text-[13px] text-text">
          {choices.map((c) => <option key={c}>{c}</option>)}
        </select>
      </label>
      <input value={detail} onChange={(e) => setDetail(e.target.value)} placeholder={other ? "Quel modèle ? (obligatoire)" : "Précision (facultatif)"} className="w-full rounded-lg border-[1.5px] border-border-strong bg-surface px-3 py-2 text-[13px]" />
      <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Pourquoi ? (facultatif) Ex. : résultats trop légers" className="w-full rounded-lg border-[1.5px] border-border-strong bg-surface px-3 py-2 text-[13px]" />
      {error && <p className="text-[12.5px] text-danger">{error}</p>}
      <div className="flex gap-2">
        <Button loading={busy} disabled={other && detail.trim().length < 2} onClick={() => void send()}>Envoyer la demande</Button>
        <Button variant="ghost" onClick={() => setOpen(false)}>Annuler</Button>
      </div>
      <p className="text-[11.5px] text-text-faint">Notre équipe reçoit votre demande et change ou améliore la solution IA pour vous, sous 24 h ou plus vite.</p>
    </div>
  );
}

function MemoryLine({ agent, onChanged }: { agent: Agent; onChanged: () => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const n = agent.memory_count ?? 0;
  return (
    <p className="text-[12.5px] text-text-soft">
      <span className="font-bold uppercase tracking-wide text-text-faint text-[11.5px]">Mémoire</span>{" "}
      {n === 0 ? "Rien de retenu pour l'instant." : `${n} échange${n > 1 ? "s" : ""} retenu${n > 1 ? "s" : ""} : l'agent s'en sert pour ses prochaines réponses.`}
      {n > 0 && (
        <button
          type="button"
          disabled={busy}
          onClick={async () => {
            if (!window.confirm("Effacer la mémoire de cet agent ?")) return;
            setBusy(true);
            try {
              await agentsCall(`/memory/${agent.key}`, "DELETE");
              await onChanged();
            } finally {
              setBusy(false);
            }
          }}
          className="ml-2 font-semibold text-accent-strong hover:underline"
        >
          Effacer
        </button>
      )}
    </p>
  );
}

type Found = { title: string; summary: string; why: string; sources: string[] };
type Used = { model: string; calls: number; tokens: number; usd: number };
type Done = { kind: string; label: string };
type Panel = { who: string; asked: string; text: string; found: Found[]; sources: string[]; used: Used[]; analysis?: string; done?: Done[] };

// Half-page sheet for an agent's answer: closes with the cross, the backdrop or Escape.
function ResponseSheet({ panel, onClose, children }: { panel: Panel; onClose: () => void; children?: React.ReactNode }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-black/30" onClick={onClose}>
      <div role="dialog" aria-label={`Réponse : ${panel.who}`} onClick={(e) => e.stopPropagation()} className="flex max-h-[60vh] w-full max-w-3xl flex-col rounded-t-2xl bg-surface shadow-2xl md:max-h-[55vh]">
        <div className="flex items-start justify-between gap-3 border-b border-border px-4 py-3 sm:px-6">
          <div className="min-w-0">
            <p className="font-display text-[18px] italic">{panel.who}</p>
            <p className="truncate text-[12px] text-text-faint">{panel.asked}</p>
          </div>
          <button type="button" onClick={onClose} aria-label="Fermer" className="shrink-0 rounded-full border border-border-strong px-3 py-1.5 text-[13px] font-semibold text-text-soft hover:border-accent">✕ Fermer</button>
        </div>
        <div className="space-y-3 overflow-y-auto px-4 py-4 pb-[max(1rem,env(safe-area-inset-bottom))] sm:px-6">
          <p className="whitespace-pre-wrap text-[14px] leading-relaxed text-text">{panel.text}</p>
          {panel.found.map((f, i) => (
            <div key={i} className="rounded-xl border border-border p-3.5 text-[13px]">
              <p className="font-semibold text-text">{f.title}</p>
              {f.summary && <p className="mt-1 text-text-soft">{f.summary}</p>}
              {f.why && <p className="mt-1 text-text-faint">Pourquoi c&rsquo;est utile : {f.why}</p>}
              <Sources urls={f.sources} />
            </div>
          ))}
          <Sources urls={panel.sources} />
          {panel.done && panel.done.length > 0 && (
            <div className="rounded-xl bg-surface-sunken p-3.5 text-[13px]">
              <p className="font-semibold text-text">Fait dans votre logiciel</p>
              <ul className="mt-1 list-disc space-y-0.5 pl-5 text-text-soft">{panel.done.map((d, i) => <li key={i}>{d.label}</li>)}</ul>
              <p className="mt-1.5 text-[12px] text-text-faint">Tout est annulable depuis « Ce que l&rsquo;IA a trouvé ou fait pour vous » sur la page Décisions.</p>
            </div>
          )}
          {children}
          {panel.used.length > 0 && (
            <p className="border-t border-border pt-2.5 text-[12px] text-text-faint">
              Modèles utilisés pour cette réponse : {panel.used.map((u) => `${u.model} (${u.calls} appel${u.calls > 1 ? "s" : ""}, ${fmtNum(u.tokens)} tokens, ${fmtUsd(u.usd)})`).join(" · ")}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function Sources({ urls }: { urls: string[] }) {
  if (urls.length === 0) return null;
  return (
    <p className="text-[12px]">
      {urls.map((u, j) => <a key={u} href={u} target="_blank" rel="noreferrer" className="mr-2 font-semibold text-accent-strong hover:underline">source {j + 1}</a>)}
    </p>
  );
}

function DirectRequest({ agent, onDone }: { agent: Agent; onDone: () => Promise<void> }) {
  const [text, setText] = useState("");
  const [follow, setFollow] = useState(true);
  const [tool, setTool] = useState("");
  const [tools, setTools] = useState<{ key: string; label: string }[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [panel, setPanel] = useState<Panel | null>(null);
  const [relay, setRelay] = useState("");
  const [relaying, setRelaying] = useState(false);

  useEffect(() => {
    if (agent.key !== "guide") return;
    getIntegrationPlan()
      .then((p) => {
        setTools(p.tools.map((t) => ({ key: t.key, label: t.label })));
        if (p.tools[0]) setTool(p.tools[0].key);
      })
      .catch(() => undefined);
  }, [agent.key]);

  async function run(job: () => Promise<Panel>) {
    setBusy(true);
    setError(null);
    try {
      setPanel(await job());
      await onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Échec");
    } finally {
      setBusy(false);
    }
  }

  async function veilleurAsk(request: string, followTopic: boolean, withAnalysis = false): Promise<Panel> {
    const r = await agentsCall<{ message: string; found: Found[]; used?: Used[]; shared_chars?: number }>("/veilleur/ask", "POST", { request, follow: followTopic, with_analysis: withAnalysis });
    const shared = r.shared_chars ? `(Analyse transmise : ${fmtNum(r.shared_chars)} caractères de votre analyse complète : risques, opportunités, ventes, achats, produits, stocks.)\n\n` : "";
    return { who: "Veilleur", asked: request, text: shared + r.message, found: r.found, sources: [], used: r.used ?? [] };
  }

  if (agent.key === "analyste") {
    return (
      <div>
        <p className="text-[11.5px] font-bold uppercase tracking-wide text-text-faint">Lui demander</p>
        <p className="mt-1 text-[12.5px] text-text-soft">L&rsquo;Analyste relit tous vos chiffres (ventes, achats, clients, produits) et résume ce qui a changé depuis la dernière analyse.</p>
        <Button
          className="mt-2.5"
          loading={busy}
          onClick={() =>
            void run(async () => {
              const r = await agentsCall<{ message: string; summary?: string; started?: boolean }>("/analyste/run");
              const summary = r.summary ?? r.message;
              if (r.started !== undefined && !r.summary) return { who: "Analyste", asked: "Analyse de vos données", text: summary, found: [], sources: [], used: [] };
              setRelay("Cherche sur le web et dans les sites utiles ce qui peut m'aider à traiter ces points.");
              return { who: "Analyste", asked: "Analyse de vos données", text: summary, found: [], sources: [], used: [], analysis: summary };
            })
          }
        >
          Lancer l&rsquo;analyse maintenant
        </Button>
        {error && <p className="mt-2 text-[13px] text-danger">{error}</p>}
        {panel && (
          <ResponseSheet panel={panel} onClose={() => setPanel(null)}>
            {panel.analysis && (
              <div className="rounded-xl bg-surface-sunken p-3.5">
                <p className="text-[12.5px] font-semibold text-text">Transmettre l&rsquo;analyse complète au Veilleur</p>
                <p className="mt-0.5 text-[12px] text-text-soft">Il reçoit l&rsquo;analyse détaillée (risques, opportunités, ventes, achats, produits, stocks), en priorité ce qui touche à votre consigne.</p>
                <textarea value={relay} onChange={(e) => setRelay(e.target.value)} rows={2} className="mt-2 w-full rounded-lg border-[1.5px] border-border-strong bg-surface px-3 py-2 text-[13px]" />
                <Button
                  className="mt-2"
                  loading={relaying}
                  disabled={relay.trim().length < 3}
                  onClick={async () => {
                    setRelaying(true);
                    setError(null);
                    try {
                      setPanel(await veilleurAsk(relay.trim(), false, true));
                      await onDone();
                    } catch (e) {
                      setError(e instanceof Error ? e.message : "Échec");
                    } finally {
                      setRelaying(false);
                    }
                  }}
                >
                  Transmettre l&rsquo;analyse au Veilleur
                </Button>
                {relaying && <p className="mt-2 text-[12.5px] text-text-faint">Le Veilleur travaille sur l&rsquo;analyse, cela peut prendre une minute…</p>}
                {error && <p className="mt-2 text-[12.5px] text-danger">{error}</p>}
              </div>
            )}
          </ResponseSheet>
        )}
      </div>
    );
  }

  if (agent.key === "executant") {
    return (
      <div>
        <p className="text-[11.5px] font-bold uppercase tracking-wide text-text-faint">Lui confier une tâche</p>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={3}
          placeholder="Ex. : Ajoute au catalogue les références STM32F4 et STM32F7, et prépare un e-mail de demande de prix à Acme Parts"
          className="mt-2 w-full rounded-xl border-[1.5px] border-border-strong bg-surface px-3.5 py-2.5 text-[13.5px] outline-none focus:border-accent"
        />
        <Button
          className="mt-2.5"
          loading={busy}
          disabled={busy || !agent.configured || text.trim().length < 3}
          onClick={() =>
            void run(async () => {
              const r = await agentsCall<{ message: string; done: Done[]; used?: Used[] }>("/executant/ask", "POST", { request: text.trim() });
              return { who: "Exécutant", asked: text.trim(), text: r.message, found: [], sources: [], used: r.used ?? [], done: r.done };
            })
          }
        >
          Faire exécuter
        </Button>
        {!agent.configured && <p className="mt-2 text-[12.5px] text-text-faint">Cet agent attend la clé OpenRouter (OPENROUTER_API_KEY).</p>}
        {busy && <p className="mt-2 text-[12.5px] text-text-faint">L&rsquo;Exécutant travaille, cela peut prendre une minute…</p>}
        {error && <p className="mt-2 text-[13px] text-danger">{error}</p>}
        {panel && <ResponseSheet panel={panel} onClose={() => setPanel(null)} />}
      </div>
    );
  }

  const disabled = busy || !agent.configured || text.trim().length < 3;
  return (
    <div>
      <p className="text-[11.5px] font-bold uppercase tracking-wide text-text-faint">Lui demander directement</p>
      {agent.key === "guide" && (
        <select value={tool} onChange={(e) => setTool(e.target.value)} className="mt-2 w-full rounded-xl border-[1.5px] border-border-strong bg-surface px-3.5 py-2.5 text-[13.5px]">
          {tools.length === 0 && <option value="">Aucun outil déclaré</option>}
          {tools.map((t) => <option key={t.key} value={t.key}>{t.label}</option>)}
        </select>
      )}
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={3}
        placeholder={agent.key === "veilleur" ? "Ex. : Surveille oemstrade.com, ses prix et ses stocks, et le salon Electronica à Munich" : "Ex. : où trouver l'export des clients ?"}
        className="mt-2 w-full rounded-xl border-[1.5px] border-border-strong bg-surface px-3.5 py-2.5 text-[13.5px] outline-none focus:border-accent"
      />
      {agent.key === "veilleur" && (
        <label className="mt-2 flex items-center gap-2 text-[12.5px] text-text-soft">
          <input type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} />
          Continuer à suivre ce sujet dans la durée
        </label>
      )}
      <Button
        className="mt-2.5"
        loading={busy}
        disabled={disabled || (agent.key === "guide" && !tool)}
        onClick={() =>
          void run(async () => {
            if (agent.key === "veilleur") return veilleurAsk(text.trim(), follow);
            const r = await askToolGuide(tool, text.trim());
            return { who: "Guide de connexion", asked: text.trim(), text: r.answer, found: [], sources: r.sources, used: (r as { used?: Used[] }).used ?? [] };
          })
        }
      >
        {agent.key === "veilleur" ? "Demander au Veilleur" : "Demander au Guide"}
      </Button>
      {!agent.configured && <p className="mt-2 text-[12.5px] text-text-faint">Cet agent attend une clé de recherche web (OPENROUTER_API_KEY) pour répondre.</p>}
      {busy && <p className="mt-2 text-[12.5px] text-text-faint">Recherche en cours, cela peut prendre une minute…</p>}
      {error && <p className="mt-2 text-[13px] text-danger">{error}</p>}
      {panel && <ResponseSheet panel={panel} onClose={() => setPanel(null)} />}
    </div>
  );
}

function UsagePanel({ usage, agents }: { usage: AgentsUsage; agents: Agent[] }) {
  return (
    <Card className="space-y-4 p-4 sm:p-6">
      <div>
        <h2 className="font-display text-[22px] italic">Consommation IA</h2>
        <p className="text-[13px] text-text-soft">Les tokens sont les « mots » lus et écrits par les modèles : c&rsquo;est ce qui est facturé. Les montants viennent du fournisseur quand il les donne, sinon du tarif public (indicatif).</p>
      </div>
      <div className="grid grid-cols-3 gap-3 text-center">
        <Stat label="Tokens au total" value={fmtNum(usage.total.tokens)} />
        <Stat label="Appels" value={fmtNum(usage.total.calls)} />
        <Stat label="Coût estimé" value={fmtUsd(usage.total.usd)} />
      </div>
      <ul className="divide-y divide-border text-[13px]">
        {agents.map((a) => {
          const u = usage.agents[a.key];
          return (
            <li key={a.key} className="py-2.5">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                <span className="font-semibold text-text">{a.label}</span>
                <span className="text-text-soft">
                  {u && u.calls > 0 ? `${fmtNum(u.tokens_in + u.tokens_out)} tokens · ${fmtUsd(u.usd)}` : a.key === "analyste" ? "Aucun token : calculs internes, 0 $" : "Aucune consommation"}
                </span>
              </div>
              {u?.models.map((m) => (
                <p key={m.model} className="text-[12px] text-text-faint">
                  {m.model} : {fmtNum(m.tin)} en entrée, {fmtNum(m.tout)} en sortie, {m.calls} appel{m.calls > 1 ? "s" : ""} → {fmtUsd(m.usd)}
                </p>
              ))}
            </li>
          );
        })}
      </ul>
      <p className="text-[11.5px] text-text-faint">Mise à jour à chaque tâche d&rsquo;un agent. La consommation de l&rsquo;assistant « Demander à l&rsquo;IA » n&rsquo;est pas comptée ici.</p>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-surface-sunken px-2 py-3">
      <p className="text-[18px] font-bold text-text">{value}</p>
      <p className="text-[11px] text-text-soft">{label}</p>
    </div>
  );
}
