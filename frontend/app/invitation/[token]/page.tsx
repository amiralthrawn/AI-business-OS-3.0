import { AcceptInvitationForm } from "@/components/auth/AuthForms";
import { getInvitation } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function InvitationPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  const invitation = await getInvitation(token).catch(() => null);
  return <AcceptInvitationForm token={token} invitation={invitation} />;
}
