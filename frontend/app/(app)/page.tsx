import Link from "next/link";
import OnboardingGate from "@/components/home/OnboardingGate";
import BriefingCard from "@/components/home/BriefingCard";
import DataLevel from "@/components/home/DataLevel";
import RecommendationCard from "@/components/home/RecommendationCard";
import NarrativeCard from "@/components/home/NarrativeCard";
import OSActivityRow from "@/components/home/OSActivityRow";
import HomeAskAI from "@/components/home/HomeAskAI";
import HomeDirector from "@/components/home/HomeDirector";
import HomeOperations from "@/components/home/HomeOperations";
import TaskCard from "@/components/actions/TaskCard";
import AnimatedNumber from "@/components/ui/AnimatedNumber";
import Badge from "@/components/ui/Badge";
import Card from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import ErrorBanner from "@/components/ui/ErrorBanner";
import PageHeader from "@/components/ui/PageHeader";
import StatCard from "@/components/ui/StatCard";
import { getCompany, getFinanceOverview, getHomeView, getMe } from "@/lib/api";
import { can } from "@/lib/objects";
import { NARRATIVE_PROPOSAL_CHANNEL_DETAILS } from "@/lib/labels";
import { monthOverMonth, monthlySpark } from "@/lib/series";
import type { AIPriorityItem, FinanceOverview, HomeResponse } from "@/lib/types";

export const dynamic = "force-dynamic";

const SECTOR_DOMAINS = [
  { domain: "finance", label: "Finance" },
  { domain: "procurement", label: "Achats" },
  { domain: "sales", label: "Ventes" },
];

function sectorState(priorities: AIPriorityItem[], domain: string): { label: string; tone: "danger" | "success" | "warning" | "neutral" } {
  const inDomain = priorities.filter((p) => p.domain === domain);
  if (inDomain.some((p) => p.kind === "risk")) return { label: "↓ Vigilance requise", tone: "danger" };
  if (inDomain.some((p) => p.kind === "opportunity")) return { label: "↑ Bonne dynamique", tone: "success" };
  if (inDomain.length > 0) return { label: "→ À surveiller", tone: "warning" };
  return { label: "→ Stable", tone: "neutral" };
}

// Month-over-month badge, only when two complete months with transactions
// exist (lib/series.ts) -- never a hard-coded "en hausse".
function trendBadge(t: { pct: number; label: string } | null, costs: boolean): { label: string; tone: "success" | "warning" | "neutral" } | undefined {
  if (!t) return undefined;
  const up = t.pct > 0.02;
  const down = t.pct < -0.02;
  const sign = t.pct > 0 ? "+" : "";
  const label = `${up ? "↑" : down ? "↓" : "→"} ${sign}${Math.round(t.pct * 100)} % sur un mois`;
  if (!up && !down) return { label, tone: "neutral" };
  return { label, tone: up !== costs ? "success" : "warning" };
}

