import { formatTimeFR } from "@/lib/labels";
import type { OSActivityItem } from "@/lib/types";

const DOMAIN_LABEL_FR: Record<string, string> = { finance: "Finance", procurement: "Achats", sales: "Ventes" };

export default function OSActivityRow({ item }: { item: OSActivityItem }) {
  return (
    <div className="flex items-start gap-4 border-b border-border py-3.5 text-[13px] last:border-0">
      <span className="w-12 shrink-0 pt-0.5 font-mono text-[11.5px] text-text-faint">{formatTimeFR(item.occurred_at)}</span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          {item.domain && (
            <span className="text-[10.5px] font-bold uppercase tracking-wide text-accent-strong">{DOMAIN_LABEL_FR[item.domain] ?? item.domain}</span>
          )}
          <span className="font-medium text-text">{item.label}</span>
        </div>
        <p className="mt-0.5 truncate text-text-soft">{item.detail}</p>
      </div>
    </div>
  );
}
