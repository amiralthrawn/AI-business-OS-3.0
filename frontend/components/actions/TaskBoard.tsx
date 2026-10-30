"use client";

import { useState } from "react";
import TaskCard from "@/components/actions/TaskCard";
import TaskCreateModal from "@/components/actions/TaskCreateModal";
import TaskDetailPanel from "@/components/actions/TaskDetailPanel";
import Button from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";
import { SECTOR_LABEL_FR } from "@/lib/labels";
import type { TaskRead } from "@/lib/types";

const DOMAINS = ["finance", "procurement", "sales", "marketing", "hr", "direction", "operations"];

const STATUS_FILTERS: { key: string; label: string; match: (t: TaskRead) => boolean }[] = [
  { key: "all", label: "Tout", match: () => true },
  { key: "pending_validation", label: "À valider", match: (t) => t.status === "pending_validation" },
  { key: "open", label: "À faire", match: (t) => t.status === "open" },
  { key: "in_progress", label: "En cours", match: (t) => t.status === "in_progress" },
  { key: "done", label: "Terminé", match: (t) => t.status === "done" || t.status === "executed" },
];

function Chip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full border-[1.5px] px-3.5 py-1.5 text-[13px] font-medium transition-colors ${
        active ? "border-accent bg-accent-soft text-accent-strong font-semibold" : "border-border-strong text-text-soft hover:border-text-faint"
      }`}
    >
      {label}
    </button>
  );
}

// The Tasks tab as the enterprise's real action center (Step 29 points
// 12-15): filter by sector and by lifecycle stage, open any task for its
// full context, and create real new ones from the action library. All state
// here mirrors real Task rows -- no fabricated in-between stages the
// backend doesn't actually track.
export default function TaskBoard({ initialTasks, entityNames }: { initialTasks: TaskRead[]; entityNames: Record<string, string> }) {
  const [tasks, setTasks] = useState(initialTasks);
  const [domainFilter, setDomainFilter] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const statusMatch = STATUS_FILTERS.find((s) => s.key === statusFilter)?.match ?? (() => true);
  const filtered = tasks.filter((t) => (domainFilter ? t.domain === domainFilter : true) && statusMatch(t));
  const selected = tasks.find((t) => t.id === selectedId) ?? null;

  function handleTaskUpdated(updated: TaskRead) {
    setTasks((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
  }

  function handleCreated(task: TaskRead) {
    setTasks((prev) => [task, ...prev]);
    setCreating(false);
    setSelectedId(task.id);
  }

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          <Chip label="Tout" active={domainFilter === null} onClick={() => setDomainFilter(null)} />
          {DOMAINS.map((d) => (
            <Chip key={d} label={SECTOR_LABEL_FR[d]} active={domainFilter === d} onClick={() => setDomainFilter(d)} />
          ))}
        </div>
        <Button onClick={() => setCreating(true)}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          Nouvelle action
        </Button>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {STATUS_FILTERS.map((s) => (
          <Chip key={s.key} label={`${s.label} (${tasks.filter(s.match).length})`} active={statusFilter === s.key} onClick={() => setStatusFilter(s.key)} />
        ))}
      </div>

      <ul className="mt-6 space-y-3">
        {filtered.length === 0 ? (
          <EmptyState message="Aucune tâche ne correspond à ce filtre." />
        ) : (
          filtered.map((t) => <TaskCard key={t.id} task={t} onOpen={() => setSelectedId(t.id)} />)
        )}
      </ul>

      {selected && (
        <TaskDetailPanel
          task={selected}
          entityName={selected.related_entity_id ? entityNames[selected.related_entity_id] ?? null : null}
          onClose={() => setSelectedId(null)}
          onChange={handleTaskUpdated}
        />
      )}

      {creating && <TaskCreateModal onClose={() => setCreating(false)} onCreated={handleCreated} />}
    </div>
  );
}
