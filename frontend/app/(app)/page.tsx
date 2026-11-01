import Link from "next/link";
import OnboardingGate from "@/components/home/OnboardingGate";
import BriefingCard from "@/components/home/BriefingCard";
import DecisionFeed from "@/components/home/DecisionFeed";
import HomeAskAI from "@/components/home/HomeAskAI";
import AnimatedNumber from "@/components/ui/AnimatedNumber";
import Card from "@/components/ui/Card";
import ErrorBanner from "@/components/ui/ErrorBanner";
import PageHeader from "@/components/ui/PageHeader";
import StatCard from "@/components/ui/StatCard";
import { getCompany, getFinanceOverview, getHomeView, getMe } from "@/lib/api";
import { can } from "@/lib/objects";
import type { FinanceOverview, HomeResponse } from "@/lib/types";

export const dynamic = "force-dynamic";

// Three levels of reading:
//  1. this page -- a feed of decisions sorted by euros at stake, one click each;
//  2. "Pourquoi ?" inside every card -- reasoning, sources, links to the records;
//  3. "Données" (menu) -- every detailed table behind a single entry and a search.
export default async function CommandCenterPage() {
  let home: HomeResponse | null = null;
  let error: string | null = null;
  try {
    home = await getHomeView();
  } catch {
    error = "Impossible de joindre le backend. L'API est-elle démarrée ?";
  }

  const [me, company] = await Promise.all([getMe().catch(() => null), getCompany().catch(() => null)]);
  const needsSetup = !!company && !company.industry && can(me?.permissions, "write:settings");

  let finance: FinanceOverview | null = null;
  if (home && can(me?.permissions, "view:finance")) finance = await getFinanceOverview().catch(() => null);

  const signals = home?.priorities.filter((p) => p.kind === "risk" || p.kind === "opportunity" || p.kind === "decision" || p.kind === "interpretation") ?? [];
  const pendingTasks = home?.tasks.recent_tasks.filter((t) => t.status === "pending_validation") ?? [];
  const atStake = signals.reduce((sum, s) => sum + (s.amount_eur ?? 0), 0);

  return (
    <main className="mx-auto max-w-3xl space-y-10 p-6 md:p-10">
      <OnboardingGate needsSetup={needsSetup} />

      <PageHeader title={`Bonjour${me?.profile?.name ? ` ${me.profile.name.split(" ")[0]}` : ""}.`} description="Voici ce qui demande votre décision aujourd'hui." />

      {error && <ErrorBanner message={error} />}

      {home && (
        <>
          {/* Trois chiffres, adaptés au rôle */}
          <section className="grid gap-4 sm:grid-cols-3">
            {finance ? (
              <>
                <StatCard label="Chiffre d'affaires" value={<AnimatedNumber value={finance.total_revenue} format="EUR" />} />
                <StatCard label="Coûts" value={<AnimatedNumber value={finance.total_costs} format="EUR" />} />
                <StatCard
                  label="Marge globale"
                  value={finance.overall_margin_pct === null ? "—" : <AnimatedNumber value={finance.overall_margin_pct * 100} format="percent" />}
                  emphasize={(finance.overall_margin_pct ?? 0) < 0}
                />
              </>
            ) : (
              <>
                <StatCard label="Décisions en attente" value={<AnimatedNumber value={signals.length + pendingTasks.length} format="number" />} />
                <StatCard label="Montant concerné" value={<AnimatedNumber value={atStake} format="EUR" />} />
                <StatCard label="Actions à valider" value={<AnimatedNumber value={pendingTasks.length} format="number" />} />
              </>
            )}
          </section>

          {home.briefing && <BriefingCard briefing={home.briefing} viewer={home.viewer} />}

          <section>
            <span className="mb-4 block text-[11.5px] font-bold uppercase tracking-wide text-text-faint">Vos décisions, par montant concerné</span>
            <DecisionFeed items={signals} tasks={pendingTasks} />
          </section>

          {can(me?.permissions, "action:ask_ai") && (
            <section>
              <span className="mb-4 block text-[11.5px] font-bold uppercase tracking-wide text-text-faint">Une question ?</span>
              <Card className="p-6">
                <HomeAskAI />
              </Card>
            </section>
          )}

          <p className="text-center text-[13px] text-text-soft">
            Besoin de vérifier un chiffre ?{" "}
            <Link href="/data" className="font-semibold text-accent-strong hover:underline">
              Ouvrir les données →
            </Link>
          </p>
        </>
      )}
    </main>
  );
}
