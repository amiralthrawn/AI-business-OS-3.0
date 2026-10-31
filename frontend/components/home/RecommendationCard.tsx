import Link from "next/link";
import Badge from "@/components/ui/Badge";
import Card from "@/components/ui/Card";
import { entityHref } from "@/lib/related-entity";
import type { AIPriorityItem } from "@/lib/types";

const DOMAIN_LABEL: Record<string, string> = { finance: "Finance", procurement: "Achats", sales: "Ventes", accounting: "Comptabilité", people: "Équipe" };
const LEVEL: Record<string, { label: string; tone: "danger" | "warning" | "neutral" }> = {
  high: { label: "élevé", tone: "danger" },
  medium: { label: "moyen", tone: "warning" },
  low: { label: "faible", tone: "neutral" },
};

function detailHref(item: AIPriorityItem): string | null {
  if (item.detail_kind === "risk" && item.detail_id) return `/intelligence/risks/${item.detail_id}`;
  if (item.detail_kind === "opportunity" && item.detail_id) return `/intelligence/opportunities/${item.detail_id}`;
  return null;
}

// Three levels in one card: the recommendation in plain words (level 1),
// the reasoning and options one click away in a fold (level 2), and the
// underlying objects and raw records behind links (level 3).
export default function RecommendationCard({ item }: { item: AIPriorityItem }) {
  const detail = detailHref(item);
  const type = item.entity_type ?? item.related_entity_type;
  const id = item.entity_id ?? item.related_entity_id;
  const data = type && id ? entityHref(type, id) : null;

  return (
    <Card className="p-6">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[11px] font-bold uppercase tracking-wide text-accent-strong">{DOMAIN_LABEL[item.domain] ?? item.domain}</span>
        <Badge label={`Impact ${LEVEL[item.impact]?.label ?? item.impact}`} tone={LEVEL[item.impact]?.tone ?? "neutral"} />
        <Badge label={`Urgence ${LEVEL[item.urgency]?.label ?? item.urgency}`} tone={LEVEL[item.urgency]?.tone ?? "neutral"} />
      </div>
      <p className="mt-2.5 text-[16px] font-semibold leading-snug text-text">{item.title}</p>
      {item.recommendation && (
        <p className="mt-2 text-[13.5px] text-text">
          <span className="font-semibold text-accent-strong">Je recommande : </span>
          {item.recommendation}
        </p>
      )}

      {(item.explanation || (item.decision_options && item.decision_options.length > 0)) && (
        <details className="group mt-3">
          <summary className="cursor-pointer select-none text-[12.5px] font-semibold text-text-soft hover:text-text">Pourquoi cette recommandation</summary>
          <div className="mt-2.5 space-y-3 rounded-xl bg-surface-sunken p-4">
            {item.explanation && <p className="text-[13px] text-text-soft">{item.explanation}</p>}
            {item.decision_options && item.decision_options.length > 0 && (
              <ul className="space-y-2">
                {item.decision_options.map((o) => (
                  <li key={o.label} className="text-[12.5px] text-text-soft">
                    <span className="font-semibold text-text">{o.label}</span> — bénéfice : {o.expected_benefit} ; contrepartie : {o.trade_offs}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </details>
      )}

      {(detail || data) && (
        <div className="mt-4 flex flex-wrap items-center gap-4 text-[12.5px] font-semibold">
          {detail && (
            <Link href={detail} className="text-accent-strong hover:underline">
              Examiner le détail →
            </Link>
          )}
          {data && (
            <Link href={data} className="text-text-soft hover:text-text hover:underline">
              Voir les données
            </Link>
          )}
        </div>
      )}
    </Card>
  );
}
