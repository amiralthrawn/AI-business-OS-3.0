"use client";

import { useState } from "react";
import Button from "@/components/ui/Button";
import { createTask } from "@/lib/api";
import type { RelatedEntityType } from "@/lib/types";

interface CreateTaskButtonProps {
  defaultTitle: string;
  relatedEntityType?: RelatedEntityType;
  relatedEntityId?: string;
}

// "Créer une tâche" (Step 27) -- a real, immediate Task (status "open"),
// never routed through AI approval since a human created it directly. Same
// backend write as every other real action in the product (POST /actions/tasks).
export default function CreateTaskButton({ defaultTitle, relatedEntityType, relatedEntityId }: CreateTaskButtonProps) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState(defaultTitle);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!title.trim()) return;
    setLoading(true);
    setError(null);
    try {
      await createTask({ title: title.trim(), related_entity_type: relatedEntityType, related_entity_id: relatedEntityId });
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Une erreur est survenue.");
    } finally {
      setLoading(false);
    }
  }

  if (done) {
    return <p className="text-[12.5px] font-medium text-success">Tâche créée.</p>;
  }

  if (!open) {
    return (
      <Button variant="ghost" onClick={() => setOpen(true)}>
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
        </svg>
        Créer une tâche
      </Button>
    );
  }

  return (
    <div className="rounded-xl border-[1.5px] border-border-strong bg-surface p-4">
      <label className="mb-1.5 block text-[11.5px] font-medium text-text-faint">Titre de la tâche</label>
      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        className="w-full rounded-lg border-[1.5px] border-border-strong px-3 py-2 text-[13.5px] outline-none focus:border-accent"
      />
      {error && <p className="mt-2 text-[12px] text-danger">{error}</p>}
      <div className="mt-3 flex gap-2">
        <Button variant="primary" loading={loading} onClick={submit} disabled={!title.trim()}>
          Créer
        </Button>
        <Button variant="ghost" onClick={() => setOpen(false)}>
          Annuler
        </Button>
      </div>
    </div>
  );
}
