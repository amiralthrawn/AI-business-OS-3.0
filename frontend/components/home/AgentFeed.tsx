"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import { type AgentProposal, agentsCall } from "@/lib/api";

const ACTION_LABEL: Record<string, string> = { calendar_event: "Ajouter au calendrier", task: "Créer la tâche", browser: "Lancer l\u2019IA dans le navigateur" };
const AUTO_LABEL: Record<string, string> = { calendar_event: "Ajouté au calendrier", task: "Tâche créée", browser: "Navigateur lancé : suivez-le dans Agents IA", none: "Fait" };

function host(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

// What the agents found or did, as cards of the decision feed.
export default function AgentFeed({ proposals }: { proposals: AgentProposal[] }) {
  const router = useRouter();
  const [state, setState] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [text, setText] = useState<Record<string, string>>({});

  async function call(p: AgentProposal, path: string, next: string, body?: unknown) {
    setBusy(p.id);
    setError(null);
    try {
      await agentsCall(`/proposals/${p.id}/${path}`, "POST", body);
      setState((s) => ({ ...s, [p.id]: next }));
      if (path === "answer") router.refresh(); // the agent may have deduced tasks or a follow-up question
    } catch (e) {
      setError(e instanceof Error ? e.message : "Échec");
    } finally {
      setBusy(null);
    }
  }

  const open = proposals.filter((p) => !state[p.id]);
  const done = proposals.filter((p) => state[p.id]);
  if (proposals.length === 0) return null;

  return (
    <section className="space-y-4">
      <span className="block text-[11.5px] font-bold uppercase tracking-wide text-text-faint">Ce que l&rsquo;IA a trouvé ou fait pour vous</span>
      {error && <p className="text-[13px] text-danger">{error}</p>}
      {open.map((p) => {
        if (p.kind === "missing_info") {
          return (
            <Card key={p.id} className="p-6">
              <Badge label="L'IA a besoin d'une information" tone="warning" />
              <p className="mt-2.5 text-[16px] font-semibold leading-snug text-text">{p.title}</p>
              {p.why && <p className="mt-1.5 text-[13px] text-text-soft">{p.why}</p>}
              <div className="mt-3 flex gap-2.5">
                <input
                  value={text[p.id] ?? ""}
                  onChange={(e) => setText((t) => ({ ...t, [p.id]: e.target.value }))}
                  placeholder="Votre réponse"
                  className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-surface px-3 py-2 text-[13.5px]"
                />
                <Button loading={busy === p.id} disabled={!(text[p.id] ?? "").trim()} onClick={() => call(p, "answer", "answered", { text: text[p.id] })}>Répondre</Button>
              </div>
            </Card>
          );
        }
        if (p.status === "auto_done") {
          return (
            <Card key={p.id} className="border-success/40 p-5">
              <div className="flex flex-wrap items-center gap-2">
                <Badge label="Fait automatiquement" tone="success" />
                <span className="text-[12px] text-text-faint">{AUTO_LABEL[p.action_type] ?? "Fait"}</span>
              </div>
              <p className="mt-2 text-[14.5px] font-semibold text-text">{p.title}</p>
              {(p.answer || p.summary) && p.agent === "executant" && <p className="mt-1.5 whitespace-pre-wrap text-[13px] text-text-soft">{p.answer ?? p.summary}</p>}
              <div className="mt-3"><Button variant="ghost" loading={busy === p.id} onClick={() => call(p, "undo", "undone")}>Annuler</Button></div>
            </Card>
          );
        }
        return (
          <Card key={p.id} className="p-6">
            <div className="flex flex-wrap items-center gap-2">
              <Badge label={p.action_type === "browser" ? "Le navigateur peut le faire" : p.agent === "analyste" ? "Proposé par l'Analyste" : p.agent === "guide" ? "Proposé par le Guide" : "Trouvé par le Veilleur"} tone="accent" />
              {p.category && <span className="text-[11px] font-bold uppercase tracking-wide text-accent-strong">{p.category}</span>}
              {p.event_date && <span className="ml-auto text-[13px] font-semibold text-text">{new Date(p.event_date).toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" })}</span>}
            </div>
            <p className="mt-2.5 text-[16px] font-semibold leading-snug text-text">{p.title}</p>
            {p.summary && <p className="mt-1.5 text-[13.5px] text-text-soft">{p.summary}</p>}
            {p.action_text && p.action_type !== "none" && (
              <p className="mt-2 text-[13.5px] text-text"><span className="font-semibold text-accent-strong">L&rsquo;IA propose : </span>{p.action_text}</p>
            )}
            <div className="mt-4 flex flex-wrap gap-2.5">
              {p.action_type === "task" && <Button loading={busy === p.id} onClick={() => call(p, "execute", "accepted")}>Le faire seul (Exécutant)</Button>}
              {p.action_type !== "none" && <Button variant={p.action_type === "task" ? "ghost" : "primary"} disabled={busy === p.id} onClick={() => call(p, "accept", "accepted")}>Valider · {ACTION_LABEL[p.action_type]}</Button>}
              <Button variant="ghost" onClick={() => call(p, "ignore", "ignored")}>Ignorer</Button>
            </div>
            {(p.why || p.sources.length > 0) && (
              <details className="mt-4">
                <summary className="cursor-pointer select-none text-[12.5px] font-semibold text-text-soft hover:text-text">Pourquoi ?</summary>
                <div className="mt-2.5 space-y-2 rounded-xl bg-surface-sunken p-4">
                  {p.why && <p className="text-[13px] text-text-soft">{p.why}</p>}
                  {p.sources.length > 0 && (
                    <p className="text-[12.5px] text-text-soft">
                      Sources :{" "}
                      {p.sources.slice(0, 5).map((s, i) => (
                        <a key={s} href={s} target="_blank" rel="noreferrer" className="font-semibold text-accent-strong hover:underline">{i > 0 ? ", " : ""}{host(s)}</a>
                      ))}
                    </p>
                  )}
                </div>
              </details>
            )}
          </Card>
        );
      })}
      {done.length > 0 && <p className="text-[12.5px] text-text-faint">{done.length} traité{done.length > 1 ? "s" : ""} à l&rsquo;instant.</p>}
    </section>
  );
}
