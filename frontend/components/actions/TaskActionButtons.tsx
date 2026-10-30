"use client";

import { useState } from "react";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import { approveTask, rejectTask } from "@/lib/api";

const STATUS_LABEL: Record<string, string> = {
  approved: "approuvée",
  executed: "exécutée",
  rejected: "rejetée",
};

// The one Human-in-the-Loop control: an AI-proposed action (a Task with
// pending_action set) is never executed on its own -- this is the only path
// that turns pending_validation into executed or rejected, reused by the
// Tasks list, Risk/Opportunity detail, Home and Ask AI.
export default function TaskActionButtons({ taskId, taskTitle }: { taskId: string; taskTitle: string }) {
  const [status, setStatus] = useState<string | null>(null);
  const [loadingAction, setLoadingAction] = useState<"approve" | "reject" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handle(action: "approve" | "reject") {
    setLoadingAction(action);
    setError(null);
    try {
      const task = action === "approve" ? await approveTask(taskId) : await rejectTask(taskId);
      setStatus(task.status);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Une erreur est survenue.");
    } finally {
      setLoadingAction(null);
    }
  }

  return (
    <div className="rounded-2xl border-[1.5px] border-warning-soft bg-warning-soft/30 p-5">
      <p className="text-[13.5px] font-semibold text-text">Action proposée&nbsp;: {taskTitle}</p>
      {error && <p className="mt-2 text-[12.5px] text-danger">{error}</p>}
      {status ? (
        <div className="mt-3 flex items-center gap-2">
          <Badge label={STATUS_LABEL[status] ?? status} tone={status === "rejected" ? "neutral" : "success"} />
          <span className="text-[12.5px] text-text-soft">La tâche est maintenant {STATUS_LABEL[status] ?? status}.</span>
        </div>
      ) : (
        <div className="mt-3.5 flex gap-2.5">
          <Button variant="primary" loading={loadingAction === "approve"} onClick={() => handle("approve")} className="flex-1">
            {loadingAction !== "approve" && (
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            )}
            Approuver
          </Button>
          <Button variant="ghost" loading={loadingAction === "reject"} onClick={() => handle("reject")} className="flex-1">
            Rejeter
          </Button>
        </div>
      )}
    </div>
  );
}
