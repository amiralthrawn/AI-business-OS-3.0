import OnboardingWizard from "@/components/onboarding/OnboardingWizard";
import { getBusinessContext, getCompany } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function OnboardingPage() {
  const [company, context] = await Promise.all([getCompany().catch(() => null), getBusinessContext().catch(() => null)]);

  return <OnboardingWizard initialCompany={company} initialContext={context} />;
}
