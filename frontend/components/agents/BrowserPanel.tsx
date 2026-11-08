"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import { type BrowserStatus, type BrowserTask, browserCall, browserScreen } from "@/lib/api";

const LABEL: Record<BrowserTask["status"], string> = {
  starting: "Ouverture du navigateur…", running: "L'IA travaille", human: "Vous avez la main", needs_human: "L'IA a besoin de vous",
  done: "Terminé", failed: "Échec", cancelled: "Arrêté",
};
const OVER = ["done", "failed", "cancelled"];

// The AI browser: the AI works in a browser shown here. The person watches,
// takes over to log in or validate (what they type goes straight to the page),
// and hands back.
export default function BrowserPanel({ initialGoal = "", autoStart = false }: { initialGoal?: string; autoStart?: boolean }) {
  const [info, setInfo] = useState<BrowserStatus | null>(null);
  const [task, setTask] = useState<BrowserTask | null>(null);
  const [goal, setGoal] = useState(initialGoal);
  const [startUrl, setStartUrl] = useState("");
  const [shot, setShot] = useState<string | null>(null);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [imported, setImported] = useState<Record<number, string>>({});
  const img = useRef<HTMLImageElement>(null);

  useEffect(() => {
    browserCall<BrowserStatus>("/status").then((s) => { setInfo(s); if (s.active) setTask(s.active); }).catch(() => setInfo({ available: false, provider: null, active: null }));
  }, []);

  const poll = useCallback(async () => {
    if (!task) return;
    try {
      const fresh = await browserCall<BrowserTask>(`/tasks/${task.id}`);
      setTask(fresh);
      if (fresh.has_shot && !fresh.live_url) {
        const url = await browserScreen(fresh.id);
        if (url) setShot((old) => { if (old) URL.revokeObjectURL(old); return url; });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Suivi interrompu.");
    }
  }, [task]);
  useEffect(() => {
    if (!task || OVER.includes(task.status)) return;
    const t = setInterval(() => void poll(), 1500);
    return () => clearInterval(t);
  }, [task, poll]);

  async function act<T>(job: () => Promise<T>) {
    setBusy(true);
    setError(null);
    try {
      return await job();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Échec");
    } finally {
      setBusy(false);
    }
  }

  const start = useCallback(async () => {
    const t = await act(() => browserCall<BrowserTask>("/tasks", "POST", { goal: goal.trim(), start_url: startUrl.trim() || null }));
    if (t) { setTask(t); setShot(null); setImported({}); }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [goal, startUrl]);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (autoStart && info?.available && !info.active && goal.trim().length >= 5 && !task) void start();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoStart, info]);

  const control = (path: string, body?: unknown) => act(async () => { await browserCall(`/tasks/${task!.id}${path}`, "POST", body); await poll(); });
  const inHuman = task && (task.status === "human" || task.status === "needs_human");

  function clickShot(e: React.MouseEvent<HTMLImageElement>) {
    if (!inHuman || !img.current || !task) return;
    const r = img.current.getBoundingClientRect();
    void control("/input", { type: "click", x: ((e.clientX - r.left) / r.width) * task.view.width, y: ((e.clientY - r.top) / r.height) * task.view.height });
  }

  return (
    <Card className="space-y-4 p-4 sm:p-6">
      <div>
        <h2 className="font-display text-[22px] italic">Navigateur de l&rsquo;IA</h2>
        <p className="text-[13px] text-text-soft">L&rsquo;IA travaille dans un vrai navigateur, sous vos yeux : exporter un fichier d&rsquo;un logiciel, relever une information, configurer un accès. Quand il faut vous connecter ou valider, elle vous passe la main.</p>
      </div>

      {info && !info.available && !task && (
        <p className="rounded-xl bg-surface-sunken p-3.5 text-[13px] text-text-soft">Le navigateur de l&rsquo;IA n&rsquo;est pas encore activé sur ce serveur (clés du navigateur cloud et OpenRouter à renseigner).</p>
      )}

      {info?.available && (!task || OVER.includes(task.status)) && (
        <div className="space-y-2">
          <textarea value={goal} onChange={(e) => setGoal(e.target.value)} rows={2} placeholder="Ex. : Exporte la liste de mes clients en CSV depuis mon logiciel de facturation" className="w-full rounded-xl border-[1.5px] border-border-strong bg-surface px-3.5 py-2.5 text-[13.5px] outline-none focus:border-accent" />
          <div className="flex flex-wrap gap-2">
            <input value={startUrl} onChange={(e) => setStartUrl(e.target.value)} placeholder="Adresse de départ (facultatif)" className="min-w-0 flex-1 rounded-xl border-[1.5px] border-border-strong bg-surface px-3.5 py-2.5 text-[13.5px]" />
            <Button loading={busy} disabled={busy || goal.trim().length < 5} onClick={() => void start()}>Lancer dans le navigateur</Button>
          </div>
        </div>
      )}
      {error && <p className="text-[13px] text-danger">{error}</p>}

      {task && (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2 text-[13px]">
            <span className={`rounded-full px-2.5 py-0.5 text-[11.5px] font-semibold ${task.status === "needs_human" ? "bg-warning-soft text-warning" : task.status === "done" ? "bg-success-soft text-success" : task.status === "failed" ? "bg-danger/10 text-danger" : "bg-surface-sunken text-text-soft"}`}>{LABEL[task.status]}</span>
            <span className="min-w-0 truncate text-text-soft">{task.goal}</span>
          </div>
          {task.status === "needs_human" && <p className="rounded-xl bg-warning-soft p-3 text-[13.5px] font-semibold text-text">{task.reason}</p>}

          {task.live_url ? (
            <iframe src={task.live_url} title="Navigateur de l'IA" className="h-[420px] w-full rounded-xl border border-border sm:h-[520px]" sandbox="allow-same-origin allow-scripts" />
          ) : shot ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img ref={img} src={shot} alt="Écran du navigateur de l'IA" onClick={clickShot} className={`w-full rounded-xl border border-border ${inHuman ? "cursor-crosshair ring-2 ring-accent" : ""}`} />
          ) : (
            !OVER.includes(task.status) && <p className="text-[13px] text-text-faint">Le navigateur démarre…</p>
          )}

          {!OVER.includes(task.status) && (
            <div className="flex flex-wrap items-center gap-2">
              {task.status === "running" && <Button variant="ghost" disabled={busy} onClick={() => void control("/take-over")}>Prendre la main</Button>}
              {inHuman && <Button disabled={busy} onClick={() => void control("/hand-back")}>Rendre la main à l&rsquo;IA</Button>}
              <Button variant="ghost" disabled={busy} onClick={() => void control("/cancel")}>Arrêter</Button>
            </div>
          )}
          {inHuman && !task.live_url && (
            <div className="space-y-2 rounded-xl bg-surface-sunken p-3.5">
              <p className="text-[12.5px] text-text-soft">Cliquez directement sur l&rsquo;image pour agir. Ce que vous tapez va droit à la page : l&rsquo;IA ne le voit pas et rien n&rsquo;est enregistré.</p>
              <div className="flex flex-wrap gap-2">
                <input type="password" autoComplete="off" value={typed} onChange={(e) => setTyped(e.target.value)} placeholder="Texte à saisir (identifiant, mot de passe, code)" className="min-w-0 flex-1 rounded-lg border-[1.5px] border-border-strong bg-surface px-3 py-2 text-[13.5px]" />
                <Button variant="ghost" disabled={busy || !typed} onClick={async () => { const text = typed; setTyped(""); await control("/input", { type: "type", text }); }}>Saisir</Button>
                <Button variant="ghost" disabled={busy} onClick={() => void control("/input", { type: "key", key: "Enter" })}>Entrée</Button>
                <Button variant="ghost" disabled={busy} onClick={() => void control("/input", { type: "key", key: "Tab" })}>Tab</Button>
                <Button variant="ghost" disabled={busy} onClick={() => void control("/input", { type: "scroll", direction: "down" })}>↓</Button>
                <Button variant="ghost" disabled={busy} onClick={() => void control("/input", { type: "scroll", direction: "up" })}>↑</Button>
              </div>
            </div>
          )}

          {task.summary && <p className="whitespace-pre-wrap rounded-xl bg-surface-sunken p-3.5 text-[13.5px] text-text">{task.summary}</p>}
          {task.downloads.length > 0 && (
            <ul className="space-y-2">
              {task.downloads.map((d) => (
                <li key={d.index} className="flex flex-wrap items-center gap-2 rounded-xl border border-border px-3.5 py-2.5 text-[13px]">
                  <span className="min-w-0 flex-1 truncate font-semibold text-text">{d.name}</span>
                  {imported[d.index] ? <span className="text-success">{imported[d.index]}</span> : (
                    <Button variant="ghost" disabled={busy} onClick={async () => {
                      const r = await act(() => browserCall<{ created: number; updated: number; kind: string }>(`/tasks/${task.id}/downloads/${d.index}/import`, "POST"));
                      if (r) setImported((m) => ({ ...m, [d.index]: `Importé : ${r.created} ajouté(s), ${r.updated} mis à jour` }));
                    }}>Importer dans le logiciel</Button>
                  )}
                </li>
              ))}
            </ul>
          )}
          <details>
            <summary className="cursor-pointer text-[12.5px] font-semibold text-text-soft">Journal des actions</summary>
            <ul className="mt-2 space-y-1 text-[12.5px] text-text-soft">{task.steps.slice().reverse().map((s, i) => <li key={i}>{new Date(s.at).toLocaleTimeString("fr-FR")} · {s.text}</li>)}</ul>
          </details>
        </div>
      )}
    </Card>
  );
}
