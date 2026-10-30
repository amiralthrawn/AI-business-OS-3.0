import TransactionRow from "@/components/data/TransactionRow";
import EmptyState from "@/components/ui/EmptyState";
import ErrorBanner from "@/components/ui/ErrorBanner";
import ExportCsvButton from "@/components/ui/ExportCsvButton";
import PageHeader from "@/components/ui/PageHeader";
import { TRANSACTION_STATUS_LABEL, TRANSACTION_TYPE_LABEL } from "@/lib/labels";
import { getTransactions } from "@/lib/api";
import type { TransactionRead } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function TransactionsPage() {
  let transactions: TransactionRead[] = [];
  let error: string | null = null;
  try {
    transactions = await getTransactions();
  } catch (err) {
    error = err instanceof Error ? err.message : "Impossible de charger les transactions.";
  }

  return (
    <main className="space-y-8 p-8 md:p-12">
      <PageHeader
        title="Transactions"
        description="Les commandes, factures et commandes clients les plus récentes du Data Core."
        action={
          <ExportCsvButton
            filename="transactions.csv"
            headers={["Date", "Type", "Statut", "Fournisseur", "Client", "Produit", "Montant", "Devise"]}
            rows={transactions.map((t) => [
              new Date(t.occurred_at).toLocaleDateString("fr-FR"),
              TRANSACTION_TYPE_LABEL[t.type] ?? t.type,
              TRANSACTION_STATUS_LABEL[t.status] ?? t.status,
              t.supplier_name,
              t.customer_name,
              t.product_name,
              t.amount,
              t.currency,
            ])}
          />
        }
      />
      {error && <ErrorBanner message={error} />}
      {!error && (
        <ul className="space-y-2">
          {transactions.length === 0 ? (
            <EmptyState message="Aucune transaction pour l'instant." />
          ) : (
            transactions.map((t) => <TransactionRow key={t.id} transaction={t} party="auto" linkParty showProduct />)
          )}
        </ul>
      )}
    </main>
  );
}
