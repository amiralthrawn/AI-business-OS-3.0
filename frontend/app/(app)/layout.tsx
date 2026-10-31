import AppShell from "@/components/layout/AppShell";
import { getCompany, getMe, getPendingApprovalCount, getUsers } from "@/lib/api";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const [company, pending, me, users] = await Promise.all([
    getCompany().catch(() => null),
    getPendingApprovalCount().catch(() => ({ count: 0 })),
    getMe().catch(() => null),
    getUsers().catch(() => []),
  ]);
  const pendingCount = pending.count;

  return (
    <AppShell companyName={company?.name ?? null} pendingCount={pendingCount} me={me} users={users}>
      {children}
    </AppShell>
  );
}
