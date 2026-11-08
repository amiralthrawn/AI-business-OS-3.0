"use client";

import { useEffect, useState } from "react";
import { agentsCall } from "@/lib/api";
import Button from "@/components/ui/Button";

type Entry = { at: string; text: string };

// The Directeur's journal: what it decided, and when. It also runs on its own every hour.
export default function DirecteurPanel({ onDone }: { onDone: () => Promise<void> }) {
  const [log, setLog] = useState<Entry[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const load = () => agentsCall<Entry[]>("/directeur/journal", "GET").then(setLog).catch(() => undefined);
  useEffect(() => {
    void load();
  }, []);

  async function go() {
    setBusy(true);
    setError(null);
    try {
      await agentsCall("/directeur/run");
      await load();
      await onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Échec");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <p className="text-[11.5px] font-bold uppercase tracking-wide text-text-faint">Son journal</p>
      <p className="mt-1 text-[12.5px] text-text-soft">Toutes les heures, le Directeur fait le point : il vous pose des questions, propose des initiatives et s&rsquo;assure que sans cesse un agent travaille.</p>
      <Button className="mt-2.5" loading={busy} onClick={() => void go()}>Lui demander de faire le point maintenant</Button>
      {error && <p className="mt-2 text-[13px] text-danger">{error}</p>}
      {log.length === 0 ? (
        <p className="mt-3 text-[13px] text-text-faint">Pas encore de point fait.</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {log.slice(0, 6).map((e) => (
            <li key={e.at} className="rounded-lg border border-border px-3 py-2 text-[12.5px] text-text-soft">
              {e.text} <span className="text-text-faint">· {new Date(e.at).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
