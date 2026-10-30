import Link from "next/link";
import SectionLabel from "@/components/objects/SectionLabel";
import SettingsForm from "@/components/settings/SettingsForm";
import UsersAndRoles from "@/components/settings/UsersAndRoles";
import ErrorBanner from "@/components/ui/ErrorBanner";
import PageHeader from "@/components/ui/PageHeader";
import { getAccessCatalog, getBusinessContext, getCompany, getConfigurationSuggestions, getCustomRoles, getMe, getRoles, getUsers } from "@/lib/api";
import { can } from "@/lib/objects";

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  let error: string | null = null;
  const [company, context, suggestions, users, roles, me, catalog, customRoles] = await Promise.all([
    getCompany().catch(() => null),
    getBusinessContext().catch(() => null),
    getConfigurationSuggestions().catch(() => []),
    getUsers().catch(() => []),
    getRoles().catch(() => []),
    getMe().catch(() => null),
    getAccessCatalog().catch(() => null),
    getCustomRoles().catch(() => []),
  ]);

  if (!company || !context) {
    error = "Impossible de charger la configuration de l'entreprise.";
  }

  return (
    <main className="space-y-10 p-8 md:p-12">
      <PageHeader
        title="Configuration"
        description={`Personnalisez AI Business OS${company ? ` pour ${company.name}` : ""}.`}
        action={
          <Link
            href="/onboarding"
            className="inline-flex items-center gap-2 rounded-full border border-border-strong bg-surface px-4 py-2 text-[13px] font-semibold text-text transition-colors hover:border-accent hover:text-accent"
            title="Reprendre l'assistant pas à pas (secteur, rôle, priorités). L'accès direct à l'application reste disponible."
          >
            Assistant de configuration →
          </Link>
        }
      />
      {error && <ErrorBanner message={error} />}
      {company && context && <SettingsForm company={company} context={context} suggestions={suggestions} canEdit={can(me?.permissions, "write:settings")} />}
      <section>
        <SectionLabel id="profils">Équipe et accès</SectionLabel>
        <UsersAndRoles users={users} roles={roles} customRoles={customRoles} catalog={catalog} canManage={can(me?.permissions, "write:settings")} selfId={me?.profile?.id ?? null} />
      </section>
    </main>
  );
}
