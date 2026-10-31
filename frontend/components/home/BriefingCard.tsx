import type { HomeBriefing, HomeViewer } from "@/lib/types";

// Level 1, first thing on Home: the AI says in plain words what matters for
// this person today. Written by the backend from what this profile may see.
export default function BriefingCard({ briefing, viewer }: { briefing: HomeBriefing; viewer: HomeViewer | null | undefined }) {
  return (
    <section className="rounded-[20px] border border-border bg-surface p-7 shadow-card md:p-9">
      <p className="text-[11.5px] font-bold uppercase tracking-wide text-accent-strong">
        Votre point du jour{viewer ? ` · ${viewer.job_title ? `${viewer.job_title} (${viewer.role})` : viewer.role}` : ""}
      </p>
      <h2 className="mt-3 font-display text-[26px] italic leading-snug md:text-[30px]">{briefing.headline}</h2>
      {briefing.lines.length > 0 && (
        <ul className="mt-4 space-y-1.5">
          {briefing.lines.map((line) => (
            <li key={line} className="text-[14px] text-text-soft">
              {line}
            </li>
          ))}
        </ul>
      )}
      {viewer && viewer.areas.length > 0 && (
        <p className="mt-5 text-[12px] text-text-faint">Vous voyez : {viewer.areas.join(" · ")}. Votre direction peut ajuster cet accès dans Configuration.</p>
      )}
    </section>
  );
}
