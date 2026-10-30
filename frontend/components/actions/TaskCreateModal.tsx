"use client";

import { useState } from "react";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import { createTask } from "@/lib/api";
import { ACTION_LIBRARY, type ActionTemplate } from "@/lib/action-library";
import type { TaskRead } from "@/lib/types";

// "Nouvelle action" (Step 29 points 12-13): picking a template from the real
// action library creates a REAL Task via POST /actions/tasks -- nothing here
// simulates an execution. `context` is the user's own real input, stored in
// the Task's `description`, which is what a detail panel later shows as
// "Pourquoi / Contexte" -- never fabricated at render time.
export default function TaskCreateModal({ onClose, onCreated }: { onClose: () => void; onCreated: (task: TaskRead) => void }) {
  const [domainKey, setDomainKey] = useState(ACTION_LIBRARY[0].key);
  const [selected, setSelected] = useState<ActionTemplate | null>(null);
  const [context, setContext] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const domain = ACTION_LIBRARY.find((d) => d.key === domainKey) ?? ACTION_LIBRARY[0];

  async function submit() {
    if (!selected) return;
    setLoading(true);
    setError(null);
    try {
      const task = await createTask({
        title: selected.label,
        description: context.trim() || undefined,
        domain: domainKey,
        requires_decision: !!selected.requiresDecision,
      });
      onCreated(task);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Une erreur est survenue.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-text/30 p-4" onClick={onClose}>
      <div className="animate-pop w-full max-w-lg rounded-2xl border border-border bg-surface p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h2 className="font-display text-[18px] italic text-text">Nouvelle action</h2>
          <button type="button" onClick={onClose} aria-label="Fermer" className="text-text-faint hover:text-text">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <div className="mt-4 flex flex-wrap gap-1.5">
          {ACTION_LIBRARY.map((d) => (
            <button
              key={d.key}
              type="button"
              onClick={() => {
                setDomainKey(d.key);
                setSelected(null);
              }}
              className={`rounded-full border-[1.5px] px-3 py-1 text-[12.5px] font-medium transition-colors ${
                domainKey === d.key ? "border-accent bg-accent-soft text-accent-strong font-semibold" : "border-border-strong text-text-soft hover:border-text-faint"
              }`}
            >
              {d.label}
            </button>
          ))}
        </div>

        <div className="mt-3 max-h-56 space-y-1 overflow-y-auto pr-1">
          {domain.actions.map((a) => (
            <button
              key={a.id}
              type="button"
              onClick={() => setSelected(a)}
              className={`flex w-full items-center justify-between gap-2 rounded-lg px-3 py-2 text-left text-[13px] transition-colors ${
                selected?.id === a.id ? "bg-accent-soft font-semibold text-accent-strong" : "text-text hover:bg-surface-sunken"
              }`}
            >
              <span>{a.label}</span>
              {a.requiresDecision && <Badge label="Décision requise" tone="warning" />}
            </button>
          ))}
        </div>

        {selected && (
          <div className="mt-4">
            <label className="mb-1.5 block text-[11.5px] font-medium text-text-faint">Contexte (optionnel)</label>
            <textarea
              value={context}
              onChange={(e) => setContext(e.target.value)}
              rows={3}
              placeholder="Pourquoi cette action, informations utiles..."
              className="w-full resize-none rounded-lg border-[1.5px] border-border-strong px-3 py-2 text-[13.5px] outline-none focus:border-accent"
            />
          </div>
        )}

        {error && <p className="mt-2 text-[12.5px] text-danger">{error}</p>}

        <div className="mt-5 flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Annuler
          </Button>
          <Button variant="primary" disabled={!selected} loading={loading} onClick={submit}>
            Créer la tâche
          </Button>
        </div>
      </div>
    </div>
  );
}
