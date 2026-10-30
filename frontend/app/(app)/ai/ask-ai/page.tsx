"use client";

import { useState } from "react";
import TaskActionButtons from "@/components/actions/TaskActionButtons";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import ErrorBanner from "@/components/ui/ErrorBanner";
import PageHeader from "@/components/ui/PageHeader";
import { askAI } from "@/lib/api";
import { CAPABILITY_LABEL_FR } from "@/lib/labels";
import type { AskAIResponse } from "@/lib/types";

const EXAMPLES = ["Pourquoi la marge est-elle en baisse ?", "Quelle est notre exposition au risque fournisseur ?", "Quels clients risquent de partir ?"];
const AGENT_LABEL_FR: Record<string, string> = { finance: "Finance", procurement: "Achats", sales: "Ventes" };

export default function AskAIPage() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<AskAIResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(q: string) {
    if (!q.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await askAI(q));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Une erreur est survenue.");
    } finally {
      setLoading(false);
    }
  }

  const agents = result ? result.agent.split(",").map((a) => a.trim()) : [];

  return (
    <main className="mx-auto max-w-2xl space-y-7 p-8 md:p-12">
      <PageHeader title="Demander à l'IA" description="Une question, répondue à partir de vraies données métier par un agent spécialisé. Pas de mémoire, pas d'historique." />

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit(question);
        }}
        className="flex gap-2.5"
      >
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Quelle est notre situation fournisseurs actuelle ?"
          className="flex-1 rounded-xl border-[1.5px] border-border-strong px-4 py-3 text-[14px] outline-none focus:border-accent"
        />
        <Button type="submit" loading={loading} disabled={!question.trim()}>
          Demander
        </Button>
      </form>

      <div className="flex flex-wrap gap-2">
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            type="button"
            onClick={() => {
              setQuestion(ex);
              submit(ex);
            }}
            className="rounded-full border border-border bg-surface-alt px-3 py-1.5 text-[12.5px] text-text-soft transition-colors hover:border-border-strong hover:text-text"
          >
            {ex}
          </button>
        ))}
      </div>

      {error && <ErrorBanner message={error} />}

      {result && (
        <div className="animate-reveal space-y-6">
          <Card className="p-6">
            <span className="text-[11.5px] font-bold tracking-wide text-text-faint uppercase">Réponse</span>
            <p className="mt-3 whitespace-pre-wrap text-[14px] leading-relaxed text-text">{result.answer}</p>
          </Card>

          <details className="rounded-2xl border border-border bg-surface-alt p-5">
            <summary className="cursor-pointer text-[11.5px] font-bold tracking-wide text-text-faint uppercase">
              Comment cette réponse a été construite
            </summary>
            <div className="mt-4 space-y-4">
              <div>
                <p className="text-[12px] font-semibold text-text-soft">Secteur{agents.length > 1 ? "s" : ""} consulté{agents.length > 1 ? "s" : ""}</p>
                <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                  {agents.map((a) => (
                    <Badge key={a} label={AGENT_LABEL_FR[a] ?? a} tone="accent" />
                  ))}
                  {agents.length > 1 && <span className="text-[11px] font-semibold text-warning">raisonnement cross-domaine</span>}
                </div>
              </div>

              <div>
                <p className="text-[12px] font-semibold text-text-soft">Le système a consulté</p>
                <ul className="mt-1.5 list-disc space-y-1 pl-4 text-[12.5px] text-text-soft">
                  {[...new Set(result.capabilities_used.map((c) => CAPABILITY_LABEL_FR[c] ?? c))].map((label) => (
                    <li key={label}>{label}</li>
                  ))}
                </ul>
              </div>
            </div>
          </details>

          {result.requires_human_validation && result.action_result && (
            <div>
              <p className="mb-2.5 text-[13px] font-semibold text-warning">Cette réponse inclut une action proposée — rien n&rsquo;a encore été exécuté.</p>
              <TaskActionButtons taskId={result.action_result.task_id} taskTitle={result.action_result.title} />
            </div>
          )}
        </div>
      )}
    </main>
  );
}
