import Link from "next/link";
import Badge from "@/components/ui/Badge";
import Card from "@/components/ui/Card";

interface EntityListItemProps {
  href: string;
  name: string;
  subtitle: string;
  signalCount?: number;
  topSignalTitle?: string | null;
}

// The one list-row card for a Supplier/Customer/Product -- name, one
// composed subtitle line (the page decides what belongs in it), an AI
// signal-count badge, and the top signal's own title when there is one.
export default function EntityListItem({ href, name, subtitle, signalCount, topSignalTitle }: EntityListItemProps) {
  return (
    <Link href={href}>
      <Card className="p-5 transition-colors hover:border-border-strong">
        <div className="flex items-center justify-between gap-3">
          <p className="font-semibold text-[14.5px] text-text">{name}</p>
          {!!signalCount && signalCount > 0 && (
            <Badge label={`${signalCount} signal${signalCount > 1 ? "aux" : ""}`} tone="accent" />
          )}
        </div>
        <p className="mt-1.5 text-[12.5px] text-text-faint">{subtitle}</p>
        {topSignalTitle && <p className="mt-2 text-[13px] text-text-soft">{topSignalTitle}</p>}
      </Card>
    </Link>
  );
}
