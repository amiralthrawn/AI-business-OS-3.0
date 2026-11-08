"use client";

import { useEffect, useState } from "react";
import { agentsCall } from "@/lib/api";

type Job = { agent: string; label: string; status: "running" | "done" | "error" | "cancelled"; percent: number; steps: string[]; elapsed: number; started: number; cancelling: boolean };

const NAME: Record<string, string> = { analyste: "Analyste", veilleur: "Veilleur", guide: "Guide", executant: "Exécutant", navigateur: "Navigateur" };

// A small card that follows the person through the app and tells what the AI
// is doing right now. The work runs on the server: changing page never stops
// it. The cross closes the card; "Arrêter" really stops the work.
export default function AIProgressDock() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [hidden, setHidden] = useState<Set<string>>(new Set());

  useEffect(() => {
    try {
      if (!sessionStorage.getItem("aibos_questions_asked")) {
        sessionStorage.setItem("aibos_questions_asked", "1");
        void agentsCall("/questions/refresh").catch(() => undefined); // the AI looks for what it still needs to ask
      }
    } catch {
      /* storage unavailable */
    }
    let alive = true;
    const load = () => {
      if (document.hidden) return;
      agentsCall<Job[]>("/progress", "GET").then((j) => alive && setJobs(j)).catch(() => undefined);
    };
    load();
    const timer = setInterval(load, 3000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);

  const working = jobs.some((j) => j.status === "running");
  useEffect(() => {
    if (!working) return;
    const warn = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [working]);

  const visible = jobs.filter((j) => !hidden.has(`${j.agent}:${j.started}`) && (j.status === "running" || j.elapsed < 300));
  if (visible.length === 0) return null;

  const close = (j: Job) => setHidden((h) => new Set(h).add(`${j.agent}:${j.started}`));
  const stop = (j: Job) => void agentsCall(`/progress/${j.agent}/cancel`).catch(() => undefined);

  return (
    <div className="pointer-events-none fixed bottom-[calc(76px+env(safe-area-inset-bottom))] right-3 z-40 flex w-[min(360px,calc(100vw-24px))] flex-col gap-2 md:bottom-5 md:right-5">
      {visible.map((j) => (
        <div key={`${j.agent}:${j.started}`} className="pointer-events-auto rounded-2xl border border-border bg-surface p-3.5 shadow-card" role="status">
          <div className="flex items-start gap-2.5">
            <span className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${j.status === "running" ? "animate-pulse bg-accent" : j.status === "done" ? "bg-success" : "bg-danger"}`} />
            <div className="min-w-0 flex-1">
              <p className="text-[12.5px] font-semibold text-text">{NAME[j.agent] ?? j.agent} {j.status === "running" ? "travaille pour vous" : j.status === "done" ? "a terminé" : j.status === "cancelled" ? "a été arrêté" : "s'est interrompu"}</p>
              <p className="mt-0.5 text-[12.5px] text-text-soft">{j.cancelling && j.status === "running" ? "Arrêt en cours…" : j.label}</p>
              {j.status === "running" && (
                <>
                  <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-sunken">
                    <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${Math.max(4, j.percent)}%` }} />
                  </div>
                  <div className="mt-1.5 flex items-center justify-between gap-2 text-[11.5px] text-text-faint">
                    <span>Continue même si vous changez de page</span>
                    <button type="button" onClick={() => stop(j)} className="font-semibold text-text-soft hover:text-danger">Arrêter</button>
                  </div>
                </>
              )}
            </div>
            <button type="button" onClick={() => close(j)} className="-mr-1 -mt-1 rounded-full px-1.5 text-[18px] leading-none text-text-faint hover:text-text" aria-label="Fermer">×</button>
          </div>
        </div>
      ))}
    </div>
  );
}
