// How far a signal travelled through Observation → Interprétation →
// Décision, derived from its real `kind` (the Snapshot's own vocabulary --
// see backend app/home/service.py). A `risk`/`opportunity`/`decision` kind
// means the full chain ran to completion; `interpretation` stopped one step
// short; `observation` is the earliest, rawest signal. Never fabricated --
// this is a direct, honest reading of data the backend already returns.
function stagesLit(kind: string): number {
  if (kind === "observation") return 1;
  if (kind === "interpretation") return 2;
  return 3; // decision, risk, opportunity
}

export default function ReasoningTrail({ kind, compact = false }: { kind: string; compact?: boolean }) {
  const lit = stagesLit(kind);
  const stages = ["Observation", "Interprétation", "Décision"];

  return (
    <div className="flex items-center gap-1.5">
      {stages.map((stage, i) => (
        <div key={stage} className="flex items-center gap-1.5">
          {i > 0 && <span className="h-px w-3.5 bg-border-strong" />}
          <span
            className={`h-1.5 w-1.5 rounded-full ${i < lit ? "bg-accent" : "bg-border-strong"}`}
            title={stage}
          />
        </div>
      ))}
      {!compact && (
        <span className="ml-2 text-[11px] text-text-faint">{stages.slice(0, lit).join(" · ")}</span>
      )}
    </div>
  );
}
