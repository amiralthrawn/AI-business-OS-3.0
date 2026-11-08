"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { importAuto, importDataFile } from "@/lib/api";
import type { ImportKind } from "@/lib/types-config";
import Button from "@/components/ui/Button";

const HELP: Record<string, { title: string; where: string[]; formats: string }> = {
  fec: {
    title: "Déposer votre FEC",
    where: [
      "Le FEC (Fichier des Écritures Comptables) est un fichier que tout logiciel de comptabilité sait produire : Sage, EBP, Cegid, Quadra, Pennylane, Tiime…",
      "Dans votre logiciel : menu « Exports » ou « Déclarations fiscales », puis « Fichier des Écritures Comptables (FEC) ». Choisissez l'exercice en cours.",
      "Pas d'accès au logiciel ? Votre expert-comptable peut vous l'envoyer en 2 minutes : demandez-lui « le FEC de l'exercice en cours ».",
    ],
    formats: "Fichier .txt ou .csv",
  },
  customers: {
    title: "Déposer votre liste de clients",
    where: [
      "Dans votre outil de facturation, de CRM ou de gestion : « Clients » puis « Exporter » (CSV ou Excel).",
      "À défaut, un tableur Excel avec une ligne par client (nom, pays, e-mail) suffit.",
    ],
    formats: "Excel ou CSV",
  },
  suppliers: {
    title: "Déposer votre liste de fournisseurs",
    where: [
      "Dans votre logiciel de gestion ou de comptabilité : « Fournisseurs » puis « Exporter » (CSV ou Excel).",
      "À défaut, un tableur avec une ligne par fournisseur (nom, pays, délai de livraison habituel) suffit.",
    ],
    formats: "Excel ou CSV",
  },
  products: {
    title: "Déposer votre catalogue de produits",
    where: [
      "Dans votre logiciel de stock, de gestion ou votre boutique en ligne : « Produits » ou « Articles » puis « Exporter ».",
      "Idéalement avec la référence, le nom, le prix de vente et le coût d'achat : c'est ce qui permet de calculer vos marges.",
    ],
    formats: "Excel ou CSV",
  },
  sales: {
    title: "Déposer vos ventes et vos achats",
    where: [
      "Dans votre outil de facturation : « Factures » (ventes) et « Factures fournisseurs » (achats), puis « Exporter ».",
      "Si vous avez un FEC, déposez-le plutôt : il contient déjà les deux.",
    ],
    formats: "Excel ou CSV",
  },
};

// The Guide opens the right drop zone in place, with where to find the document.
export default function ImportHelper({ kind, onClose }: { kind: string; onClose: () => void }) {
  const router = useRouter();
  const help = HELP[kind] ?? HELP.sales;
  const picker = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState<{ file: string; text: string; ok: boolean }[]>([]);

  async function upload(files: FileList | File[]) {
    setBusy(true);
    const done = [...results];
    for (const file of Array.from(files)) {
      try {
        const r = kind === "sales" ? await importAuto(file) : await importDataFile(kind as ImportKind, file);
        done.push({ file: file.name, ok: true, text: `${r.created} ajouté${r.created > 1 ? "s" : ""}${r.updated ? `, ${r.updated} mis à jour` : ""}` });
      } catch (err) {
        done.push({ file: file.name, ok: false, text: err instanceof Error ? err.message : "Import impossible." });
      }
      setResults([...done]);
    }
    setBusy(false);
    router.refresh();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-0 sm:items-center sm:p-6" role="dialog" aria-modal="true">
      <div className="max-h-[92vh] w-full max-w-xl overflow-y-auto rounded-t-[22px] border border-border bg-surface p-5 shadow-card sm:rounded-[22px] sm:p-7">
        <div className="flex items-start justify-between gap-3">
          <h2 className="font-display text-[22px] italic">{help.title}</h2>
          <button type="button" onClick={onClose} className="rounded-full px-2 text-[20px] leading-none text-text-faint hover:text-text" aria-label="Fermer">×</button>
        </div>
        <p className="mt-4 text-[11.5px] font-bold uppercase tracking-wide text-text-faint">Où trouver ce document</p>
        <ul className="mt-2 space-y-2 text-[13.5px] text-text-soft">
          {help.where.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
        <div
          onDragOver={(e) => { e.preventDefault(); setOver(true); }}
          onDragLeave={() => setOver(false)}
          onDrop={(e) => { e.preventDefault(); setOver(false); if (e.dataTransfer.files.length) void upload(e.dataTransfer.files); }}
          className={`mt-5 rounded-2xl border-2 border-dashed px-5 py-8 text-center transition-colors ${over ? "border-accent bg-accent-soft" : "border-border-strong bg-surface-sunken"}`}
        >
          <p className="text-[14.5px] font-semibold text-text">Glissez votre fichier ici</p>
          <p className="mt-1 text-[12.5px] text-text-soft">{help.formats}</p>
          <input ref={picker} type="file" multiple className="hidden" accept=".csv,.xls,.xlsx,.xlsm,.txt,.fec" onChange={(e) => { if (e.target.files?.length) void upload(e.target.files); e.target.value = ""; }} />
          <Button className="mt-4" loading={busy} onClick={() => picker.current?.click()}>Choisir un fichier</Button>
        </div>
        {results.length > 0 && (
          <ul className="mt-4 space-y-2">
            {results.map((r, i) => (
              <li key={`${r.file}-${i}`} className={`rounded-xl border px-4 py-2.5 text-[13px] ${r.ok ? "border-success/40 bg-success-soft text-success" : "border-danger/40 bg-danger-soft text-danger"}`}>
                <span className="break-all font-semibold">{r.file}</span> · {r.text}
              </li>
            ))}
          </ul>
        )}
        <div className="mt-5 flex justify-end">
          <button type="button" onClick={onClose} className="text-[13px] font-semibold text-accent-strong hover:underline">{results.some((r) => r.ok) ? "Terminé" : "Plus tard"}</button>
        </div>
      </div>
    </div>
  );
}
