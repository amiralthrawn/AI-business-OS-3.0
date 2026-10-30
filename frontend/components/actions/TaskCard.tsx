"use client";

import TaskActionButtons from "@/components/actions/TaskActionButtons";
import Badge, { type BadgeTone } from "@/components/ui/Badge";
import Card from "@/components/ui/Card";
import { SECTOR_LABEL_FR } from "@/lib/labels";
import type { TaskRead } from "@/lib/types";

const STATUS_LABEL: Record<string, string> = {
  pending_validation: "en attente de validation",
  open: "ouverte",
  in_progress: "en cours",
  done: "terminée",
  cancelled: "annulée",
  rejected: "rejetée",
  executed: "exécutée",
};

function statusTone(status: string): BadgeTone {
  if (status === "pending_validation") return "warning";
  if (status === "executed" || status === "done") return "success";
  if (status === "rejected" || status === "cancelled") return "neutral";
  return "accent";
}

// `onOpen` is optional: TaskCard is reused on the Command Center (no detail
// panel there, just the quick approve/reject path) and on the Tasks board
// (Step 29 point 15), where the whole card opens a real detail panel.
export default function TaskCard({ task, onOpen }: { task: TaskRead; onOpen?: () => void }) {
  return (
    <Card className="p-6" as="li">
      <div
        className={onOpen ? "cursor-pointer" : undefined}
        onClick={onOpen}
        role={onOpen ? "button" : undefined}
        tabIndex={onOpen ? 0 : undefined}
      >
        <div className="flex items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            {task.domain && <Badge label={SECTOR_LABEL_FR[task.domain] ?? task.domain} tone="neutral" />}
            <p className="font-semibold text-[14.5px] text-text">{task.title}</p>
          </div>
          <div className="flex items-center gap-1.5">
            {task.requires_decision && <Badge label="Décision requise" tone="warning" />}
            <Badge label={STATUS_LABEL[task.status] ?? task.status} tone={statusTone(task.status)} />
          </div>
        </div>
        {task.description && <p className="mt-1.5 text-[13.5px] text-text-soft">{task.description}</p>}
      </div>
      {task.status === "pending_validation" && task.pending_action && (
        <div className="mt-4">
          <TaskActionButtons taskId={task.id} taskTitle={task.title} />
        </div>
      )}
    </Card>
  );
}
