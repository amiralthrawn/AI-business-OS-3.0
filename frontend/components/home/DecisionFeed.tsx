"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import { approveTask, createTask, rejectTask } from "@/lib/api";
import { entityHref } from "@/lib/related-entity";
import type { AIPriorityItem, TaskRead } from "@/lib/types";

const DOMAIN_LABEL: Record<string, string> = { finance: "Finance", procurement: "Achats", sales: "Ventes", accounting: "Comptabilité", people: "Équipe" };
const eur = (n: number) => new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(n);

type Phase = "open" | "validated" | "ignored";
const STORE = "decision-feed-v1";

function keyOf(item: AIPriorityItem, i: number) {
  return `${item.kind}:${item.entity_id ?? item.related_entity_id ?? item.title}:${i}`.slice(0, 160);
}

function detailHref(item: AIPriorityItem): string | null {
  if (item.detail_kind === "risk" && item.detail_id) return `/intelligence/risks/${item.detail_id}`;
  if (item.detail_kind === "opportunity" && item.detail_id) return `/intelligence/opportunities/${item.detail_id}`;
  return null;
}

// Level 1: one card per decision, sorted by what is at stake in euros.
// Level 2 ("Pourquoi ?") sits inside each card; level 3 is the Données menu.
export default function DecisionFeed({ items, tasks }: { items: AIPriorityItem[]; tasks: TaskRead[] }) {
  const [phase, setPhase] = useState<Record<string, Phase>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORE);
      // eslint-disable-next-line react-hooks/set-state-in-effect
      if (saved) setPhase(JSON.parse(saved));
    } catch {}
  }, []);

  function remember(next: Record<string, Phase>) {
    setPhase(next);
    try {
      localStorage.setItem(STORE, JSON.stringify(next));
    } catch {}
  }

  async function run(key: string, action: () => Promise<unknown>, result: Phase) {
    setBusy(key);
    setError(null);
    try {
      await action();
      remember({ ...phase, [key]: result });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Une erreur est survenue.");
    } finally {
      setBusy(null);
    }
  }

  const cards = [
    ...tasks.map((t) => ({ type: "task" as const, key: `task:${t.id}`, task: t, amount: 0 })),
    // A signal already turned into a proposed action is shown once, as the action.
    ...items.filter((item) => !tasks.some((t) => t.title.includes(item.title) || (t.description ?? "").includes(item.title))).map((item, i) => ({ type: "signal" as const, key: keyOf(item, i), item, amount: item.amount_eur ?? 0 })),
  ];
  const visible = cards.filter((c) => (phase[c.key] ?? "open") === "open");
  const validated = cards.filter((c) => phase[c.key] === "validated").length;

  if (cards.length === 0) {
    return (
      <Card className="p-8 text-center">
        <p className="text-[15px] font-semibold text-text">Rien à décider pour l&rsquo;instant.</p>
        <p className="mx-auto mt-2 max-w-md text-[13.5px] text-text-soft">
          Les décisions apparaissent dès que l&rsquo;IA a vos données. Déposez vos fichiers de ventes, d&rsquo;achats ou votre comptabilité dans la configuration.
        </p>
        <Link href="/settings" className="mt-4 inline-block text-[13px] font-semibold text-accent-strong hover:underline">
          Ajouter mes données →
        </Link>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {error && <p className="text-[13px] text-danger">{error}</p>}
      {visible.length === 0 && (
        <Card className="p-8 text-center">
          <p className="text-[15px] font-semibold text-text">Tout est traité 🎉</p>
          <p className="mt-1 text-[13.5px] text-text-soft">{validated} décision{validated > 1 ? "s" : ""} validée{validated > 1 ? "s" : ""}. Le suivi est dans « Données › Actions ».</p>
        </Card>
      )}
      {visible.map((c) =>
        c.type === "task" ? (
          <Card key={c.key} className="p-6">
            <div className="flex flex-wrap items-center gap-2">
              <Badge label="À valider" tone="warning" />
              {c.task.domain && <span className="text-[11px] font-bold uppercase tracking-wide text-accent-strong">{DOMAIN_LABEL[c.task.domain] ?? c.task.domain}</span>}
            </div>
            <p className="mt-2.5 text-[16px] font-semibold leading-snug text-text">{c.task.title}</p>
            {c.task.description && <p className="mt-1.5 text-[13.5px] text-text-soft">{c.task.description}</p>}
            <p className="mt-2 text-[12.5px] text-text-faint">Rien n&rsquo;est exécuté sans votre accord.</p>
            <div className="mt-4 flex flex-wrap gap-2.5">
              <Button loading={busy === c.key} onClick={() => run(c.key, () => approveTask(c.task.id), "validated")}>Valider</Button>
              <Link href="/actions/tasks"><span className="inline-flex rounded-xl border-[1.5px] border-border-strong px-4 py-2.5 text-[13.5px] font-semibold text-text hover:border-text-faint">Modifier</span></Link>
              <Button variant="ghost" loading={busy === c.key} onClick={() => run(c.key, () => rejectTask(c.task.id), "ignored")}>Ignorer</Button>
            </div>
          </Card>
        ) : (
          <SignalCard
            key={c.key}
            item={c.item}
            busy={busy === c.key}
            onValidate={() =>
              run(
                c.key,
                () =>
                  createTask({
                    title: c.item.recommendation ?? c.item.title,
                    description: `Décision validée depuis l'accueil : ${c.item.title}`,
                    domain: c.item.domain,
                    related_entity_type: (c.item.entity_type ?? c.item.related_entity_type) ?? undefined,
                    related_entity_id: (c.item.entity_id ?? c.item.related_entity_id) ?? undefined,
                  }),
                "validated",
              )
            }
            onIgnore={() => remember({ ...phase, [c.key]: "ignored" })}
          />
        ),
      )}
    </div>
  );
}

