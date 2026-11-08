"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import { integrateWebsite, requestWebsiteCreation } from "@/lib/api";
import type { SiteIntelligence } from "@/lib/types-v21";

const fmt = (iso?: string) => (iso ? new Date(iso).toLocaleDateString("fr-FR", { day: "numeric", month: "long" }) : "");

// Add the company's site, have the Analyste read it in depth, or ask us to build one.
export default function SiteIntegration({ websiteUrl, intelligence, compact = false }: { websiteUrl: string | null; intelligence?: SiteIntelligence | null; compact?: boolean }) {
  const router = useRouter();
  const [url, setUrl] = useState(websiteUrl ?? "");
  const [notes, setNotes] = useState("");
  const [noSite, setNoSite] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const a = intelligence?.analysis;
  const requested = intelligence?.request?.status === "requested";

  async function act(key: string, job: () => Promise<string | void>) {
    setBusy(key);
    setError(null);
    try {
      setDone((await job()) || null);
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Une erreur est survenue.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <Card className="space-y-4 p-4 sm:p-6">
      <div>
        <h2 className="font-display text-[22px] italic">Votre site web</h2>
        <p className="text-[13px] text-text-soft">
          {a ? `Lu par l\u2019Analyste le ${fmt(intelligence?.analysed_at)} (${intelligence?.pages?.length ?? 0} pages). Il le relit chaque semaine et ce qu\u2019il comprend est partagé avec les autres agents.` : "L\u2019Analyste lit votre site en profondeur pour comprendre votre métier, puis propose des améliorations et des synchronisations avec le logiciel."}
        </p>
      </div>

      {!noSite || websiteUrl ? (
        <div className="flex flex-wrap gap-2">
          <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="www.votre-entreprise.fr" className="min-w-0 flex-1 rounded-xl border-[1.5px] border-border-strong bg-surface px-3.5 py-2.5 text-[14px] outline-none focus:border-accent" />
          <Button
            loading={busy === "integrate"}
            disabled={busy !== null || url.trim().length < 4}
            onClick={() => act("integrate", async () => { const r = await integrateWebsite(url.trim()); return `${r.indirect ? "Votre site bloque les lectures automatiques : je l\u2019ai étudié via la recherche web (lecture indirecte, moins détaillée)." : `Site lu (${r.pages} page${r.pages > 1 ? "s" : ""}).`} ${r.created} proposition${r.created > 1 ? "s" : ""} ajoutée${r.created > 1 ? "s" : ""} aux décisions.`; })}
          >
            {a ? "Relire mon site" : "Intégrer et analyser mon site"}
          </Button>
        </div>
      ) : null}
      {busy === "integrate" && <p className="text-[12.5px] text-text-faint">L&rsquo;Analyste lit votre site, cela peut prendre une minute…</p>}
      {done && <p className="text-[13px] font-semibold text-success">{done}</p>}
      {error && <p className="text-[13px] text-danger">{error}</p>}

      {!websiteUrl && !a && (
        <div className="rounded-xl bg-surface-sunken p-3.5 text-[13px]">
          {requested ? (
            <p className="text-text-soft">Votre demande de création de site nous est bien parvenue ({fmt(intelligence?.request?.at)}). Nous revenons vers vous avec une proposition.</p>
          ) : !noSite ? (
            <button type="button" onClick={() => setNoSite(true)} className="font-semibold text-accent-strong hover:underline">Je n&rsquo;ai pas de site web</button>
          ) : (
            <div className="space-y-2">
              <p className="text-text-soft">Nous pouvons concevoir votre site à partir de votre activité et de vos produits (sur devis). Décrivez ce que vous souhaitez :</p>
              <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} placeholder="Ex. : site vitrine avec catalogue et formulaire de devis" className="w-full rounded-lg border-[1.5px] border-border-strong bg-surface px-3 py-2 text-[13px]" />
              <div className="flex gap-2">
                <Button loading={busy === "request"} disabled={busy !== null} onClick={() => act("request", async () => { await requestWebsiteCreation(notes.trim() || null); return "Demande envoyée : nous revenons vers vous."; })}>Envoyer la demande</Button>
                <Button variant="ghost" onClick={() => setNoSite(false)}>Annuler</Button>
              </div>
            </div>
          )}
        </div>
      )}

      {a && !compact && (
        <div className="space-y-3 text-[13px]">
          <p className="leading-relaxed text-text">{a.summary}</p>
          {a.offer.length > 0 && <p className="text-text-soft"><span className="font-semibold text-text">Offre présentée :</span> {a.offer.join(", ")}</p>}
          {a.audience && <p className="text-text-soft"><span className="font-semibold text-text">Public visé :</span> {a.audience}</p>}
          {a.weaknesses.length > 0 && <p className="text-text-soft"><span className="font-semibold text-text">À améliorer :</span> {a.weaknesses.join(" · ")}</p>}
          {(intelligence?.not_in_catalog?.length ?? 0) > 0 && <p className="text-text-soft"><span className="font-semibold text-text">Sur le site mais pas dans votre catalogue :</span> {intelligence!.not_in_catalog!.join(", ")}</p>}
          {((intelligence?.emails?.length ?? 0) + (intelligence?.phones?.length ?? 0)) > 0 && <p className="text-text-soft"><span className="font-semibold text-text">Contacts trouvés :</span> {[...(intelligence?.emails ?? []), ...(intelligence?.phones ?? [])].join(" · ")}</p>}
          {a.improvements.length > 0 && (
            <div>
              <p className="font-semibold text-text">Améliorations proposées (aussi dans vos décisions)</p>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-text-soft">
                {a.improvements.map((i) => <li key={i.title}><span className="text-text">{i.title}</span>{i.why ? ` : ${i.why}` : ""}</li>)}
              </ul>
            </div>
          )}
          {a.syncs.length > 0 && (
            <div>
              <p className="font-semibold text-text">Synchronisations possibles avec le logiciel</p>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-text-soft">
                {a.syncs.map((i) => <li key={i.title}><span className="text-text">{i.title}</span>{i.why ? ` : ${i.why}` : ""}</li>)}
              </ul>
            </div>
          )}
          {!intelligence?.by_model && <p className="text-[12px] text-text-faint">Analyse simplifiée (sans modèle de langage) : ajoutez la clé OpenRouter pour une lecture complète.</p>}
        </div>
      )}
    </Card>
  );
}
