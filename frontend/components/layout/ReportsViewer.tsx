"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { agentsCall } from "@/lib/api";
import Button from "@/components/ui/Button";

export type Report = { id: string; agent: string; title: string; text: string; at: string; read: boolean; next: { label: string; href?: string; relay?: string }[] };

const when = (iso: string) => new Date(iso).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });

// A half-page with the reports of the agents: what they did, what they found, what they suggest next.
export default function ReportsViewer({ firstId, onClose }: { firstId?: string | null; onClose: () => void }) {
  const [reports, setReports] = useState<Report[]>([]);
  const [openId, setOpenId] = useState<string | null>(firstId ?? null);
  const [busy, setBusy] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  useEffect(() => {
    agentsCall<Report[]>("/reports", "GET").then(setReports).catch(() => undefined);
  }, []);
  useEffect(() => {
    if (openId) void agentsCall("/reports/read", "POST", { id: openId }).catch(() => undefined);
  }, [openId]);

  const current = reports.find((r) => r.id === openId) ?? null;

  async function relay(request: string) {
    setBusy(request);
    setResult(null);
    try {
      const r = await agentsCall<{ message: string }>("/veilleur/ask", "POST", { request, follow: false, with_analysis: true });
      setResult(r.message);
    } catch (e) {
      setResult(e instanceof Error ? e.message : "Échec");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="pointer-events-auto fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-center sm:p-6" role="dialog" aria-modal="true">
      <div className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-t-[22px] border border-border bg-surface p-5 shadow-card sm:rounded-[22px] sm:p-7">
        <div className="flex items-start justify-between gap-3">
          <h2 className="font-display text-[22px] italic">{current ? current.title : "Comptes rendus de vos agents"}</h2>
          <button type="button" onClick={onClose} className="rounded-full px-2 text-[20px] leading-none text-text-faint hover:text-text" aria-label="Fermer">×</button>
        </div>
        {current ? (
          <>
            <p className="mt-1 text-[12px] text-text-faint">{when(current.at)}</p>
            <p className="mt-3 whitespace-pre-wrap text-[14px] leading-relaxed text-text">{current.text}</p>
            {current.next.length > 0 && (
              <div className="mt-5 flex flex-wrap gap-2.5">
                {current.next.map((n) =>
                  n.relay ? (
                    <Button key={n.label} loading={busy === n.relay} onClick={() => void relay(n.relay!)}>{n.label}</Button>
                  ) : (
                    <Link key={n.label} href={n.href ?? "/"} onClick={onClose} className="rounded-full border-[1.5px] border-accent px-4 py-2 text-[13px] font-semibold text-accent-strong hover:bg-accent-soft">{n.label}</Link>
                  ),
                )}
              </div>
            )}
            {result && <p className="mt-4 whitespace-pre-wrap rounded-xl bg-surface-sunken p-3.5 text-[13px] text-text-soft">{result}</p>}
            <button type="button" onClick={() => { setOpenId(null); setResult(null); }} className="mt-5 text-[13px] font-semibold text-accent-strong hover:underline">← Tous les comptes rendus</button>
          </>
        ) : (
          <ul className="mt-4 space-y-2">
            {reports.length === 0 && <li className="text-[13px] text-text-faint">Aucun compte rendu pour le moment : ils arrivent à la fin de chaque travail d&rsquo;un agent.</li>}
            {reports.map((r) => (
              <li key={r.id}>
                <button type="button" onClick={() => setOpenId(r.id)} className="w-full rounded-xl border border-border px-4 py-3 text-left hover:bg-surface-sunken">
                  <span className="flex items-center gap-2 text-[13.5px] font-semibold text-text">{!r.read && <span className="h-2 w-2 rounded-full bg-accent" />}{r.title}</span>
                  <span className="mt-0.5 block text-[12px] text-text-faint">{when(r.at)}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