function SignalCard({ item, busy, onValidate, onIgnore }: { item: AIPriorityItem; busy: boolean; onValidate: () => void; onIgnore: () => void }) {
  const detail = detailHref(item);
  const type = item.entity_type ?? item.related_entity_type;
  const id = item.entity_id ?? item.related_entity_id;
  const data = type && id ? entityHref(type, id) : null;
  const opportunity = item.kind === "opportunity" || item.interpretation_type === "opportunity";
  return (
    <Card className="p-6">
      <div className="flex flex-wrap items-center gap-2">
        <Badge label={opportunity ? "Opportunité" : "Point d'attention"} tone={opportunity ? "success" : "danger"} />
        <span className="text-[11px] font-bold uppercase tracking-wide text-accent-strong">{DOMAIN_LABEL[item.domain] ?? item.domain}</span>
        {item.amount_eur ? <span className="ml-auto text-[13px] font-semibold text-text">{eur(item.amount_eur)} concernés</span> : null}
      </div>
      <p className="mt-2.5 text-[16px] font-semibold leading-snug text-text">{item.title}</p>
      <p className="mt-2 text-[13.5px] text-text">
        <span className="font-semibold text-accent-strong">L&rsquo;IA propose : </span>
        {item.recommendation ?? "Examiner ce point avec les données associées."}
      </p>
      <div className="mt-4 flex flex-wrap gap-2.5">
        <Button loading={busy} onClick={onValidate}>Valider</Button>
        <Link href={detail ?? data ?? "/actions/tasks"}>
          <span className="inline-flex rounded-xl border-[1.5px] border-border-strong px-4 py-2.5 text-[13.5px] font-semibold text-text hover:border-text-faint">Modifier</span>
        </Link>
        <Button variant="ghost" onClick={onIgnore}>Ignorer</Button>
      </div>
      <details className="mt-4">
        <summary className="cursor-pointer select-none text-[12.5px] font-semibold text-text-soft hover:text-text">Pourquoi ?</summary>
        <div className="mt-2.5 space-y-3 rounded-xl bg-surface-sunken p-4">
          {item.explanation && <p className="text-[13px] text-text-soft">{item.explanation}</p>}
          {item.decision_options && item.decision_options.length > 0 && (
            <ul className="space-y-2">
              {item.decision_options.map((o) => (
                <li key={o.label} className="text-[12.5px] text-text-soft">
                  <span className="font-semibold text-text">{o.label}</span> — bénéfice : {o.expected_benefit} ; contrepartie : {o.trade_offs}
                </li>
              ))}
            </ul>
          )}
          <p className="text-[12px] text-text-faint">
            Confiance de l&rsquo;IA : {item.confidence}. Le montant est ce qui est déjà facturé avec cet élément, pas une prévision de perte.
          </p>
          <div className="flex flex-wrap gap-4 text-[12.5px] font-semibold">
            {detail && <Link href={detail} className="text-accent-strong hover:underline">Voir le raisonnement complet →</Link>}
            {data && <Link href={data} className="text-text-soft hover:text-text hover:underline">Voir la fiche et les données sources</Link>}
          </div>
        </div>
      </details>
    </Card>
  );
}
