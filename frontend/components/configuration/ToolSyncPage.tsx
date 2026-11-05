"use client";

import { useEffect, useRef, useState } from "react";
import { addToolReminder, askToolGuide, getIntegrationPlan, getToolGuide, getToolNextSteps, importAuto, requestToolConnection } from "@/lib/api";
import type { GuideAnswer, ImportKind, ImportResultRead, IntegrationItem, NextSteps, ToolGuide } from "@/lib/types-config";

const KIND_LABEL: Record<ImportKind, string> = {
  fec: "écritures comptables",
  customers: "clients",
  suppliers: "fournisseurs",
  products: "produits",
  sales: "ventes",
  purchases: "achats",
};
const fmt = (n: number) => new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 }).format(n);

type Outcome = { file: string; result?: ImportResultRead; error?: string };

// One full page per declared tool: what lives in it, what the AI does with it,
// and how to bring it in. Files are read for real; a direct connection is
// requested (we set it up with the company) and never shown as connected.
export default function ToolSyncPage({ toolKey, label, onRemove }: { toolKey: string; label: string; onRemove?: () => void }) {
  const [item, setItem] = useState<IntegrationItem | null>(null);
  const [outcomes, setOutcomes] = useState<Outcome[]>([]);
  const [busy, setBusy] = useState(false);
  const [over, setOver] = useState(false);
  const [asked, setAsked] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const picker = useRef<HTMLInputElement>(null);
  const [guide, setGuide] = useState<ToolGuide | null>(null);
  const [guideLoading, setGuideLoading] = useState(true);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<GuideAnswer | null>(null);
  const [asking, setAsking] = useState(false);
  const [next, setNext] = useState<NextSteps | null>(null);
  const [reminded, setReminded] = useState(false);

  async function load() {
    try {
      const plan = await getIntegrationPlan();
      const found = plan.tools.find((t) => t.key === toolKey) ?? null;
      setItem(found);
      if (found?.connection === "requested") setAsked(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chargement impossible.");
    }
  }
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [toolKey]);

  useEffect(() => {
    let live = true;
    getToolGuide(toolKey)
      .then((g) => live && setGuide(g))
      .catch(() => live && setGuide(null))
      .finally(() => live && setGuideLoading(false));
    return () => { live = false; };
  }, [toolKey]);

  async function refreshNext() {
    try { setNext(await getToolNextSteps(toolKey)); } catch { /* the page works without it */ }
  }
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refreshNext();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [toolKey]);

  async function ask() {
    if (question.trim().length < 2) return;
    setAsking(true);
    try { setAnswer(await askToolGuide(toolKey, question.trim())); } catch (err) { setError(err instanceof Error ? err.message : "Question impossible."); }
    setAsking(false);
  }

  async function remind() {
    try { await addToolReminder(toolKey); setReminded(true); } catch (err) { setError(err instanceof Error ? err.message : "Rappel impossible."); }
  }

  async function upload(files: FileList | File[]) {
    setBusy(true);
    const done: Outcome[] = [...outcomes];
    for (const file of Array.from(files)) {
      try {
        done.push({ file: file.name, result: await importAuto(file, toolKey) });
      } catch (err) {
        done.push({ file: file.name, error: err instanceof Error ? err.message : "Import impossible." });
      }
      setOutcomes([...done]);
    }
    setBusy(false);
    await load();
    await refreshNext();
  }

  async function askConnection() {
    try {
      await requestToolConnection(toolKey);
      setAsked(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Demande impossible.");
    }
  }

  const synced = outcomes.some((o) => o.result) || item?.status === "imported";
  const received = outcomes.filter((o) => o.result);

  return (
    <div>
      <p className="mt-3 text-[12px] font-semibold text-text-faint">Synchronisation</p>
      <div className="mt-6 flex items-center gap-5">
        <div className={`flex h-[64px] w-[64px] shrink-0 items-center justify-center rounded-[18px] font-display text-[30px] font-semibold text-white transition-colors ${synced ? "bg-success" : "bg-accent"}`}>
          {synced ? (
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
          ) : (
            label.charAt(0).toUpperCase()
          )}
        </div>
        <h1 className="font-display text-[36px] italic leading-tight md:text-[42px]">{synced ? `${label} est synchronisé` : `Synchronisons ${label}`}</h1>
      </div>
      {error && <p className="mt-4 text-[13px] text-danger">{error}</p>}
      {!item && !error && <p className="mt-6 text-[13px] text-text-faint">Chargement…</p>}

      {item && (
        <>
          <p className="mt-6 max-w-xl text-[16px] leading-relaxed text-text-soft">{item.ai_use}</p>

          <div className="mt-6 flex flex-wrap gap-2">
            {item.data.map((d) => (
              <span key={d} className="rounded-full bg-surface-sunken px-3.5 py-1.5 text-[12.5px] font-medium text-text-soft">{d}</span>
            ))}
          </div>

          <div className="mt-9 rounded-2xl border border-border p-6">
            <p className="text-[12px] font-bold uppercase tracking-wide text-accent-strong">Récupérer vos données</p>
            <p className="mt-2 text-[14px] font-semibold text-text">1. Exportez-les depuis {label}.</p>
            {guideLoading && <p className="mt-2 text-[13px] text-text-faint">Je cherche la procédure de {label} dans sa documentation…</p>}
            {!guideLoading && guide?.status === "sourced" && (
              <div className="mt-3 rounded-xl bg-surface-sunken p-4">
                <ol className="space-y-2.5">
                  {guide.steps.map((s, i) => (
                    <li key={i} className="flex gap-3 text-[13.5px] text-text-soft">
                      <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-accent text-[11px] font-bold text-white">{i + 1}</span>
                      <span><span className="font-semibold text-text">{s.title}</span>{s.title && s.detail ? " : " : ""}{s.detail}</span>
                    </li>
                  ))}
                </ol>
                {guide.caveats && <p className="mt-3 text-[12.5px] text-text-soft">À savoir : {guide.caveats}</p>}
                <p className="mt-3 text-[12px] text-text-faint">
                  Procédure trouvée dans la documentation :{" "}
                  {guide.sources.map((u, i) => (
                    <a key={u} href={u} target="_blank" rel="noreferrer" className="mr-2 font-semibold text-accent-strong hover:underline">source {i + 1}</a>
                  ))}
                </p>
              </div>
            )}
            {!guideLoading && guide?.status !== "sourced" && (
              <div className="mt-3 rounded-xl bg-surface-sunken p-4 text-[13.5px] text-text-soft">
                <p className="font-semibold text-text">
                  {guide?.status === "no_sources" ? `Je n'ai pas trouvé de procédure fiable pour ${label}, donc je ne vous en invente pas.` : "La recherche de procédure n'est pas disponible pour le moment."}
                </p>
                {guide?.status === "unavailable" && guide.reason && (
                  <p className="mt-1.5 text-[12.5px] text-text-faint">
                    Raison technique : {guide.reason === "not_configured" ? "la clé PERPLEXITY_API_KEY n'est pas lue par le serveur (API)." : guide.reason}
                  </p>
                )}
                <p className="mt-1.5">Instructions générales, non vérifiées pour {label} : {item.export_help}</p>
              </div>
            )}
            <div className="mt-3">
              <p className="text-[12.5px] font-semibold text-text-faint">Une question, un blocage ?</p>
              <div className="mt-1.5 flex gap-2">
                <input
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") void ask(); }}
                  placeholder={`Ex. : je ne trouve pas l'export dans ${label}`}
                  className="min-w-0 flex-1 rounded-xl border-[1.5px] border-border-strong bg-surface px-3.5 py-2 text-[13.5px] outline-none focus:border-accent"
                />
                <button type="button" disabled={asking} onClick={() => void ask()} className="rounded-full bg-text px-5 py-2 text-[13px] font-semibold text-surface hover:bg-text/90 disabled:opacity-50">
                  {asking ? "Recherche…" : "Demander"}
                </button>
              </div>
              {answer && (
                <div className="mt-2.5 rounded-xl border border-border p-3.5 text-[13.5px] text-text-soft">
                  <p className="whitespace-pre-line">{answer.answer}</p>
                  {answer.sources.length > 0 && (
                    <p className="mt-2 text-[12px] text-text-faint">
                      {answer.sources.map((u, i) => (
                        <a key={u} href={u} target="_blank" rel="noreferrer" className="mr-2 font-semibold text-accent-strong hover:underline">source {i + 1}</a>
                      ))}
                    </p>
                  )}
                </div>
              )}
            </div>
            <p className="mt-2 text-[14px] font-semibold text-text">2. Déposez le fichier ici.</p>

            <div
              onDragOver={(e) => { e.preventDefault(); setOver(true); }}
              onDragLeave={() => setOver(false)}
              onDrop={(e) => { e.preventDefault(); setOver(false); if (e.dataTransfer.files.length) void upload(e.dataTransfer.files); }}
              className={`mt-3 rounded-2xl border-2 border-dashed px-6 py-10 text-center transition-colors ${over ? "border-accent bg-accent-soft" : "border-border-strong bg-surface-sunken"}`}
            >
              <input
                ref={picker}
                type="file"
                multiple
                className="hidden"
                accept=".csv,.xlsx,.xlsm,.txt,.fec,text/csv,text/plain"
                onChange={(e) => { if (e.target.files?.length) void upload(e.target.files); e.target.value = ""; }}
              />
              <p className="text-[14px] text-text-soft">{busy ? "Lecture en cours…" : "Glissez vos fichiers ici, ou"}</p>
              <button type="button" disabled={busy} onClick={() => picker.current?.click()} className="mt-3 rounded-full bg-text px-6 py-2.5 text-[13.5px] font-semibold text-surface hover:bg-text/90 disabled:opacity-50">
                Choisir des fichiers
              </button>
            </div>

            {received.length > 0 && (
              <ul className="mt-4 space-y-2">
                {received.map((o, i) => (
                  <li key={`${o.file}-${i}`} className="rounded-xl bg-success/10 px-4 py-3 text-[13px] text-text">
                    <span className="font-semibold">{o.file}</span> : {KIND_LABEL[o.result!.kind]} reconnues ·{" "}
                    <span className="font-semibold text-success">{fmt(o.result!.created)} ajouté{o.result!.created > 1 ? "s" : ""}</span>
                    {o.result!.updated > 0 && ` · ${fmt(o.result!.updated)} mis à jour`}
                    {o.result!.skipped > 0 && ` · ${fmt(o.result!.skipped)} ignoré${o.result!.skipped > 1 ? "s" : ""}`}
                    {o.result!.summary && ` · chiffre d'affaires lu : ${fmt(o.result!.summary.revenue)} €`}
                  </li>
                ))}
              </ul>
            )}
            {outcomes.filter((o) => o.error).map((o, i) => (
              <p key={i} className="mt-3 text-[13px] text-danger"><span className="font-semibold">{o.file}</span> : {o.error}</p>
            ))}
          </div>

          {next && (next.notes.length > 0 || next.suggestions.length > 0) && next.imported_kinds.length > 0 && (
            <div className="mt-5 rounded-2xl border border-accent/40 bg-accent-soft p-6">
              <p className="text-[12px] font-bold uppercase tracking-wide text-accent-strong">Et maintenant ?</p>
              {next.notes.map((n) => <p key={n} className="mt-2 text-[13.5px] text-text">{n}</p>)}
              <div className="mt-3 flex flex-wrap gap-2">
                {next.suggestions.map((sg) => {
                  if (sg.action === "reminder" && reminded) return <span key="r" className="px-1 py-2 text-[13px] font-semibold text-success">Rappel ajouté au calendrier.</span>;
                  if (sg.action === "request_connection" && asked) return null;
                  const run = sg.action === "upload" ? () => picker.current?.click() : sg.action === "reminder" ? () => void remind() : () => void askConnection();
                  return (
                    <button key={`${sg.action}-${sg.kind ?? ""}`} type="button" onClick={run} className="rounded-full border-[1.5px] border-border-strong bg-surface px-4 py-2 text-[13px] font-semibold text-text hover:border-accent hover:text-accent">
                      {sg.text}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          <div className="mt-5 rounded-2xl border border-border p-6">
            <p className="text-[12px] font-bold uppercase tracking-wide text-text-faint">Connexion directe</p>
            <p className="mt-2 text-[13.5px] text-text-soft">
              Pour que {label} se synchronise seul, sans fichier : {item.direct_methods.join(" ou ")}. Elle se fait en lecture seule, avec l&rsquo;accord de votre administrateur, et nous la mettons en place avec vous.
            </p>
            {asked ? (
              <p className="mt-3 text-[13px] font-semibold text-success">Demande enregistrée : nous reviendrons vers vous pour connecter {label}.</p>
            ) : (
              <button type="button" onClick={() => void askConnection()} className="mt-3 rounded-full border-[1.5px] border-border-strong px-5 py-2 text-[13px] font-semibold text-text-soft hover:border-accent hover:text-accent">
                Je veux qu&rsquo;on connecte {label} pour moi
              </button>
            )}
          </div>
          {onRemove && (
            <button type="button" onClick={onRemove} className="mt-5 text-[12.5px] text-text-faint hover:text-text-soft hover:underline">
              Je n&rsquo;utilise finalement pas {label}
            </button>
          )}
        </>
      )}
    </div>
  );
}
