"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import ToolSyncPage from "@/components/configuration/ToolSyncPage";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import { type ManagedService, connectManagedService, getManagedServices } from "@/lib/api";

// The two connections the product keeps asking for until they exist: the
// company mailbox and the control of its website. The Guide agent researches
// the procedure for the chosen provider and walks the person through it.
export default function ServiceConnections() {
  const router = useRouter();
  const [services, setServices] = useState<ManagedService[]>([]);
  const [choice, setChoice] = useState<Record<string, string>>({});
  const [open, setOpen] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      setServices(await getManagedServices());
    } catch {
      setServices([]);
    }
  }
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, []);

  const todo = services.filter((s) => s.state === "none");
  if (todo.length === 0) return null;

  return (
    <section className="space-y-4">
      {todo.map((s) => {
        const picked = choice[s.service] ?? s.choices[0]?.key ?? "";
        const label = s.choices.find((c) => c.key === picked)?.label ?? picked;
        return (
          <Card key={s.service} className="space-y-3 p-4 sm:p-6">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-warning-soft px-2.5 py-0.5 text-[11.5px] font-semibold text-warning">À faire</span>
              <h2 className="text-[16px] font-semibold text-text">{s.label}</h2>
            </div>
            <p className="text-[13.5px] text-text-soft">{s.why}</p>
            {open === s.service ? (
              <div className="rounded-xl border border-border p-3 sm:p-4">
                <ToolSyncPage key={picked} toolKey={picked} label={label} />
                <Button variant="ghost" className="mt-3" onClick={() => { setOpen(null); void load(); router.refresh(); }}>Fermer le guide</Button>
              </div>
            ) : (
              <div className="flex flex-wrap items-center gap-2">
                <select value={picked} onChange={(e) => setChoice((c) => ({ ...c, [s.service]: e.target.value }))} className="min-w-0 flex-1 rounded-xl border-[1.5px] border-border-strong bg-surface px-3.5 py-2.5 text-[14px]">
                  {s.choices.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
                </select>
                <Button
                  loading={busy === s.service}
                  disabled={busy !== null || !picked}
                  onClick={async () => {
                    setBusy(s.service);
                    setError(null);
                    try {
                      await connectManagedService(s.service, picked);
                      setOpen(s.service);
                    } catch (e) {
                      setError(e instanceof Error ? e.message : "Échec");
                    } finally {
                      setBusy(null);
                    }
                  }}
                >
                  Lancer la connexion guidée
                </Button>
              </div>
            )}
          </Card>
        );
      })}
      {error && <p className="text-[13px] text-danger">{error}</p>}
    </section>
  );
}
