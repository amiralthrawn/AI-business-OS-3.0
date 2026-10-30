import Link from "next/link";
import Card from "@/components/ui/Card";
import type { AIPriorityItem } from "@/lib/types";

const DOMAIN_LABEL_FR: Record<string, string> = { finance: "Finance", procurement: "Achats", sales: "Ventes" };

function detailHref(item: AIPriorityItem): string | null {
  if (item.detail_kind === "risk" && item.detail_id) return `/intelligence/risks/${item.detail_id}`;
  if (item.detail_kind === "opportunity" && item.detail_id) return `/intelligence/opportunities/${item.detail_id}`;
  return null;
}

// The Command Center's own terse version of a priority: domain + one
// sentence + a single CTA into the full reasoning (PriorityCard, on the
// Risks/Opportunities/entity detail pages). Deliberately shorter than
// PriorityCard so the same signal isn't shown twice at full length in two
// places (Step 27, point 22 -- redundancy).
export default function DecisionToDoCard({ item }: { item: AIPriorityItem }) {
  const href = detailHref(item);
  const body = (
    <>
      <div className="flex items-center justify-between gap-3">
        <span className="text-[11px] font-bold uppercase tracking-wide text-accent-strong">
          {DOMAIN_LABEL_FR[item.domain] ?? item.domain}
        </span>
        {href && (
          <span className="text-[12.5px] font-semibold text-accent-strong">
            Examiner →
          </span>
        )}
      </div>
      <p className="mt-1.5 text-[14.5px] font-semibold text-text">{item.title}</p>
      {item.explanation && <p className="mt-1 line-clamp-2 text-[13px] text-text-soft">{item.explanation}</p>}
    </>
  );

  const className = "p-5 transition-colors hover:border-border-strong";

  return href ? (
    <Link href={href}>
      <Card className={className}>{body}</Card>
    </Link>
  ) : (
    <Card className={className}>{body}</Card>
  );
}
