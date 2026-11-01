"use client";

import Link from "next/link";
import { useState } from "react";
import { can } from "@/lib/objects";

type Tile = { href: string; label: string; hint: string; permission: string; words: string };
const GROUPS: { title: string; tiles: Tile[] }[] = [
  {
    title: "Ventes & clients",
    tiles: [
      { href: "/business/sales", label: "Ventes", hint: "Chiffre d'affaires, commandes, devis", permission: "view:sales", words: "ca revenu commande devis facture" },
      { href: "/data/customers", label: "Clients", hint: "Fiches clients et historique", permission: "view:sales", words: "client prospect" },
    ],
  },
  {
    title: "Achats & fournisseurs",
    tiles: [
      { href: "/business/procurement", label: "Achats", hint: "Commandes et factures fournisseurs", permission: "view:procurement", words: "achat commande fournisseur facture" },
      { href: "/data/suppliers", label: "Fournisseurs", hint: "Fiches et fiabilité", permission: "view:procurement", words: "fournisseur livraison" },
    ],
  },
  {
    title: "Catalogue & stock",
    tiles: [{ href: "/data/products", label: "Produits et stock", hint: "Références, prix, marges", permission: "view:catalog", words: "produit article stock prix marge référence" }],
  },
  {
    title: "Finance & trésorerie",
    tiles: [
      { href: "/business/finance", label: "Finance", hint: "Résultats, marges, évolution", permission: "view:finance", words: "marge résultat coûts comptabilité" },
      { href: "/data/transactions", label: "Transactions", hint: "Toutes les écritures", permission: "view:finance", words: "transaction écriture paiement" },
      { href: "/direction", label: "Trésorerie & direction", hint: "Trésorerie, actionnariat", permission: "view:treasury|view:ownership", words: "trésorerie cash banque actionnaire" },
    ],
  },
  {
    title: "Communications & équipe",
    tiles: [
      { href: "/communications", label: "Communications", hint: "E-mails et brouillons", permission: "view:communications", words: "email mail message brouillon" },
      { href: "/data/contacts", label: "Contacts", hint: "Personnes chez vos clients et fournisseurs", permission: "view:communications", words: "contact personne" },
      { href: "/people", label: "Équipe", hint: "Personnes et rôles", permission: "view:people", words: "équipe employé rôle" },
    ],
  },
  {
    title: "Suivi de l'IA",
    tiles: [
      { href: "/intelligence/risks", label: "Risques et opportunités", hint: "Tout ce que l'IA a détecté", permission: "view:intelligence", words: "risque opportunité alerte" },
      { href: "/actions/tasks", label: "Actions et validations", hint: "Décisions validées, à valider", permission: "view:actions", words: "tâche action validation décision" },
      { href: "/actions/activity", label: "Journal d'activité", hint: "Ce qui s'est passé dans l'entreprise", permission: "view:intelligence", words: "historique journal activité" },
    ],
  },
];

const norm = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

// Level 3: every detailed table behind one menu entry, with one search box.
export default function DataHub({ permissions }: { permissions: string[] | undefined }) {
  const [q, setQ] = useState("");
  const needle = norm(q.trim());
  const groups = GROUPS.map((g) => ({
    ...g,
    tiles: g.tiles.filter(
      (t) => (!t.permission || t.permission.split("|").some((p) => can(permissions, p))) && (!needle || norm(`${t.label} ${t.hint} ${t.words} ${g.title}`).includes(needle)),
    ),
  })).filter((g) => g.tiles.length > 0);

  return (
    <div className="space-y-8">
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Chercher : un client, une facture, la marge, la trésorerie…"
        className="w-full rounded-xl border-[1.5px] border-border-strong bg-surface px-4 py-3 text-[14px] text-text outline-none focus:border-accent"
      />
      {groups.length === 0 && <p className="text-[13.5px] text-text-soft">Aucun écran ne correspond à « {q} ».</p>}
      {groups.map((g) => (
        <section key={g.title}>
          <span className="mb-3 block text-[11.5px] font-bold uppercase tracking-wide text-text-faint">{g.title}</span>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {g.tiles.map((t) => (
              <Link key={t.href} href={t.href} className="rounded-2xl border border-border bg-surface p-5 transition-colors hover:border-accent">
                <p className="text-[14.5px] font-semibold text-text">{t.label}</p>
                <p className="mt-1 text-[12.5px] text-text-soft">{t.hint}</p>
              </Link>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
