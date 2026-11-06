import DataHub from "@/components/data/DataHub";
import PageHeader from "@/components/ui/PageHeader";
import { getMe } from "@/lib/api";

export const dynamic = "force-dynamic";

// Level 3 of the product: all the detailed tables behind one menu entry.
export default async function DataPage() {
  const me = await getMe().catch(() => null);
  return (
    <main className="space-y-8 p-4 sm:p-8 md:p-12">
      <PageHeader title="Données" description="Tous les tableaux détaillés, pour vérifier un chiffre à la source." />
      <DataHub permissions={me?.permissions} />
    </main>
  );
}
