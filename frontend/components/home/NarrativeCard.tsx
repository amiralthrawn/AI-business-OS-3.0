import Link from "next/link";
import CreateTaskButton from "@/components/actions/CreateTaskButton";
import Badge from "@/components/ui/Badge";
import Card from "@/components/ui/Card";
import { CHANNEL_DETAIL_LABEL_FR, NARRATIVE_PROPOSAL_CHANNEL_DETAILS } from "@/lib/labels";
import type { CompanyNarrativeItem } from "@/lib/types";

const ENTITY_HREF: Record<string, string> = { supplier: "/data/suppliers", customer: "/data/customers", product: "/data/products" };

export default function NarrativeCard({ item, showAction = true }: { item: CompanyNarrativeItem; showAction?: boolean }) {
  const isProposal = item.channel_detail ? NARRATIVE_PROPOSAL_CHANNEL_DETAILS.includes(item.channel_detail) : false;
  const label = item.channel_detail ? CHANNEL_DETAIL_LABEL_FR[item.channel_detail] : null;

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between gap-3">
        <p className="font-semibold text-[14px] text-text">{item.subject}</p>
        {label && <Badge label={label} tone={isProposal ? "accent" : "neutral"} />}
      </div>
      {item.body && <p className="mt-1.5 text-[13px] leading-relaxed text-text-soft">{item.body}</p>}
      {item.related_entity_name && item.related_entity_type && ENTITY_HREF[item.related_entity_type] && (
        <Link
          href={`${ENTITY_HREF[item.related_entity_type]}`}
          className="mt-1.5 inline-block text-[12px] text-text-faint hover:text-text hover:underline"
        >
          {item.related_entity_name}
        </Link>
      )}
      {showAction && isProposal && (
        <div className="mt-3">
          <CreateTaskButton defaultTitle={item.subject ?? "Examiner la proposition"} />
        </div>
      )}
    </Card>
  );
}
