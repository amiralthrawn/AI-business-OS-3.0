import Link from "next/link";
import { can } from "@/lib/objects";

const LINKS: { href: string; label: string; permission: string }[] = [
  { href: "/data/customers", label: "Clients", permission: "view:sales" },
  { href: "/data/suppliers", label: "Fournisseurs", permission: "view:procurement" },
  { href: "/data/products", label: "Produits", permission: "view:catalog" },
  { href: "/data/transactions", label: "Transactions", permission: "view:finance" },
  { href: "/business/finance", label: "Finance détaillée", permission: "view:finance" },
  { href: "/communications", label: "Communications", permission: "view:communications" },
  { href: "/actions/activity", label: "Journal d'activité", permission: "view:intelligence" },
];

// Level 3: the technical data behind every recommendation, always reachable,
// limited to what the profile may open.
export default function DataLevel({ permissions }: { permissions: string[] | undefined }) {
  const visible = LINKS.filter((l) => can(permissions, l.permission));
  if (visible.length === 0) return null;
  return (
    <section>
      <span className="mb-4 block text-[11.5px] font-bold uppercase tracking-wide text-text-faint">Les données derrière les recommandations</span>
      <div className="flex flex-wrap gap-2.5">
        {visible.map((l) => (
          <Link key={l.href} href={l.href} className="rounded-full border border-border bg-surface px-4 py-2 text-[13px] font-semibold text-text transition-colors hover:border-accent hover:text-accent">
            {l.label}
          </Link>
        ))}
      </div>
    </section>
  );
}
