import AgentsHub from "@/components/agents/AgentsHub";
import Card from "@/components/ui/Card";
import ErrorBanner from "@/components/ui/ErrorBanner";
import PageHeader from "@/components/ui/PageHeader";
import { getAgentsOverview } from "@/lib/api";

export const dynamic = "force-dynamic";

// The three agents that work for the company: what powers each, what it did
// last, and a direct line to each (the assistant only explains your data).
export default async function AgentsPage() {
  const overview = await getAgentsOverview().catch(() => null);
  return (
    <main className="mx-auto max-w-3xl space-y-7 p-4 sm:p-8 md:p-10">
      <PageHeader title="Agents IA" description="Les trois agents qui travaillent pour vous : ce qui les fait tourner, leur dernière tâche, et une ligne directe vers chacun." />
      {!overview && <ErrorBanner message="Impossible de charger les agents. L'API est-elle démarrée ?" />}
      {overview && overview.agents.length === 0 && (
        <Card className="p-6 text-[13.5px] text-text-soft">Seuls les profils qui gèrent la configuration voient et pilotent les agents. Leurs trouvailles arrivent sur votre accueil.</Card>
      )}
      {overview && overview.agents.length > 0 && <AgentsHub overview={overview} />}
    </main>
  );
}
