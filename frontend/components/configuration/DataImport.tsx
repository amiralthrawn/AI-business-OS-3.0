"use client";

import { useEffect, useState } from "react";
import { getIntegrationPlan, importDataFile } from "@/lib/api";
import type { ImportKind, ImportResultRead, IntegrationItem, IntegrationPlan } from "@/lib/types-config";

const KIND_LABEL: Record<ImportKind, string> = {
  fec: "FEC comptable",
  customers: "Clients",
  suppliers: "Fournisseurs",
  products: "Articles / produits",
};

const fmt = (n: number) => new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 }).format(n);

// The real way data comes in: the file each tool can export. Every upload is
// read for real and lands in the company's own customers, suppliers and
// products (and, for a FEC, a financial summary). Nothing is simulated.
export default function DataImport({ refreshKey = 0 }: { refreshKey?: number }) {
  const [plan, setPlan] = useState<IntegrationPlan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, ImportResultRead | string>>({});

  async function reload() {
    try {
      setPlan(await getIntegrationPlan());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chargement impossible.");
    }
  }

  useEffect(() => {
    void reload();
  }, [refreshKey]);

  async function upload(slot: string, kind: ImportKind, file: File, tool?: string) {
    setBusy(slot);
    try {
      const res = await importDataFile(kind, file, tool);
      setResults((r) => ({ ...r, [slot]: res }));
      await reload();
    } catch (err) {
      setResults((r) => ({ ...r, [slot]: err instanceof Error ? err.message : "Import impossible." }));
    } finally {
      setBusy(null);
    }
  }

  function renderUploader({ slot, kind, tool }: { slot: string; kind: ImportKind; tool?: string }) {
    const result = results[slot];
    return (
      <div key={slot} className="rounded-xl border border-border px-3.5 py-3">
        <div className="flex items-center justify-between gap-3">
          <span className="text-[13px] font-semibold text-text">{KIND_LABEL[kind]}</span>
          <label className={`cursor-pointer rounded-lg border-[1.5px] border-border-strong px-3 py-1.5 text-[12px] font-semibold text-text-soft hover:border-accent hover:text-accent ${busy === slot ? "opacity-50" : ""}`}>
            {busy === slot ? "Lecture…" : "Choisir un fichier"}
            <input
              type="file"
              className="hidden"
              accept={kind === "fec" ? ".txt,.csv,.fec,text/plain" : ".csv,.xlsx,.xlsm,.txt,text/csv"}
              disabled={busy !== null}
              onChange={(e) => {
                const file = e.target.files?.[0];
                e.target.value = "";
                if (file) void upload(slot, kind, file, tool);
              }}
            />
          </label>
        </div>
        {typeof result === "string" && <p className="mt-2 text-[12px] text-danger">{result}</p>}
        {result && typeof result !== "string" && (
          <div className="mt-2 text-[12px] text-text-soft">
            <p>
              <span className="font-semibold text-success">{result.created} ajouté{result.created > 1 ? "s" : ""}</span>
              {result.updated > 0 && ` · ${result.updated} mis à jour`}
              {result.skipped > 0 && ` · ${result.skipped} ignoré${result.skipped > 1 ? "s" : ""}`}
            </p>
            {result.summary && (
              <p className="mt-1">
                Chiffre d&rsquo;affaires lu : {fmt(result.summary.revenue)} · achats : {fmt(result.summary.purchases)} ({result.summary.entries} écritures)
              </p>
            )}
            {result.problems.slice(0, 3).map((p) => (
              <p key={p} className="text-text-faint">{p}</p>
            ))}
          </div>
        )}
      </div>
    );
  }

  if (error) return <p className="text-[13px] text-danger">{error}</p>;
  if (!plan) return <p className="text-[13px] text-text-faint">Chargement…</p>;

  const items: IntegrationItem[] = plan.tools;
  const fec = plan.fec_summary;

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-border-strong bg-surface-sunken p-4">
        <p className="text-[13.5px] font-semibold text-text">Commencez par ces trois fichiers : ils suffisent à faire comprendre votre activité à l&rsquo;IA.</p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {renderUploader({ slot: "fec", kind: "fec" })}
          {renderUploader({ slot: "customers", kind: "customers" })}
          {renderUploader({ slot: "suppliers", kind: "suppliers" })}
          {renderUploader({ slot: "products", kind: "products" })}
        </div>
        <p className="mt-3 text-[12px] text-text-faint">
          CSV (virgule, point-virgule ou tabulation) ou Excel .xlsx. Les colonnes sont reconnues par leur sens : « Client », « Raison sociale », « Désignation », « Prix d&rsquo;achat »… Réimporter un fichier met à jour sans créer de doublons.
        </p>
        {fec && (
          <p className="mt-2 text-[12px] text-text-soft">
            Dernier FEC lu : {fec.customers_found} clients, {fec.suppliers_found} fournisseurs, du {fec.from ?? "?"} au {fec.to ?? "?"}.
          </p>
        )}
      </div>

      {items.map((item) => (
        <div key={item.key} className="rounded-2xl border border-border p-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-[14px] font-semibold text-text">{item.label}</p>
            <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${item.status === "imported" ? "bg-success/15 text-success" : "bg-surface-sunken text-text-soft"}`}>
              {item.status === "imported" ? "Données reçues" : "Données à importer"}
            </span>
          </div>
          <p className="mt-1 text-[12px] text-text-faint">{item.category_label} · contient : {item.data.join(", ")}</p>
          <p className="mt-2 text-[12.5px] text-text-soft"><span className="font-semibold text-text">Comment l&rsquo;exporter&nbsp;:</span> {item.export_help}</p>
          <p className="mt-1.5 text-[12.5px] text-text-soft"><span className="font-semibold text-text">Ce que l&rsquo;IA en fait&nbsp;:</span> {item.ai_use}</p>
          {item.import_kinds.length > 0 ? (
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              {item.import_kinds.map((kind) => renderUploader({ slot: `${item.key}:${kind}`, kind, tool: item.key }))}
            </div>
          ) : (
            <p className="mt-2 text-[12px] text-text-faint">
              Ce type d&rsquo;outil se relie par {item.direct_methods.join(" ou ")} : l&rsquo;IA vous guidera dans l&rsquo;autorisation à donner lors de la mise en place avec votre équipe technique.
            </p>
          )}
        </div>
      ))}
      {plan.custom_tools.length > 0 && (
        <p className="text-[12.5px] text-text-soft">
          Outils ajoutés par vous : {plan.custom_tools.join(", ")}. Exportez leurs données en CSV ou Excel et déposez-les ci-dessus.
        </p>
      )}
    </div>
  );
}
