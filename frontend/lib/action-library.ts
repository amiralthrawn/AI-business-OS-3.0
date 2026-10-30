// A curated library of real business actions (Step 29 points 12-13), grouped
// by sector, used to create REAL Tasks via POST /actions/tasks -- never a
// simulated execution. Selecting an item pre-fills a Task's title/domain;
// `requiresDecision` marks actions sensitive enough (financing, strategic
// commitments) that they must go through "Soumettre pour validation" before
// being considered done, rather than being closed directly (point 14).
export interface ActionTemplate {
  id: string;
  label: string;
  requiresDecision?: boolean;
}

export interface ActionDomain {
  key: string;
  label: string;
  actions: ActionTemplate[];
}

export const ACTION_LIBRARY: ActionDomain[] = [
  {
    key: "finance",
    label: "Finance",
    actions: [
      { id: "fin-loan", label: "Analyser une demande de prêt", requiresDecision: true },
      { id: "fin-financing-options", label: "Comparer plusieurs options de financement", requiresDecision: true },
      { id: "fin-big-expense", label: "Examiner une dépense importante", requiresDecision: true },
      { id: "fin-cost-variation", label: "Analyser une variation inhabituelle des coûts" },
      { id: "fin-report", label: "Préparer un rapport financier" },
      { id: "fin-monthly-summary", label: "Préparer une synthèse mensuelle" },
      { id: "fin-invoice-check", label: "Vérifier une facture" },
      { id: "fin-payment", label: "Préparer un paiement pour validation", requiresDecision: true },
      { id: "fin-anomaly", label: "Examiner une anomalie comptable" },
    ],
  },
  {
    key: "hr",
    label: "RH",
    actions: [
      { id: "hr-open-role", label: "Créer un poste", requiresDecision: true },
      { id: "hr-hiring-need", label: "Analyser le besoin de recrutement" },
      { id: "hr-job-sheet", label: "Préparer une fiche de poste" },
      { id: "hr-search-candidates", label: "Rechercher des candidats" },
      { id: "hr-screen-applications", label: "Trier des candidatures" },
      { id: "hr-prep-interview", label: "Préparer un entretien" },
      { id: "hr-organize-interview", label: "Organiser un entretien" },
      { id: "hr-contact-candidate", label: "Contacter un candidat" },
      { id: "hr-prepare-offer", label: "Préparer une proposition", requiresDecision: true },
      { id: "hr-onboarding", label: "Organiser un onboarding" },
      { id: "hr-1on1", label: "Planifier une réunion avec un salarié" },
      { id: "hr-overload", label: "Analyser une surcharge d'équipe" },
      { id: "hr-raise-request", label: "Examiner une demande d'augmentation", requiresDecision: true },
    ],
  },
  {
    key: "sales",
    label: "Ventes",
    actions: [
      { id: "sales-contact-prospect", label: "Contacter un prospect" },
      { id: "sales-followup-prospect", label: "Relancer un prospect" },
      { id: "sales-prep-email", label: "Préparer un email commercial" },
      { id: "sales-prep-call", label: "Préparer un appel" },
      { id: "sales-schedule-meeting", label: "Programmer un rendez-vous" },
      { id: "sales-prep-proposal", label: "Préparer une proposition commerciale" },
      { id: "sales-followup-proposal", label: "Relancer une proposition" },
      { id: "sales-at-risk-customer", label: "Analyser un client à risque" },
      { id: "sales-identify-opportunities", label: "Identifier des opportunités commerciales" },
      { id: "sales-prep-prospecting-campaign", label: "Préparer une campagne de prospection" },
      { id: "sales-outreach-list", label: "Démarcher une liste de prospects" },
    ],
  },
  {
    key: "procurement",
    label: "Achats",
    actions: [
      { id: "proc-contact-supplier", label: "Contacter un fournisseur" },
      { id: "proc-renegotiate", label: "Renégocier un prix", requiresDecision: true },
      { id: "proc-request-quote", label: "Demander un devis" },
      { id: "proc-compare-suppliers", label: "Comparer plusieurs fournisseurs" },
      { id: "proc-find-alternative", label: "Rechercher un fournisseur alternatif" },
      { id: "proc-check-delivery", label: "Vérifier une livraison" },
      { id: "proc-followup-supplier", label: "Relancer un fournisseur" },
      { id: "proc-price-increase", label: "Analyser une hausse de prix" },
      { id: "proc-prepare-order", label: "Préparer une commande", requiresDecision: true },
      { id: "proc-dependency", label: "Identifier une dépendance fournisseur" },
    ],
  },
  {
    key: "marketing",
    label: "Marketing",
    actions: [
      { id: "mkt-linkedin-post", label: "Préparer une publication LinkedIn" },
      { id: "mkt-facebook-post", label: "Préparer une publication Facebook" },
      { id: "mkt-multi-post", label: "Préparer un post pour plusieurs réseaux" },
      { id: "mkt-newsletter", label: "Préparer une newsletter" },
      { id: "mkt-email-campaign", label: "Préparer une campagne email", requiresDecision: true },
      { id: "mkt-analyze-campaign", label: "Analyser les résultats d'une campagne" },
      { id: "mkt-respond-interactions", label: "Répondre aux interactions importantes" },
      { id: "mkt-product-campaign", label: "Préparer une campagne produit", requiresDecision: true },
      { id: "mkt-broadcast-news", label: "Diffuser une actualité de l'entreprise" },
      { id: "mkt-funnel-analysis", label: "Analyser conversion / engagement / rétention" },
    ],
  },
  {
    key: "direction",
    label: "Direction",
    actions: [
      { id: "dir-schedule-meeting", label: "Organiser un rendez-vous avec un membre de l'entreprise" },
      { id: "dir-team-meeting", label: "Organiser une réunion d'équipe" },
      { id: "dir-agenda", label: "Préparer un ordre du jour" },
      { id: "dir-minutes", label: "Préparer un compte rendu" },
      { id: "dir-strategic-decision", label: "Examiner une décision stratégique", requiresDecision: true },
      { id: "dir-compare-scenarios", label: "Comparer plusieurs scénarios", requiresDecision: true },
      { id: "dir-ask-ai", label: "Demander une analyse à l'OS" },
      { id: "dir-sector-activity", label: "Consulter l'activité d'un secteur" },
      { id: "dir-review-risks", label: "Examiner les principaux risques" },
      { id: "dir-review-opportunities", label: "Examiner les principales opportunités" },
      { id: "dir-weekly-review", label: "Préparer le bilan hebdomadaire de l'entreprise" },
    ],
  },
  {
    key: "operations",
    label: "Opérations",
    actions: [
      { id: "ops-review-problem", label: "Examiner un problème opérationnel" },
      { id: "ops-assign-owner", label: "Assigner un responsable" },
      { id: "ops-action-plan", label: "Créer un plan d'action" },
      { id: "ops-check-progress", label: "Vérifier l'avancement" },
      { id: "ops-bottleneck", label: "Identifier un goulot d'étranglement" },
      { id: "ops-analyze-delay", label: "Analyser un retard" },
      { id: "ops-organize-intervention", label: "Organiser une intervention" },
      { id: "ops-check-resolution", label: "Vérifier la résolution d'un problème" },
    ],
  },
];
