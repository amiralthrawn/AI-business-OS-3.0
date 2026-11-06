"use client";

import { useEffect, useRef, useState } from "react";
import { getIntegrationPlan, importAuto, requestToolConnection } from "@/lib/api";
import type { ImportKind, ImportResultRead, IntegrationPlan } from "@/lib/types-config";

const KIND_LABEL: Record<ImportKind, string> = {
  fec: "comptabilité (FEC)",
  customers: "clients",
  suppliers: "fournisseurs",
  products: "produits",
  sales: "ventes",
  purchases: "achats",
  stock: "références en stock",
  prospects: "prospects",
};

const fmt = (n: number) => new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 }).format(n);

type Outcome = { file: string; result?: ImportResultRead; error?: string };

// One place to drop files, whatever the tool: the AI recognises what each
// file contains. Files are read for real and land in the company's own
// customers, suppliers, products and finances. Nothing is simulated.
export default function DataImport({ refreshKey = 0, documentsOnly = false }: { refreshKey?: number; documentsOnly?: boolean }) {
  const [plan, setPlan] = useState<IntegrationPlan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [over, setOver] = useState(false);
  const [outcomes, setOutcomes] = useState<Outcome[]>([]);
  const picker = useRef<HTMLInputElement>(null);

  async function reload() {
    try {
      setPlan(await getIntegrationPlan());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chargement impossible.");
    }
  }

  useEffect(() => {
    getIntegrationPlan()
      .then(setPlan)
      .catch((err) => setError(err instanceof Error ? err.message : "Chargement impossible."));
  }, [refreshKey]);

  async function upload(files: FileList | File[]) {
    setBusy(true);
    const done: Outcome[] = [...outcomes];
    for (const file of Array.from(files)) {
      try {
        done.push({ file: file.name, result: await importAuto(file) });
      } catch (err) {
        done.push({ file: file.name, error: err instanceof Error ? err.message : "Import impossible." });
      }
      setOutcomes([...done]);
    }
    setBusy(false);
    await reload();
  }

  async function ask(toolKey: string) {
    try {
      await requestToolConnection(toolKey);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Demande impossible.");
    }
  }

  if (error) return <p className="text-[13px] text-danger">{error}</p>;
  if (!plan) return <p className="text-[13px] text-text-faint">Chargement…</p>;

  const fec = plan.fec_summary;
  const deposited = [...plan.imports].reverse();

  return (
    <div className="space-y-6">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          if (e.dataTransfer.files.length) void upload(e.dataTransfer.files);
        }}
        className={`rounded-2xl border-2 border-dashed px-6 py-9 text-center transition-colors ${over ? "border-accent bg-accent-soft" : "border-border-strong bg-surface-sunken"}`}
      >
        <p className="text-[15px] font-semibold text-text">{documentsOnly ? "Déposez ici vos autres documents" : "Déposez ici vos fichiers"}</p>
        <p className="mx-auto mt-1.5 max-w-md text-[12.5px] text-text-soft">
          Exports de vos outils, tableurs Excel, fichiers CSV, comptabilité (FEC). Plusieurs à la fois, dans n&rsquo;importe quel ordre : l&rsquo;IA reconnaît tout seule s&rsquo;il s&rsquo;agit de clients, de fournisseurs, de produits ou de comptabilité.
        </p>
        <input
          ref={picker}
          type="file"
          multiple
          className="hidden"
          accept=".csv,.xls,.xlsx,.xlsm,.txt,.fec,text/csv,text/plain"
          onChange={(e) => {
            if (e.target.files?.length) void upload(e.target.files);
            e.target.value = "";
          }}
        />
        <button
          type="button"
          disabled={busy}
          onClick={() => picker.current?.click()}
          className="mt-4 rounded-full border-[1.5px] border-accent bg-surface px-5 py-2 text-[13px] font-semibold text-accent-strong hover:bg-accent-soft disabled:opacity-50"
        >
          {busy ? "Lecture en cours…" : "Choisir des fichiers"}
        </button>
      </div>

      <p className={`text-[14px] font-semibold ${deposited.length ? "text-success" : "text-text-faint"}`} aria-live="polite">
        {deposited.length === 0 ? "Aucun document déposé" : deposited.length === 1 ? "1 document déposé" : `${deposited.length} documents déposés`}
      </p>

      {(outcomes.some((o) => o.error) || deposited.length > 0) && (
        <ul className="space-y-2">
          {outcomes.filter((o) => o.error).map((o, i) => (
            <li key={`err-${o.file}-${i}`} className="rounded-xl border border-danger/40 bg-danger-soft px-4 py-3 text-[13px]">
              <span className="font-semibold text-text">{o.file}</span>
              <span className="mt-0.5 block text-danger sm:ml-2 sm:inline">{o.error}</span>
            </li>
          ))}
          {deposited.map((d, i) => (
            <li key={`${d.file}-${d.at}-${i}`} className="rounded-xl border border-border px-4 py-3 text-[13px]">
              <span className="break-all font-semibold text-text">{d.file}</span>
              <span className="mt-0.5 block text-text-soft sm:ml-2 sm:inline">
                {KIND_LABEL[d.kind] ?? d.kind} ·{" "}
                <span className="font-semibold text-success">
                  {fmt(d.created)} ajouté{d.created > 1 ? "s" : ""}
                </span>
                {d.updated > 0 && ` · ${fmt(d.updated)} mis à jour`}
                {d.skipped > 0 && ` · ${fmt(d.skipped)} ignoré${d.skipped > 1 ? "s" : ""}`}
              </span>
            </li>
          ))}
        </ul>
      )}
      {fec && (
        <p className="text-[12.5px] text-text-soft">
          Dernière comptabilité lue : {fec.customers_found} clients et {fec.suppliers_found} fournisseurs, du {fec.from ?? "?"} au {fec.to ?? "?"}.
        </p>
      )}

      {!documentsOnly && plan.tools.length > 0 && (
        <div>
          <p className="mb-3 text-[13.5px] font-semibold text-text">Vos outils : comment récupérer leurs données</p>
          <div className="space-y-2.5">
            {plan.tools.map((item) => (
              <details key={item.key} className="rounded-2xl border border-border px-4 py-3">
                <summary className="flex cursor-pointer select-none items-center justify-between gap-3 text-[14px] font-semibold text-text">
                  {item.label}
                  <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${item.status === "imported" ? "bg-success/15 text-success" : item.connection === "requested" ? "bg-accent-soft text-accent-strong" : "bg-surface-sunken text-text-soft"}`}>
                    {item.status === "imported" ? "Données reçues" : item.connection === "requested" ? "Accompagnement demandé" : "À récupérer"}
                  </span>
                </summary>
                <div className="mt-3 space-y-2 text-[12.5px] text-text-soft">
                  <p>
                    <span className="font-semibold text-text">Le plus simple :</span> {item.export_help} Puis déposez le fichier ci-dessus.
                  </p>
                  <p>
                    <span className="font-semibold text-text">Connexion directe :</span> {item.direct_methods.join(" ou ")}. Elle demande l&rsquo;autorisation de votre administrateur et se fait en lecture seule.
                  </p>
                  {item.connection !== "requested" && item.status !== "imported" && (
                    <button
                      type="button"
                      onClick={() => void ask(item.key)}
                      className="mt-1 rounded-full border-[1.5px] border-border-strong px-4 py-1.5 text-[12.5px] font-semibold text-text-soft hover:border-accent hover:text-accent"
                    >
                      Je veux être accompagné pour connecter {item.label}
                    </button>
                  )}
                </div>
              </details>
            ))}
          </div>
        </div>
      )}
      {!documentsOnly && plan.custom_tools.length > 0 && <p className="text-[12.5px] text-text-soft">Outils ajoutés par vous : {plan.custom_tools.join(", ")}. Exportez leurs données en CSV ou Excel et déposez-les ci-dessus.</p>}
    </div>
  );
}