export default async function CommandCenterPage() {
  let home: HomeResponse | null = null;
  let error: string | null = null;
  try {
    home = await getHomeView();
  } catch {
    error = "Impossible de joindre le backend. L'API est-elle démarrée ?";
  }

  // V3: only someone who manages the company (write:settings) is sent to
  // the initial setup, and only while the company has not declared its sector.
  const [me, company] = await Promise.all([getMe().catch(() => null), getCompany().catch(() => null)]);
  const needsSetup = !!company && !company.industry && can(me?.permissions, "write:settings");

  let finance: FinanceOverview | null = null;
  if (home) {
    finance = await getFinanceOverview().catch(() => null);
  }

  const toDecide = home?.priorities.filter((p) => p.kind === "risk" || p.kind === "opportunity").slice(0, 4) ?? [];
  const pendingTasks = home?.tasks.recent_tasks.filter((t) => t.status === "pending_validation") ?? [];
  const proposals = home?.company_narrative.filter((n) => n.channel_detail && NARRATIVE_PROPOSAL_CHANNEL_DETAILS.includes(n.channel_detail)) ?? [];
  const happened = home?.company_narrative.filter((n) => !n.channel_detail || !NARRATIVE_PROPOSAL_CHANNEL_DETAILS.includes(n.channel_detail)) ?? [];

  return (
    <main className="space-y-14 p-8 md:p-12">
      <OnboardingGate needsSetup={needsSetup} />

      <PageHeader
        title={`Bonjour${me?.profile?.name ? ` ${me.profile.name.split(" ")[0]}` : ""}.`}
        description="Voici ce que l'IA a remarqué pour vous aujourd'hui."
        action={
          <div className="hidden items-center gap-1.5 sm:flex">
            <span className="h-1.5 w-1.5 rounded-full bg-success" />
            <span className="font-mono text-[11.5px] text-text-faint">Mis à jour à l&rsquo;instant</span>
          </div>
        }
      />

      {error && <ErrorBanner message={error} />}

      {home && (
        <>
          {/* NIVEAU 1 -- l'IA d'abord : le point du jour, puis les recommandations */}
          {home.briefing && <BriefingCard briefing={home.briefing} viewer={home.viewer} />}

          <section>
            <div className="mb-5 flex items-baseline gap-2.5">
              <span className="text-[11.5px] font-bold tracking-wide text-text-faint uppercase">Ce que l&rsquo;IA vous recommande</span>
              {toDecide.length > 0 && <Badge label={`${toDecide.length} sujet${toDecide.length > 1 ? "s" : ""}`} tone="accent" />}
            </div>
            {toDecide.length === 0 ? (
              <EmptyState message="Aucune recommandation pour l'instant. Elles apparaissent dès que l'IA a vos données." />
            ) : (
              <div className="grid gap-4 md:grid-cols-2">
                {toDecide.map((item, i) => (
                  <RecommendationCard key={`${item.kind}-${item.entity_id ?? item.related_entity_id ?? i}`} item={item} />
                ))}
              </div>
            )}
          </section>

          {pendingTasks.length > 0 && (
            <section>
              <div className="mb-5 flex items-baseline gap-2.5">
                <span className="text-[11.5px] font-bold tracking-wide text-text-faint uppercase">À valider</span>
                <Badge label={`${pendingTasks.length} action${pendingTasks.length > 1 ? "s" : ""}`} tone="warning" />
              </div>
              <ul className="space-y-3">
                {pendingTasks.map((task) => (
                  <TaskCard key={task.id} task={task} />
                ))}
              </ul>
              <p className="mt-3 px-1 text-[11.5px] text-text-faint">Aucune action n&rsquo;est exécutée sans votre validation.</p>
            </section>
          )}

          {can(me?.permissions, "action:ask_ai") && (
            <section>
              <span className="mb-5 block text-[11.5px] font-bold tracking-wide text-text-faint uppercase">Demander à l&rsquo;IA</span>
              <Card className="p-6">
                <HomeAskAI />
              </Card>
            </section>
          )}

          {finance && can(me?.permissions, "view:finance") && (
            <section className="grid gap-5 md:grid-cols-3">
              <StatCard
                label="Chiffre d'affaires"
                value={<AnimatedNumber value={finance.total_revenue} format="EUR" />}
                sparkline={monthlySpark(finance.monthly_sales, "commandes clients enregistrées") ?? undefined}
                sparklineEmpty="Historique mensuel insuffisant"
                sparklineTone="text-accent"
                badge={trendBadge(monthOverMonth(finance.monthly_sales), false)}
              />
              <StatCard
                label="Coûts"
                value={<AnimatedNumber value={finance.total_costs} format="EUR" />}
                sparkline={monthlySpark(finance.monthly_purchases, "commandes d'achat et factures fournisseurs") ?? undefined}
                sparklineEmpty="Historique mensuel insuffisant"
                badge={trendBadge(monthOverMonth(finance.monthly_purchases), true)}
              />
              <StatCard
                label="Marge globale"
                value={finance.overall_margin_pct === null ? "—" : <AnimatedNumber value={finance.overall_margin_pct * 100} format="percent" />}
                emphasize={(finance.overall_margin_pct ?? 0) < 0}
                sparklineEmpty={finance.overall_margin_pct === null ? "Pas encore de ventes chiffrées" : "Pas de série mensuelle de marge"}
                badge={finance.overall_margin_pct === null ? undefined : finance.overall_margin_pct < 0 ? { label: "Sous pression", tone: "danger" } : { label: "Positive", tone: "success" }}
              />
            </section>
          )}

          {/* NIVEAU 2 -- le détail, replié : opérations, direction, vie de l'entreprise */}
          <details className="group rounded-[20px] border border-border bg-surface">
            <summary className="flex cursor-pointer select-none items-center justify-between px-7 py-5 text-[14px] font-semibold text-text">
              Aller plus loin : opérations, direction, ce qui s&rsquo;est passé
              <span className="text-[12px] font-medium text-text-faint group-open:hidden">Afficher</span>
            </summary>
            <div className="space-y-14 px-7 pb-8 pt-2">
              {SECTOR_DOMAINS.filter(({ domain }) => can(me?.permissions, `view:${domain}`)).length > 0 && (
                <section className="flex flex-wrap gap-3">
                  {SECTOR_DOMAINS.filter(({ domain }) => can(me?.permissions, `view:${domain}`)).map(({ domain, label }) => {
                    const state = sectorState(home!.priorities, domain);
                    return (
                      <Link
                        key={domain}
                        href={`/actions/activity?domain=${domain}`}
                        className="flex items-center gap-2.5 rounded-full border border-border bg-surface px-4 py-2 transition-colors hover:border-border-strong"
                      >
                        <span className="text-[13px] font-semibold text-text">{label}</span>
                        <Badge label={state.label} tone={state.tone} />
                      </Link>
                    );
                  })}
                </section>
              )}

              <HomeOperations />
              <HomeDirector />

              {proposals.length > 0 && (
                <section>
                  <span className="mb-5 block text-[11.5px] font-bold tracking-wide text-text-faint uppercase">Ce que l&rsquo;entreprise propose</span>
                  <div className="grid gap-4 md:grid-cols-2">
                    {proposals.map((item) => (
                      <NarrativeCard key={item.id} item={item} />
                    ))}
                  </div>
                </section>
              )}

              {happened.length > 0 && (
                <section>
                  <span className="mb-5 block text-[11.5px] font-bold tracking-wide text-text-faint uppercase">Ce qui s&rsquo;est passé</span>
                  <div className="grid gap-4 md:grid-cols-2">
                    {happened.map((item) => (
                      <NarrativeCard key={item.id} item={item} showAction={false} />
                    ))}
                  </div>
                </section>
              )}

              {home.os_activity.length > 0 && (
                <section>
                  <div className="mb-4 flex items-baseline justify-between">
                    <span className="text-[11.5px] font-bold tracking-wide text-text-faint uppercase">Activité de l&rsquo;OS</span>
                    <Link href="/actions/activity" className="text-[12.5px] font-medium text-accent-strong hover:underline">
                      Voir tout →
                    </Link>
                  </div>
                  <Card className="px-6">
                    {home.os_activity.map((item, i) => (
                      <OSActivityRow key={i} item={item} />
                    ))}
                  </Card>
                </section>
              )}
            </div>
          </details>

          {/* NIVEAU 3 -- les données techniques derrière tout cela */}
          <DataLevel permissions={me?.permissions} />
        </>
      )}
    </main>
  );
}
